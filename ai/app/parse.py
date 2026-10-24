"""Receipt, photo or sentence in; a draft for the user to review out (SPEC B4).

Every endpoint follows the same steps: build the prompt, call the model, validate what
comes back, then enforce in code the rules a prompt cannot guarantee. Nothing is saved.
"""

import json
import logging
import time
from dataclasses import replace
from pathlib import Path

import anyio
from pydantic import BaseModel, ValidationError

from app.drafts import normalize_draft
from app.errors import ApiError, ErrorCode
from app.images import validate_image
from app.model_client import (
    Image,
    ModelClient,
    ModelReply,
    ModelRequest,
    ModelUnavailable,
    model_id_for_task,
)
from app.quantities import ExtractionResult, resolve_quantities
from app.receipts import clean_receipt
from app.runtime import current_request, remaining_seconds
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


async def parse_image(body: ParseImageRequest, client: ModelClient) -> DraftResult:
    await anyio.to_thread.run_sync(
        validate_image, body.media_type, body.image_base64, abandon_on_cancel=True
    )
    task = "receipt" if body.kind is ImageKind.RECEIPT else "photo"
    request = ModelRequest(
        task=task,
        system=_prompt(task),
        image=Image(media_type=body.media_type, base64=body.image_base64),
    )
    extracted = await _call(client, request, ExtractionResult)
    draft = resolve_quantities(extracted)
    if body.kind is ImageKind.RECEIPT:
        return clean_receipt(draft)
    return normalize_draft(draft)


async def parse_items(body: ParseItemsRequest, client: ModelClient) -> DraftResult:
    if not body.text.strip():
        raise ApiError(ErrorCode.VALIDATION, "Enter at least one grocery item")
    request = ModelRequest(
        task="items",
        system=_prompt("items"),
        text=body.text,
        source=body.source.value,
    )
    extracted = await _call(client, request, ExtractionResult)
    return normalize_draft(resolve_quantities(extracted))


async def interpret(body: InterpretRequest, client: ModelClient) -> InterpretResult:
    if not body.text.strip():
        raise ApiError(ErrorCode.VALIDATION, "Enter a cooking adjustment")
    request = ModelRequest(task="interpret", system=_prompt("interpret"), text=body.text)
    # CookAdjust forbids unknown fields, so an answer that tries to change allergens or
    # diets fails validation here: the rule is enforced in code, not by the prompt.
    return InterpretResult(adjust=await _call(client, request, CookAdjust))


def _prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


async def _call[T: BaseModel](client: ModelClient, request: ModelRequest, schema: type[T]) -> T:
    state = current_request.get()
    if state:
        state.task = request.task
        state.model = model_id_for_task(client, request.task)
        state.provider = (
            "soclaas"
            if type(client).__name__ == "SchoolModelClient"
            else "fake"
            if state.model == "fake"
            else "scripted"
        )
    for attempt in range(1, ATTEMPTS + 1):
        started = time.perf_counter()
        try:
            remaining = remaining_seconds()
            if remaining is not None and remaining <= 0:
                raise ModelUnavailable("The request deadline is exhausted")
            if state:
                state.attempts = attempt
            reply = await anyio.to_thread.run_sync(client.generate, request, abandon_on_cancel=True)
        except ModelUnavailable as exc:
            _log(client, request, attempt, started, "unavailable")
            raise ApiError(ErrorCode.UPSTREAM_UNAVAILABLE, "The model is not available") from exc
        try:
            result = schema.model_validate_json(reply.text)
            if isinstance(result, CookAdjust) and not (
                result.tags
                or any(
                    value is not None
                    for value in (result.people, result.max_minutes, result.max_difficulty)
                )
            ):
                raise ValueError("An adjustment must change a supported field")
        except (ValidationError, ValueError):
            _log(client, request, attempt, started, "invalid", reply)
            if attempt < ATTEMPTS:
                request = replace(
                    request,
                    system=request.system
                    + (
                        "\nYour previous response did not satisfy the JSON schema. "
                        "Return valid JSON using only supported fields and values, without prose."
                    ),
                )
            continue
        _log(client, request, attempt, started, "ok", reply)
        return result
    raise ApiError(ErrorCode.UPSTREAM_UNAVAILABLE, "The model returned an unusable answer")


def _log(
    client: ModelClient,
    request: ModelRequest,
    attempt: int,
    started: float,
    outcome: str,
    reply: ModelReply | None = None,
) -> None:
    # One JSON line per model call; Role 3 builds the cost model from these (SPEC A6).
    state = current_request.get()
    if state:
        for field in ("input_tokens", "output_tokens"):
            value = getattr(reply, field) if reply else None
            total = 0 if attempt == 1 else getattr(state, field)
            setattr(
                state, field, total + value if total is not None and value is not None else None
            )
    logger.info(
        json.dumps(
            {
                "event": "model_call",
                "request_id": state.request_id if state else None,
                "task": request.task,
                "model_id": (
                    reply.model_id
                    if reply and reply.model_id
                    else model_id_for_task(client, request.task)
                ),
                "attempt": attempt,
                "outcome": outcome,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "input_tokens": reply.input_tokens if reply else None,
                "output_tokens": reply.output_tokens if reply else None,
            }
        )
    )
