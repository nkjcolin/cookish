"""Receipt, photo or sentence in; a draft for the user to review out (SPEC B4).

Every endpoint follows the same steps: build the prompt, call the model, validate what
comes back, then enforce in code the rules a prompt cannot guarantee. Nothing is saved.
"""

import json
import logging
import time
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.errors import ApiError, ErrorCode
from app.matching import get_catalogue
from app.model_client import Image, ModelClient, ModelReply, ModelRequest, ModelUnavailable
from app.schemas import (
    CookAdjust,
    DraftResult,
    ImageKind,
    InterpretRequest,
    InterpretResult,
    ParseImageRequest,
    ParseItemsRequest,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

PROMPTS = Path(__file__).parent / "prompts"
ATTEMPTS = 2  # one retry when the model's answer does not validate


def parse_image(body: ParseImageRequest, client: ModelClient) -> DraftResult:
    task = "receipt" if body.kind is ImageKind.RECEIPT else "photo"
    request = ModelRequest(
        task=task,
        system=_prompt(task, with_catalogue=True),
        image=Image(media_type=body.media_type, base64=body.image_base64),
    )
    return _clean(_call(client, request, DraftResult))


def parse_items(body: ParseItemsRequest, client: ModelClient) -> DraftResult:
    request = ModelRequest(
        task="items", system=_prompt("items", with_catalogue=True), text=body.text
    )
    return _clean(_call(client, request, DraftResult))


def interpret(body: InterpretRequest, client: ModelClient) -> InterpretResult:
    request = ModelRequest(task="interpret", system=_prompt("interpret"), text=body.text)
    # CookAdjust forbids unknown fields, so an answer that tries to change allergens or
    # diets fails validation here: the rule is enforced in code, not by the prompt.
    return InterpretResult(adjust=_call(client, request, CookAdjust))


def _prompt(name: str, *, with_catalogue: bool = False) -> str:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    if with_catalogue:
        text = text.replace("{catalogue}", get_catalogue().prompt_lines())
    return text


def _call[T: BaseModel](client: ModelClient, request: ModelRequest, schema: type[T]) -> T:
    for attempt in range(1, ATTEMPTS + 1):
        started = time.perf_counter()
        try:
            reply = client.generate(request)
        except ModelUnavailable as exc:
            _log(client, request, attempt, started, "unavailable")
            raise ApiError(ErrorCode.UPSTREAM_UNAVAILABLE, "The model is not available") from exc
        try:
            result = schema.model_validate_json(reply.text)
        except ValidationError:
            _log(client, request, attempt, started, "invalid", reply)
            continue
        _log(client, request, attempt, started, "ok", reply)
        return result
    raise ApiError(ErrorCode.UPSTREAM_UNAVAILABLE, "The model returned an unusable answer")


def _clean(draft: DraftResult) -> DraftResult:
    """Rules that must hold whatever the model answered."""
    catalogue = get_catalogue()
    items = [
        item.model_copy(
            update={"ingredient_id": catalogue.resolve(item.ingredient_id, item.display_name)}
        )
        for item in draft.items
    ]
    return DraftResult(items=items)


def _log(
    client: ModelClient,
    request: ModelRequest,
    attempt: int,
    started: float,
    outcome: str,
    reply: ModelReply | None = None,
) -> None:
    # One JSON line per model call; Role 3 builds the cost model from these (SPEC A6).
    logger.info(
        json.dumps(
            {
                "event": "model_call",
                "task": request.task,
                "model_id": client.model_id,
                "attempt": attempt,
                "outcome": outcome,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "input_tokens": reply.input_tokens if reply else None,
                "output_tokens": reply.output_tokens if reply else None,
            }
        )
    )
