"""Stock events: every inventory change, each of them reversible (SPEC A6)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.common import RemainingState, ResponseModel
from app.schemas.inventory import InventoryItem


class StockEventType(StrEnum):
    PURCHASE = "purchase"
    CONSUME = "consume"
    ADJUST = "adjust"
    UNDO = "undo"


class StockRefType(StrEnum):
    COOK_SESSION = "cook_session"
    BASKET = "basket"
    MANUAL = "manual"


class ItemSnapshot(ResponseModel):
    count: float | None
    unit: str | None
    remaining_state: RemainingState


class StockEventLine(ResponseModel):
    inventory_item_id: UUID
    display_name: str
    before: ItemSnapshot | None = Field(description="null when the event created the item.")
    after: ItemSnapshot | None = Field(description="null when the event removed the item.")


class StockEvent(ResponseModel):
    id: UUID
    type: StockEventType
    ref_type: StockRefType
    ref_id: UUID | None
    user_id: UUID
    created_at: datetime
    lines: list[StockEventLine]
    reverts_event_id: UUID | None
    can_undo: bool = Field(description="false for undo events and events already undone.")


class StockEventList(ResponseModel):
    events: list[StockEvent]


class InventoryChange(ResponseModel):
    """Returned by every endpoint that changes inventory; `event.id` is what Undo needs."""

    event: StockEvent
    items: list[InventoryItem] = Field(description="Current state of every item touched.")


class UndoConflict(ResponseModel):
    inventory_item_id: UUID
    display_name: str
    reason: str


class UndoResult(InventoryChange):
    conflicts: list[UndoConflict] = Field(
        description="Items changed since the original event; these were left as they are."
    )
