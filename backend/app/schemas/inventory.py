"""Inventory: one InventoryItem is one batch of one ingredient (SPEC A6).

Null always means "unknown", never zero. On PATCH, a field that is absent is left
unchanged, while a field sent as null is cleared to unknown.
"""

from datetime import date, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import (
    FreshnessStatus,
    IngredientCategory,
    ItemSource,
    LabelDateKind,
    RemainingState,
    RequestModel,
    ResponseModel,
    Storage,
)

Count = Annotated[float, Field(ge=0)]
DisplayName = Annotated[str, Field(min_length=1, max_length=80)]
Unit = Annotated[str, Field(min_length=1, max_length=16)]


class InventoryItem(ResponseModel):
    id: UUID
    ingredient_id: UUID | None = Field(description="null for a free-text item.")
    display_name: str
    category: IngredientCategory
    countable: bool = Field(description="true: tracked by count. false: tracked by state.")
    count: float | None
    unit: str | None
    remaining_state: RemainingState
    storage: Storage
    source: ItemSource
    acquired_at: date
    label_date: date | None = Field(description="Date printed on the package.")
    label_date_kind: LabelDateKind | None
    est_use_first_date: date | None = Field(description="Our estimate; never a safety claim.")
    freshness_status: FreshnessStatus
    freshness_confirmed_at: datetime | None
    last_confirmed_at: datetime
    revision: int


class InventoryGroup(ResponseModel):
    """All batches of one ingredient, earliest use-first date first."""

    ingredient_id: UUID | None
    name: str
    category: IngredientCategory
    countable: bool
    batches: list[InventoryItem]


class Inventory(ResponseModel):
    groups: list[InventoryGroup]


class _LabelDate(RequestModel):
    label_date: date | None = None
    label_date_kind: LabelDateKind | None = None

    @model_validator(mode="after")
    def _label_date_has_kind(self) -> Self:
        if self.label_date is not None and self.label_date_kind is None:
            raise ValueError("label_date_kind is required when label_date is set")
        return self


class InventoryItemCreate(_LabelDate):
    ingredient_id: UUID | None = None
    display_name: DisplayName | None = Field(
        default=None, description="Required for a free-text item; otherwise the catalogue name."
    )
    count: Count | None = None
    unit: Unit | None = None
    remaining_state: RemainingState = RemainingState.ENOUGH
    storage: Storage | None = Field(default=None, description="Defaults to the ingredient's.")
    acquired_at: date | None = Field(default=None, description="Defaults to today.")

    @model_validator(mode="after")
    def _is_identified(self) -> Self:
        if self.ingredient_id is None and self.display_name is None:
            raise ValueError("either ingredient_id or display_name is required")
        return self


class InventoryItemsCreate(RequestModel):
    source: ItemSource = ItemSource.MANUAL
    items: Annotated[list[InventoryItemCreate], Field(min_length=1, max_length=100)]


class InventoryItemUpdate(_LabelDate):
    revision: int = Field(description="The revision the client last saw; a mismatch returns 409.")
    display_name: DisplayName | None = None
    count: Count | None = None
    unit: Unit | None = None
    remaining_state: RemainingState | None = None
    storage: Storage | None = None
    freshness_confirmed: bool | None = Field(
        default=None, description='true records the "It\'s fine" answer to a freshness check.'
    )
