from fastapi import APIRouter

from app.auth import User
from app.schemas.ai import (
    DraftResult,
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
