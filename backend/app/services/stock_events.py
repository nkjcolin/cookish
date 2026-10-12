"""Stock events. STUB — Role 2 replaces the function bodies.

`apply_stock_event` and `get_inventory_snapshot` are the internal API that Role 5's
Cook and Shop services call. Their signatures are part of the agreement between roles.
"""

from typing import Any
from uuid import UUID

from app import mock
from app.auth import CurrentUser
from app.schemas.stock_events import (
    StockEvent,
    StockEventList,
    StockEventType,
    StockRefType,
    UndoResult,
)


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
    household_id: UUID,
    user_id: UUID,
    event_type: StockEventType,
    lines: list[dict[str, Any]],
    idempotency_key: UUID,
    ref_type: StockRefType = StockRefType.MANUAL,
    ref_id: UUID | None = None,
) -> StockEvent:
    """Apply one inventory change in a single transaction.

    A repeated `idempotency_key` returns the original event without changing anything.
    The exact shape of `lines` is Role 2's to define.
    """
    raise NotImplementedError("Role 2")


def get_inventory_snapshot(household_id: UUID) -> Any:
    """Everything the recommendation functions need to read, in one call."""
    raise NotImplementedError("Role 2")
