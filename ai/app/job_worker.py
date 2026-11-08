"""SQS worker entry point, plus a separate local worker: python -m app.job_worker."""

import argparse
import base64
import json
import logging
import math
import os
import time
from decimal import Decimal
from uuid import UUID

import anyio

from app import parse
from app.errors import ApiError, ErrorCode
from app.image_jobs import expire_unfinished, fail_job
from app.job_schemas import ImageJobUsage
from app.job_store import (
    MAX_ATTEMPTS,
    TERMINAL,
    AwsJobStore,
    JobStore,
    LocalJobStore,
    get_job_store,
)
from app.model_client import ModelClient, get_client
from app.pricing import COST_UNIT, cost_text
from app.runtime import RequestState, current_request
from app.schemas import ParseImageRequest

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def worker_budget(context=None) -> float:
    seconds = float(os.environ.get("AI_WORKER_TIMEOUT_SECONDS", "110"))
    if not math.isfinite(seconds) or not 0 < seconds <= 840:
        raise ValueError("AI_WORKER_TIMEOUT_SECONDS must be greater than zero and at most 840")
    if context is not None:
        seconds = min(seconds, max(0.001, context.get_remaining_time_in_millis() / 1000 - 5))
    return seconds


def attempt_usage(record, state: RequestState) -> ImageJobUsage:
    """Include prior attempts; timeout or lost attempts leave total usage unknown."""
    previous = (
        ImageJobUsage.model_validate_json(record["usage_json"])
        if record.get("usage_json")
        else None
    )
    first = record["attempts"] == 1

    def total(field):
        old = getattr(previous, field) if previous else 0 if first else None
        new = getattr(state, field)
        return old + new if old is not None and new is not None else None

    old_cost = previous.known_estimated_cost if previous else None
    known_cost = state.known_estimated_cost
    if old_cost is not None:
        known_cost = Decimal(old_cost) + (known_cost or Decimal(0))
    complete = state.estimated_cost is not None and (
        first or (previous is not None and previous.estimated_cost is not None)
    )
    return ImageJobUsage(
        model=state.model,
        input_tokens=total("input_tokens"),
        output_tokens=total("output_tokens"),
        estimated_cost=cost_text(known_cost) if complete else None,
        known_input_tokens=(previous.known_input_tokens if previous else 0)
        + state.known_input_tokens,
        known_output_tokens=(previous.known_output_tokens if previous else 0)
        + state.known_output_tokens,
        known_estimated_cost=cost_text(known_cost),
        cost_status=(
            "fake"
            if complete and state.provider == "fake"
            else "estimated"
            if complete
            else "partial"
            if known_cost is not None
            else "unknown"
        ),
        cost_unit=COST_UNIT,
    )


async def process_job(job_id: str, store: JobStore, client: ModelClient, context=None) -> bool:
    """True acknowledges the message; False requests a bounded queue retry."""
    UUID(job_id)
    now = int(time.time())
    existing = store.get(job_id)
    if not existing:
        return True
    existing = expire_unfinished(store, existing, now)
    if existing["status"] in TERMINAL or existing["expires_at"] <= now:
        return True
    budget = worker_budget(context)
    record = store.claim(job_id, now, math.ceil(budget) + 30)
    if record is None:
        # Keep an overlapping delivery until the running attempt has committed its result.
        return (store.get(job_id) or {}).get("status") in TERMINAL
    budget = min(budget, worker_budget(context))
    started = time.monotonic()
    state = RequestState(job_id, started + budget)
    token = current_request.set(state)
    try:
        with anyio.fail_after(budget):
            data = await anyio.to_thread.run_sync(store.read_image, job_id, abandon_on_cancel=True)
            body = ParseImageRequest(
                kind=record["kind"],
                media_type=record["media_type"],
                image_base64=base64.b64encode(data).decode("ascii"),
            )
            result = await parse.parse_image(body, client)
        usage = attempt_usage(record, state)
        committed = store.update(
            job_id,
            {
                "status": "completed",
                "lease_until": 0,
                "result_json": result.model_dump_json(),
                "usage_json": usage.model_dump_json(),
            },
            record["lease_token"],
        )
        if committed:
            _cleanup(store, job_id)
        return True
    except (ApiError, TimeoutError) as exc:
        if state.completed_attempts < state.attempts:
            state.input_tokens = state.output_tokens = None
            state.estimated_cost = None
        store.update(
            job_id,
            {"usage_json": attempt_usage(record, state).model_dump_json()},
            record["lease_token"],
        )
        retryable = isinstance(exc, TimeoutError) or exc.code == ErrorCode.UPSTREAM_UNAVAILABLE
        if retryable and record["attempts"] < MAX_ATTEMPTS:
            store.update(job_id, {"status": "queued", "lease_until": 0}, record["lease_token"])
            return False
        if fail_job(
            store,
            record,
            "The image could not be processed. Please try again or enter the items by hand",
            record["lease_token"],
        ):
            _cleanup(store, job_id)
        return True
    except Exception as exc:
        # Do not publish a false completion when a result write or storage read failed.
        logger.warning(
            json.dumps({"event": "image_job_error", "job_id": job_id, "type": type(exc).__name__})
        )
        raise
    finally:
        current_request.reset(token)
        logger.info(
            json.dumps(
                {
                    "event": "image_job_attempt",
                    "job_id": job_id,
                    "attempt": int(record["attempts"]),
                    "latency_ms": round((time.monotonic() - started) * 1000),
                    "model": state.model,
                    "input_tokens": state.input_tokens,
                    "output_tokens": state.output_tokens,
                    "estimated_cost": cost_text(state.estimated_cost),
                    "cost_status": state.cost_status,
                }
            )
        )


def _cleanup(store: JobStore, job_id: str) -> None:
    try:
        store.delete_image(job_id)
    except Exception:
        logger.warning("Image cleanup deferred to storage lifecycle")


def handler(event, context):
    failures = []
    for message in event.get("Records", []):
        try:
            job_id = str(UUID(json.loads(message["body"])["job_id"]))
            store = get_job_store()
            if not anyio.run(process_job, job_id, store, get_client(), context):
                if isinstance(store, AwsJobStore):
                    record = store.get(job_id) or {}
                    delay = max(30, int(record.get("lease_until", 0)) - int(time.time()) + 1)
                    store.defer(message["receiptHandle"], min(delay, 900))
                failures.append({"itemIdentifier": message["messageId"]})
        except Exception as exc:
            logger.warning(
                json.dumps({"event": "image_job_delivery_error", "type": type(exc).__name__})
            )
            failures.append({"itemIdentifier": message["messageId"]})
    return {"batchItemFailures": failures}


def main():
    parser = argparse.ArgumentParser(description="Run the separate local image-job worker")
    parser.add_argument("--once", action="store_true", help="Process pending jobs once, then exit")
    args = parser.parse_args()
    store = get_job_store()
    if not isinstance(store, LocalJobStore):
        parser.error("This local runner requires AI_JOB_BACKEND=local; AWS uses the SQS handler")
    while True:
        now = int(time.time())
        store.cleanup(now)
        for job_id in store.pending(now):
            try:
                anyio.run(process_job, job_id, store, get_client())
            except Exception as exc:
                logger.warning("Local worker attempt failed: %s", type(exc).__name__)
        if args.once:
            return
        time.sleep(2)


if __name__ == "__main__":
    main()
