"""Versioned internal JSON snapshots; never reconstruct missing historical data."""

import json
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from app.errors import ApiError, ErrorCode
from app.reco.config import LearningConfig
from app.reco.learning import MealEvidence
from app.reco.models import Candidate, CatalogIngredient, CookSession
from app.reco.shop_models import PurchaseSpec, ShopSession
from app.schemas.cook import CookRecord, Suggestion
from app.schemas.shop import Basket


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CookState(Snapshot):
    state: CookSession
    history: tuple[Suggestion, ...]
    position: int
    selected_record_id: UUID | None


class Selection(Snapshot):
    recipe: Candidate
    response: CookRecord


class ShopState(Snapshot):
    state: ShopSession
    basket_id: UUID


class Planning(Snapshot):
    response: Basket
    ingredients: dict[UUID, CatalogIngredient]
    purchases: dict[UUID, PurchaseSpec]


class Evidence(Snapshot):
    meals: tuple[MealEvidence, ...]
    config: LearningConfig


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    kind: str
    payload: dict[str, Any]


def dump[T](kind: str, schema: type[T], value: T) -> dict:
    adapter = TypeAdapter(schema)
    # Validate again through JSON: dataclass/model instances may have been copied
    # with unchecked values, and JSONB must contain no NaN/Infinity.
    payload = adapter.dump_python(value, mode="json")
    json.dumps(payload, allow_nan=False)
    adapter.validate_python(payload, extra="forbid")
    return Envelope(schema_version=1, kind=kind, payload=payload).model_dump(mode="json")


def restore[T](kind: str, schema: type[T], value: dict | None) -> T:
    if value is None:
        raise ApiError(ErrorCode.CONFLICT, "This saved session predates persistence; start again")
    try:
        envelope = Envelope.model_validate(value)
        if envelope.kind != kind or type(value.get("schema_version")) is not int:
            raise ValueError("Wrong snapshot kind or version")
        json.dumps(envelope.payload, allow_nan=False)
        return TypeAdapter(schema).validate_python(envelope.payload, extra="forbid")
    except (ValidationError, ValueError, TypeError) as error:
        raise ApiError(ErrorCode.CONFLICT, "Saved recommendation data cannot be read") from error
