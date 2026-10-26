"""Request-wide deadlines and content-free correlation/usage logs."""

import json
import logging
import math
import os
import time
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

import anyio
from starlette.responses import JSONResponse

from app.errors import ErrorBody, ErrorCode, ErrorResponse
from app.pricing import COST_UNIT, cost_text

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class RequestState:
    request_id: str
    deadline: float
    task: str = "unknown"
    model: str | None = None
    provider: str | None = None
    attempts: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    completed_attempts: int = 0
    known_input_tokens: int = 0
    known_output_tokens: int = 0
    estimated_cost: Decimal | None = None
    known_estimated_cost: Decimal | None = None
    priced_attempts: int = 0
    cost_status: str = "unknown"
    pricing_fetched_at: str | None = None


current_request: ContextVar[RequestState | None] = ContextVar("ai_request", default=None)


def remaining_seconds() -> float | None:
    state = current_request.get()
    return max(0.0, state.deadline - time.monotonic()) if state else None


def request_budget(scope: dict) -> float:
    value = os.environ.get("AI_REQUEST_TIMEOUT_SECONDS", "27").strip().strip("\"'")
    seconds = float(value)
    if not math.isfinite(seconds) or not 0 < seconds <= 120:
        raise ValueError("Invalid AI_REQUEST_TIMEOUT_SECONDS")
    context = scope.get("aws.context")
    if context is not None:
        seconds = min(seconds, 27.0, max(0.001, context.get_remaining_time_in_millis() / 1000 - 1))
    return seconds


def _request_id(scope: dict) -> str:
    # Accept UUID correlation only; never reflect arbitrary client strings in logs.
    candidate = dict(scope.get("headers", [])).get(b"x-request-id", b"")
    try:
        return str(UUID(candidate.decode("ascii")))
    except (ValueError, UnicodeError):
        return str(uuid4())


def _unavailable(message: str) -> JSONResponse:
    return JSONResponse(
        ErrorResponse(
            error=ErrorBody(code=ErrorCode.UPSTREAM_UNAVAILABLE, message=message)
        ).model_dump(mode="json"),
        status_code=503,
    )


class RequestMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = time.monotonic()
        request_id = _request_id(scope)
        try:
            budget = request_budget(scope)
        except (ValueError, TypeError):
            logger.error("Invalid AI_REQUEST_TIMEOUT_SECONDS configuration")
            response = _unavailable("The AI request deadline is not configured correctly")
            response.headers["X-Request-ID"] = request_id
            return await response(scope, receive, send)
        state = RequestState(request_id, started + budget)
        token = current_request.set(state)
        status = 500
        outcome = "complete"
        messages = []

        async def buffered_send(message):
            # All routes return finite JSON/HTML, not streaming responses. Buffer
            # until completion so a deadline cannot leave half of a 200 response.
            messages.append(message)

        async def correlated_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                headers.append((b"x-ai-attempts", str(state.attempts).encode("ascii")))
                for name, value in (
                    ("model", state.model),
                    ("provider", state.provider),
                    ("input-tokens", state.input_tokens if state.attempts else None),
                    ("output-tokens", state.output_tokens if state.attempts else None),
                    ("estimated-cost", cost_text(state.estimated_cost)),
                    ("known-estimated-cost", cost_text(state.known_estimated_cost)),
                    ("cost-status", state.cost_status if state.attempts else None),
                    ("cost-unit", COST_UNIT if state.attempts else None),
                    ("pricing-fetched-at", state.pricing_fetched_at),
                ):
                    if value is not None:
                        headers.append((f"x-ai-{name}".encode(), str(value).encode("utf-8")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            try:
                with anyio.fail_after(budget):
                    await self.app(scope, receive, buffered_send)
            except TimeoutError:
                outcome = "deadline"
                if state.completed_attempts < state.attempts:
                    state.input_tokens = state.output_tokens = None
                    state.estimated_cost = None
                    state.cost_status = (
                        "partial" if state.known_estimated_cost is not None else "unknown"
                    )
                messages.clear()
                await _unavailable("The AI request exceeded its deadline")(
                    scope, receive, buffered_send
                )
            for message in messages:
                await correlated_send(message)
        finally:
            logger.info(
                json.dumps(
                    {
                        "event": "ai_request",
                        "request_id": request_id,
                        "task": state.task,
                        "model_id": state.model,
                        "provider": state.provider,
                        "status": status,
                        "outcome": outcome,
                        "attempts": state.attempts,
                        "latency_ms": round((time.monotonic() - started) * 1000),
                        "input_tokens": state.input_tokens if state.attempts else None,
                        "output_tokens": state.output_tokens if state.attempts else None,
                        "known_input_tokens": state.known_input_tokens,
                        "known_output_tokens": state.known_output_tokens,
                        "estimated_cost": cost_text(state.estimated_cost),
                        "known_estimated_cost": cost_text(state.known_estimated_cost),
                        "cost_status": state.cost_status,
                        "cost_unit": COST_UNIT,
                        "priced_attempts": state.priced_attempts,
                    }
                )
            )
            current_request.reset(token)
