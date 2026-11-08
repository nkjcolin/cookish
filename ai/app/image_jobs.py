"""Short HTTP operations for durable image jobs, with no provider calls."""

import base64
import hashlib
import json
import logging
import os
import time
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import Request

from app.errors import ApiError, ErrorBody, ErrorCode
from app.images import validate_image
from app.job_schemas import ImageJobResponse, ImageJobUsage
from app.job_store import MAX_ATTEMPTS, TERMINAL, JobStore, Record
from app.schemas import DraftResult, ParseImageRequest

logger = logging.getLogger(__name__)
RETENTION_SECONDS = 86400
WORK_WINDOW_SECONDS = 900


def job_owner(request: Request) -> str:
    """Trust API Gateway's verified claims, never an owner supplied by the client."""
    event = request.scope.get("aws.event")
    if event is None and not os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return "local-developer"
    claims = (
        (event or {})
        .get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    try:
        return str(UUID(claims["sub"]))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ApiError(ErrorCode.UNAUTHENTICATED, "Sign in to continue") from None


def response(record: Record) -> ImageJobResponse:
    return ImageJobResponse(
        job_id=record["job_id"],
        kind=record["kind"],
        status=record["status"],
        created_at=datetime.fromtimestamp(int(record["created_at"]), UTC),
        expires_at=datetime.fromtimestamp(int(record["expires_at"]), UTC),
        result=(
            DraftResult.model_validate_json(record["result_json"])
            if record.get("result_json")
            else None
        ),
        error=(
            ErrorBody.model_validate_json(record["error_json"])
            if record.get("error_json")
            else None
        ),
        usage=(
            ImageJobUsage.model_validate_json(record["usage_json"])
            if record.get("usage_json")
            else None
        ),
    )


def fail_job(store: JobStore, record: Record, message: str, lease_token: str | None = None) -> bool:
    return store.update(
        record["job_id"],
        {
            "status": "failed",
            "lease_until": 0,
            "error_json": ErrorBody(
                code=ErrorCode.UPSTREAM_UNAVAILABLE, message=message
            ).model_dump_json(),
        },
        lease_token,
    )


def expire_unfinished(store: JobStore, record: Record, now: int) -> Record:
    if record["status"] not in TERMINAL and (
        record["work_deadline"] <= now
        or (record["attempts"] >= MAX_ATTEMPTS and record["lease_until"] <= now)
    ):
        if fail_job(
            store, record, "Image processing could not finish. Please submit the image again"
        ):
            try:
                store.delete_image(record["job_id"])
            except Exception:
                logger.warning("Image cleanup deferred to storage lifecycle")
        return store.get(record["job_id"]) or record
    return record


def submit_image_job(
    body: ParseImageRequest, owner: str, key: UUID, store: JobStore
) -> ImageJobResponse:
    validate_image(body.media_type, body.image_base64)
    data = base64.b64decode(body.image_base64, validate=True)
    fingerprint = hashlib.sha256(
        body.kind.value.encode() + b"\0" + body.media_type.encode() + b"\0" + data
    ).hexdigest()
    now = int(time.time())
    record = store.create(
        {
            "job_id": str(uuid5(NAMESPACE_URL, f"cookish-image:{owner}:{key}")),
            "owner": owner,
            "payload_hash": fingerprint,
            "kind": body.kind.value,
            "media_type": body.media_type,
            "status": "queued",
            "created_at": now,
            "expires_at": now + RETENTION_SECONDS,
            "work_deadline": now + WORK_WINDOW_SECONDS,
            "attempts": 0,
            "lease_until": 0,
            "lease_token": "",
        }
    )
    if record["payload_hash"] != fingerprint:
        raise ApiError(ErrorCode.CONFLICT, "Use a new Idempotency-Key for a different image")
    if record["expires_at"] <= now:
        raise ApiError(ErrorCode.NOT_FOUND, "This image job has expired; submit it with a new key")
    record = expire_unfinished(store, record, now)
    if record["status"] == "queued":
        # A retry with the same key repairs a partially completed upload/queue submission.
        store.put_image(record["job_id"], data, body.media_type)
        store.enqueue(record["job_id"])
    return response(record)


def read_image_job(job_id: UUID, owner: str, store: JobStore) -> ImageJobResponse:
    record = store.get(str(job_id))
    now = int(time.time())
    if not record or record["owner"] != owner or record["expires_at"] <= now:
        raise ApiError(ErrorCode.NOT_FOUND, "Image job not found or expired")
    return response(expire_unfinished(store, record, now))


def storage_unavailable(exc: Exception) -> ApiError:
    # Content-free: SDK exceptions can contain resource names or request details.
    logger.warning(json.dumps({"event": "image_job_storage_error", "type": type(exc).__name__}))
    return ApiError(ErrorCode.UPSTREAM_UNAVAILABLE, "Image processing is temporarily unavailable")
