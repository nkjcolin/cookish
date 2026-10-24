"""School Chat Completions transport and the offline fake (SPEC B4).

The provider returns JSON text; parse.py owns validation and its one repair attempt.
The experimental laas.py script is never imported or executed here.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from typing import Protocol

import httpx

from app.config import TIMEOUT_SECONDS as TIMEOUT_SECONDS
from app.config import ConfigurationError, Settings
from app.credentials import APIKeyProvider, CredentialUnavailable
from app.errors import ApiError, ErrorCode
from app.quantities import ExtractionResult
from app.runtime import remaining_seconds
from app.schemas import CookAdjust

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Image:
    media_type: str
    base64: str


@dataclass(frozen=True)
class ModelRequest:
    task: str  # receipt, photo, items or interpret; for logs (and the fake)
    system: str  # instructions, from app/prompts/
    text: str | None = None  # what the user typed or said; data, never instructions
    image: Image | None = None
    source: str | None = None  # typed or voice; supplied by the app, not the model


@dataclass(frozen=True)
class ModelReply:
    text: str  # JSON, validated by the caller
    input_tokens: int | None
    output_tokens: int | None
    model_id: str | None = None


class ModelUnavailable(Exception):
    """Timeout, throttling or any provider error. Becomes UPSTREAM_UNAVAILABLE."""


class ModelClient(Protocol):
    model_id: str

    def generate(self, request: ModelRequest) -> ModelReply: ...


def _strict_schema(node: object) -> None:
    """Adapt Pydantic's schema for strict Chat Completions without changing the API."""
    if isinstance(node, dict):
        node.pop("default", None)
        if "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"])
        for value in node.values():
            _strict_schema(value)
    elif isinstance(node, list):
        for value in node:
            _strict_schema(value)


class SchoolModelClient:
    """Reuse HTTP connections; no automatic retries or implicit provider fallback."""

    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.Client | None = None,
        key_provider: Callable[[], str] | None = None,
    ) -> None:
        self.settings = settings
        self.model_id = settings.model
        self._timeout = httpx.Timeout(
            settings.timeout_seconds,
            connect=min(5, settings.timeout_seconds),
            pool=min(5, settings.timeout_seconds),
        )
        self._http = http_client or httpx.Client(
            timeout=self._timeout,
            follow_redirects=False,
        )
        self._key = key_provider or APIKeyProvider(settings).get

    def model_for_task(self, task: str) -> str:
        return self.settings.model_for_task(task)

    def generate(self, request: ModelRequest) -> ModelReply:
        model = self.model_for_task(request.task)
        schema_class = CookAdjust if request.task == "interpret" else ExtractionResult
        if self.settings.output_mode == "json_schema":
            schema = schema_class.model_json_schema()
            _strict_schema(schema)
            response_format = {
                "type": "json_schema",
                "json_schema": {"name": schema_class.__name__, "strict": True, "schema": schema},
            }
        else:
            response_format = {"type": "json_object"}
        if request.image is not None:
            instruction = (
                "Extract the purchased food items from this receipt."
                if request.task == "receipt"
                else "Identify the visible groceries in this photo."
            )
            content = [
                {"type": "text", "text": instruction},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{request.image.media_type};base64,{request.image.base64}"
                    },
                },
            ]
        else:
            text = request.text or ""
            if request.task == "items":
                text = f"Input source: {request.source or 'typed'}\nGrocery list:\n{text}"
            content = text
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": content},
            ],
            "response_format": response_format,
            "max_tokens": self.settings.max_output_tokens,
        }
        try:
            key = self._key()
            remaining = remaining_seconds()
            if remaining is not None and remaining <= 0:
                raise ModelUnavailable("The request deadline is exhausted")
            limit = min(self.settings.timeout_seconds, remaining) if remaining is not None else None
            timeout = (
                httpx.Timeout(limit, connect=min(5, limit), pool=min(5, limit))
                if limit is not None
                else self._timeout
            )
            response = self._http.post(
                self.settings.base_url + "chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
        except (httpx.HTTPError, CredentialUnavailable) as exc:
            # Never expose response bodies, authorization headers or secret values.
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            logger.warning(
                "School model request failed: type=%s status=%s", type(exc).__name__, status
            )
            raise ModelUnavailable("The school model request failed") from None
        try:
            body = response.json()
            choice = body["choices"][0]
            message = choice["message"]
            if message.get("refusal") or choice.get("finish_reason") in {
                "length",
                "content_filter",
                "tool_calls",
            }:
                raise ValueError("The model did not complete a usable answer")
            text = message["content"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Missing JSON text")
            usage = body.get("usage") or {}
            if not isinstance(usage, dict):
                usage = {}

            def tokens(name: str) -> int | None:
                value = usage.get(name)
                return value if type(value) is int and value >= 0 else None

            return ModelReply(
                text=text,
                input_tokens=tokens("prompt_tokens"),
                output_tokens=tokens("completion_tokens"),
                model_id=model,
            )
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise ModelUnavailable("The school model returned an unusable response") from None

    def close(self) -> None:
        self._http.close()


def model_id_for_task(client: ModelClient, task: str) -> str:
    """Support the original scripted-client interface as well as per-task models."""
    select = getattr(client, "model_for_task", None)
    return select(task) if callable(select) else client.model_id


# The same three foods as the backend stub, without catalogue identifiers.
_FAKE_DRAFT = {
    "items": [
        {
            "raw_text": "FP FRESH EGGS 10S",
            "display_name": "Egg",
            "count": 10,
            "unit": "pcs",
            "storage": "fridge",
            "confidence": 0.94,
        },
        {
            "raw_text": "CABBAGE RND",
            "display_name": "Cabbage",
            "count": None,
            "unit": None,
            "storage": "fridge",
            "confidence": 0.88,
        },
        {
            "raw_text": "KKM SAMBAL 230G",
            "display_name": "Sambal",
            "count": 230,
            "unit": "g",
            "storage": None,
            "confidence": 0.41,
        },
    ]
}
_FAKE_ADJUST = {"tags": ["quicker"], "max_minutes": 20}


class FakeModelClient:
    """Fixed answers and no network. Used locally and in CI until a provider is chosen."""

    model_id = "fake"

    def generate(self, request: ModelRequest) -> ModelReply:
        reply = _FAKE_ADJUST if request.task == "interpret" else _FAKE_DRAFT
        return ModelReply(text=json.dumps(reply), input_tokens=0, output_tokens=0)


@cache
def get_client() -> ModelClient:
    try:
        settings = Settings.from_env()
    except ConfigurationError as exc:
        logger.error("AI configuration error: %s", exc)
        raise ApiError(
            ErrorCode.UPSTREAM_UNAVAILABLE, "The AI provider is not configured correctly"
        ) from None
    if settings.provider == "fake":
        return FakeModelClient()
    return SchoolModelClient(settings)
