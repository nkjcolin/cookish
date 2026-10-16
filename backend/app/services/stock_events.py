"""Stock events. STUB — Role 2 replaces the function bodies.

`apply_stock_event` and `get_inventory_snapshot` are the internal API that Role 5's
Cook and Shop services call. Their signatures and rules are agreed in app/db/README.md;
change them only by agreement.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app import mock
from app.auth import CurrentUser
from app.schemas.common import ItemSource
from app.schemas.inventory import InventoryItem, InventoryItemCreate
from app.schemas.stock_events import (
    InventoryChange,
    StockEventList,
    StockEventType,
    StockRefType,
    UndoResult,
)

# The only fields a ChangeBatch may set.
CHANGEABLE_FIELDS = frozenset(
    {
        "count",
        "unit",
        "remaining_state",
        "storage",
        "label_date",
        "label_date_kind",
        "display_name",
        "freshness_confirmed_at",
    }
)


@dataclass(frozen=True)
class NewBatch:
    """Add a new batch: a purchase, or an item added by hand."""

    item: InventoryItemCreate
    source: ItemSource


@dataclass(frozen=True)
class ChangeBatch:
    """Change or remove an existing batch."""

    item_id: UUID
    # The revision the user last saw; a mismatch raises STALE_REVISION. None when the
    # change comes from the system rather than from a user's edit.
    revision: int | None
    changes: dict[str, Any]  # keys from CHANGEABLE_FIELDS only; None means "unknown"
    remove: bool = False


StockLine = NewBatch | ChangeBatch


def list_events(user: CurrentUser, limit: int) -> StockEventList:
    items = [mock.item("egg-new"), mock.item("tomato")]
    events = [
        mock.stock_event(StockEventType.CONSUME, items, ref_type=StockRefType.COOK_SESSION),
        mock.stock_event(StockEventType.PURCHASE, items, created=True),
    ]
    return StockEventList(events=events[:limit])


def undo_event(user: CurrentUser, event_id: UUID, idempotency_key: UUID) -> UndoResult:
    """Restore each line's `before` snapshot; report lines changed since as conflicts."""
    items = [mock.item("egg-new"), mock.item("tomato")]
    return UndoResult(event=mock.stock_event(StockEventType.UNDO, items), items=items, conflicts=[])


def apply_stock_event(
    s: Session,
    user: CurrentUser,
    event_type: StockEventType,
    lines: list[StockLine],
    idempotency_key: UUID,
    ref_type: StockRefType = StockRefType.MANUAL,
    ref_id: UUID | None = None,
) -> InventoryChange:
    """Apply one inventory change as one stock event, inside the caller's transaction.

    Writes the event, a before and after snapshot per line, updates the items and bumps
    their revision. A repeated `idempotency_key` returns the original change and changes
    nothing. Every item must belong to `user.household_id`, or NOT_FOUND is raised.
    """
    items = [mock.item("tomato")]
    event = mock.stock_event(
        event_type,
        items,
        ref_type=ref_type,
        ref_id=ref_id,
        created=any(isinstance(line, NewBatch) for line in lines),
    )
    return InventoryChange(event=event, items=items)


def get_inventory_snapshot(s: Session, household_id: UUID) -> list[InventoryItem]:
    """Every batch the household has, removed ones excluded.

    Each batch already carries `est_use_first_date` and `freshness_status`, computed on
    read (app/db/README.md), so the recommendation code only reads them.
    """
    return list(mock.inventory_items().values())
