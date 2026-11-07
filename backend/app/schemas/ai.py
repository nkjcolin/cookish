"""Assisted entry, served by the `ai` Lambda under /ai (SPEC A3).

These endpoints only return drafts. Nothing reaches the inventory until the user has
reviewed the draft and the frontend posts it to POST /api/inventory/items.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from app.schemas.common import RequestModel, ResponseModel, Storage
from app.schemas.cook import CookAdjust


class ImageKind(StrEnum):
    RECEIPT = "receipt"
    PHOTO = "photo"


class TextSource(StrEnum):
    TYPED = "typed"
    VOICE = "voice"


class ParseImageRequest(RequestModel):
    kind: ImageKind
    media_type: Literal["image/jpeg", "image/png", "image/webp"] = "image/jpeg"
    image_base64: Annotated[str, Field(min_length=1)] = Field(
        description="Compressed in the browser first; Lambda rejects requests over 6 MB."
    )


class ParseItemsRequest(RequestModel):
    source: TextSource = TextSource.TYPED
    text: Annotated[str, Field(min_length=1, max_length=2000)]


class DraftItem(ResponseModel):
    raw_text: str | None = Field(description="What was read or heard, before normalisation.")
    display_name: str
    count: float | None = Field(description="null = not stated; never guessed.")
    unit: str | None
    storage: Storage | None
    confidence: float = Field(ge=0, le=1)


class DraftResult(ResponseModel):
    items: list[DraftItem]


class InterpretRequest(RequestModel):
    text: Annotated[str, Field(min_length=1, max_length=500)]


class InterpretResult(ResponseModel):
    """Optional feature. The patch can only touch soft conditions (SPEC B4)."""

    adjust: CookAdjust


class TranscribeAudioRequest(RequestModel):
    media_type: Literal[
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/webm",
        "audio/ogg",
        "audio/mp4",
        "audio/flac",
    ]
    audio_base64: Annotated[str, Field(min_length=1)]
    language: Annotated[str, Field(pattern=r"^[a-z]{2}$")] | None = "en"


class TranscriptionResult(ResponseModel):
    text: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def _nonempty_transcript(self) -> Self:
        if not self.text.strip():
            raise ValueError("The transcript must contain text")
        return self
