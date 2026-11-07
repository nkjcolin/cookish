"""Request and response shapes for /ai/* — the part of the API contract this Lambda serves.

A copy of backend/app/schemas/ai.py and the few definitions it uses from the other backend
schema files. The backend owns the shared contract and generated frontend types;
tests/test_contract.py fails if this copy drifts from docs/openapi.json.

These endpoints only return drafts. Nothing reaches the inventory until the user has
reviewed the draft and the frontend posts it to POST /api/inventory/items.
"""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --- From backend/app/schemas/common.py ---


class RequestModel(BaseModel):
    """Base for request bodies: unknown fields are rejected instead of silently dropped."""

    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Storage(StrEnum):
    PANTRY = "pantry"
    FRIDGE = "fridge"
    FREEZER = "freezer"


# --- From backend/app/schemas/identity.py ---

People = Annotated[int, Field(ge=1, le=12)]
Difficulty = Annotated[int, Field(ge=1, le=3)]


# --- From backend/app/schemas/cook.py ---


class CookTag(StrEnum):
    QUICKER = "quicker"
    EASIER = "easier"
    LESS_OIL = "less_oil"
    MORE_PROTEIN = "more_protein"
    MORE_VEGETABLES = "more_vegetables"


class CookAdjust(RequestModel):
    """Adjustments accumulate over the session; send only what the user just changed."""

    tags: list[CookTag] = Field(default_factory=list)
    people: People | None = None
    max_minutes: Annotated[int, Field(ge=5, le=240)] | None = None
    max_difficulty: Difficulty | None = None

    @model_validator(mode="after")
    def _changes_something(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("an adjustment must change at least one field")
        return self


# --- From backend/app/schemas/ai.py ---


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
