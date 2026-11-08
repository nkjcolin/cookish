from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header

from app.auth import User
from app.errors import ApiError, ErrorCode
from app.schemas.ai import (
    DraftResult,
    ImageJobResponse,
    InterpretRequest,
    InterpretResult,
    ParseImageRequest,
    ParseItemsRequest,
    TranscribeAudioRequest,
    TranscriptionResult,
)
from app.services import ai_stub

router = APIRouter(tags=["ai"])


@router.post("/parse-image")
def parse_image(user: User, body: ParseImageRequest) -> DraftResult:
    return ai_stub.parse_image(body)


@router.post("/parse-items")
def parse_items(user: User, body: ParseItemsRequest) -> DraftResult:
    return ai_stub.parse_items(body)


@router.post("/interpret")
def interpret(user: User, body: InterpretRequest) -> InterpretResult:
    return ai_stub.interpret(body)


@router.post("/transcribe-audio")
def transcribe_audio(user: User, body: TranscribeAudioRequest) -> TranscriptionResult:
    return ai_stub.transcribe_audio(body)


@router.post("/image-jobs", status_code=202)
def submit_image_job(
    user: User,
    body: ParseImageRequest,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> ImageJobResponse:
    # Contract declaration only. API Gateway sends /ai/* to the separate AI service.
    raise ApiError(ErrorCode.UPSTREAM_UNAVAILABLE, "Connect /ai to the AI service")


@router.get("/image-jobs/{job_id}")
def get_image_job(user: User, job_id: UUID) -> ImageJobResponse:
    raise ApiError(ErrorCode.UPSTREAM_UNAVAILABLE, "Connect /ai to the AI service")
