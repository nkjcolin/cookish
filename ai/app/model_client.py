"""School Chat Completions transport and the offline fake (SPEC B4).

The provider returns JSON text; parse.py owns validation and its one repair attempt.
The experimental laas.py script is never imported or executed here.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal
from functools import cache
from typing import Protocol

import httpx

from app.audio import wav_duration_seconds
from app.config import TIMEOUT_SECONDS as TIMEOUT_SECONDS
from app.config import ConfigurationError, Settings
from app.credentials import APIKeyProvider, CredentialUnavailable
from app.errors import ApiError, ErrorCode
from app.pricing import (
    ModelRate,
    PricingCache,
    PricingUnavailable,
    nonnegative_decimal,
    rate_for_model,
)
from app.quantities import ExtractionResult
from app.runtime import remaining_seconds
from app.schemas import CookAdjust

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Image:
    media_type: str
    base64: str


@dataclass(frozen=True)
class Audio:
    media_type: str
    data: bytes
    language: str | None = "en"


@dataclass(frozen=True)
class ModelRequest:
    task: str  # receipt, photo, items, interpret or transcription; for logs (and the fake)
    system: str  # instructions, from app/prompts/
    text: str | None = None  # what the user typed or said; data, never instructions
    image: Image | None = None
    source: str | None = None  # typed or voice; supplied by the app, not the model
    audio: Audio | None = None


@dataclass(frozen=True)
class ModelReply:
    text: str  # JSON, validated by the caller
    input_tokens: int | None
    output_tokens: int | None
    model_id: str | None = None
    estimated_cost: Decimal | None = None
    pricing: ModelRate | None = None
    audio_seconds: Decimal | None = None
    duration_source: str | None = None


class ModelUnavailable(Exception):
    """Timeout, throttling or any provider error. Becomes UPSTREAM_UNAVAILABLE."""

    def __init__(self, message: str, *, reply: ModelReply | None = None):
        super().__init__(message)
        self.reply = reply


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
        self._pricing = PricingCache(self._load_prices, ttl=settings.pricing_cache_seconds)

    def _load_prices(self) -> object:
        remaining = remaining_seconds()
        limit = min(1.0, self.settings.timeout_seconds)
        if remaining is not None:
            limit = min(limit, remaining - 0.25)
        if limit <= 0:
            raise PricingUnavailable()
        try:
            response = self._http.get(
                self.settings.base_url + "models",
                headers={"Authorization": f"Bearer {self._key()}"},
                timeout=httpx.Timeout(limit),
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, CredentialUnavailable, ValueError):
            raise PricingUnavailable() from None

    def model_for_task(self, task: str) -> str:
        return self.settings.model_for_task(task)

    def generate(self, request: ModelRequest) -> ModelReply:
        model = self.model_for_task(request.task)
        if request.task == "transcription":
            return self._transcribe(request, model)
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
        rates = self._pricing.snapshot()
        response = self._post("chat/completions", json=payload)
        return self._completion_reply(response, model, rates)

    def _post(self, endpoint: str, **kwargs) -> httpx.Response:
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
                self.settings.base_url + endpoint,
                headers={"Authorization": f"Bearer {key}"},
                timeout=timeout,
                **kwargs,
            )
            response.raise_for_status()
        except (httpx.HTTPError, CredentialUnavailable) as exc:
            # Never expose response bodies, authorization headers or secret values.
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            logger.warning(
                "School model request failed: type=%s status=%s", type(exc).__name__, status
            )
            raise ModelUnavailable("The school model request failed") from None
        return response

    def _transcribe(self, request: ModelRequest, model: str) -> ModelReply:
        if not model:
            raise ModelUnavailable("SOCLAAS_AUDIO_MODEL is not configured")
        if request.audio is None:
            raise ModelUnavailable("Missing audio input")
        audio = request.audio
        extensions = {
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/mpeg": "mp3",
            "audio/webm": "webm",
            "audio/ogg": "ogg",
            "audio/mp4": "m4a",
            "audio/flac": "flac",
        }
        data = {"model": model, "response_format": "json"}
        if audio.language:
            data["language"] = audio.language
        rates = self._pricing.snapshot()
        response = self._post(
            "audio/transcriptions",
            data=data,
            files={
                "file": (f"recording.{extensions[audio.media_type]}", audio.data, audio.media_type)
            },
        )
        # The shared pipeline validates {"text": ...}; do not apply receipt prompts
        # or repeat an audio request to repair an invalid provider response.
        try:
            body = response.json()
        except ValueError:
            body = {}
        seconds = None
        duration_source = None
        if isinstance(body, dict):
            seconds = nonnegative_decimal(body.get("duration"))
            usage = body.get("usage")
            if seconds is None and isinstance(usage, dict) and usage.get("type") == "duration":
                seconds = nonnegative_decimal(usage.get("seconds"))
            if seconds is not None and seconds > 0:
                duration_source = "provider"
            else:
                seconds = None
        if seconds is None:
            seconds = wav_duration_seconds(audio.data, audio.media_type)
            if seconds is not None:
                duration_source = "wav_frames"
        return self._usage_reply(
            body,
            model,
            rates,
            text=response.text,
            audio_seconds=seconds,
            duration_source=duration_source,
            transcription=True,
        )

    def _usage_reply(
        self,
        body: object,
        model: str,
        rates: dict[str, ModelRate],
        *,
        text: str,
        audio_seconds: Decimal | None = None,
        duration_source: str | None = None,
        transcription: bool = False,
    ) -> ModelReply:
        body = body if isinstance(body, dict) else {}
        returned_model = body.get("model")
        actual_model = (
            returned_model if isinstance(returned_model, str) and returned_model else model
        )
        usage = body.get("usage")
        usage = usage if isinstance(usage, dict) else {}

        def tokens(name: str, alternative: str) -> int | None:
            value = usage.get(name, usage.get(alternative))
            return value if type(value) is int and value >= 0 else None

        input_tokens = tokens("prompt_tokens", "input_tokens")
        output_tokens = tokens("completion_tokens", "output_tokens")
        rate = rate_for_model(rates, model, actual_model)
        cost = None
        if rate:
            cost = (
                rate.audio_cost(audio_seconds)
                if transcription
                else rate.chat_cost(input_tokens, output_tokens)
            )
        return ModelReply(
            text,
            input_tokens,
            output_tokens,
            model_id=actual_model,
            estimated_cost=cost,
            pricing=rate,
            audio_seconds=audio_seconds,
            duration_source=duration_source,
        )

    def _completion_reply(
        self, response: httpx.Response, model: str, rates: dict[str, ModelRate]
    ) -> ModelReply:
        reply = None
        try:
            body = response.json()
            reply = self._usage_reply(body, model, rates, text="")
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
            return replace(reply, text=text)
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise ModelUnavailable(
                "The school model returned an unusable response", reply=reply
            ) from None

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
        if request.task == "transcription":
            return ModelReply(
                text=json.dumps(
                    {"text": "Four eggs, two hundred grams of rice, and four potatoes."}
                ),
                input_tokens=0,
                output_tokens=0,
                model_id="fake",
                estimated_cost=Decimal(0),
            )
        reply = _FAKE_ADJUST if request.task == "interpret" else _FAKE_DRAFT
        return ModelReply(
            text=json.dumps(reply),
            input_tokens=0,
            output_tokens=0,
            model_id="fake",
            estimated_cost=Decimal(0),
        )


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
