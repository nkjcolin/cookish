"""Durable image jobs; mirrored by backend/app/schemas/ai.py for OpenAPI."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.errors import ErrorBody
from app.schemas import DraftResult, ImageKind, ResponseModel


class ImageJobUsage(ResponseModel):
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: str | None = None
    known_input_tokens: int = 0
    known_output_tokens: int = 0
    known_estimated_cost: str | None = None
    cost_status: str = "unknown"
    cost_unit: str = "provider_dollars"


class ImageJobResponse(ResponseModel):
    job_id: UUID
    kind: ImageKind
    status: Literal["queued", "processing", "completed", "failed"]
    created_at: datetime
    expires_at: datetime
    result: DraftResult | None = None
    error: ErrorBody | None = None
    usage: ImageJobUsage | None = None
    poll_after_seconds: int = Field(default=2, ge=1)
