"""Stock events. Role 2 owns this file.

`get_inventory_snapshot` is real. `list_events`, `undo_event` and `apply_stock_event` are
still STUBS returning mock data until the write path is built.

`apply_stock_event` and `get_inventory_snapshot` are the internal API that Role 5's
Cook and Shop services call. Their signatures and rules are agreed in app/db/README.md;
change them only by agreement.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock, mock
from app.auth import CurrentUser
from app.db import models as m
from app.schemas.common import ItemSource
from app.schemas.inventory import InventoryItem, InventoryItemCreate
from app.schemas.stock_events import (
    InventoryChange,
    StockEventList,
    StockEventType,
    StockRefType,
    UndoResult,
)
from app.services.freshness import freshness_status, use_first_date

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
    read (app/db/README.md), so the recommendation code only reads them. Batches come back
    earliest use-first date first; those with no date come last.
    """
    today, now = clock.today(), clock.now()
    rows = s.execute(
        select(m.InventoryItem, m.Ingredient)
        .outerjoin(m.Ingredient, m.Ingredient.id == m.InventoryItem.ingredient_id)
        .where(m.InventoryItem.household_id == household_id, m.InventoryItem.deleted_at.is_(None))
    ).all()
    items = [item_view(batch, ingredient, today, now) for batch, ingredient in rows]
    return sorted(items, key=_use_first_first)


def item_view(
    batch: m.InventoryItem, ingredient: m.Ingredient | None, today: date, now: datetime
) -> InventoryItem:
    """One stored batch in the shape the API returns, with its freshness worked out.

    A free-text item has no ingredient, so it is reported as category "other", tracked by
    state, and with no shelf life (so no estimated date).
    """
    shelf_life = getattr(ingredient, f"shelf_life_days_{batch.storage}", None)
    use_first = use_first_date(batch.label_date, batch.acquired_at, shelf_life)
    category = None if ingredient is None else ingredient.category
    return InventoryItem(
        id=batch.id,
        ingredient_id=batch.ingredient_id,
        display_name=batch.display_name,
        category=category or "other",
        countable=bool(ingredient and ingredient.countable),
        count=None if batch.count is None else float(batch.count),
        unit=batch.unit,
        remaining_state=batch.remaining_state,
        storage=batch.storage,
        source=batch.source,
        acquired_at=batch.acquired_at,
        label_date=batch.label_date,
        label_date_kind=batch.label_date_kind,
        est_use_first_date=use_first,
        freshness_status=freshness_status(
            today=today,
            now=now,
            remaining_state=batch.remaining_state,
            label_date=batch.label_date,
            label_date_kind=batch.label_date_kind,
            use_first=use_first,
            category=category,
            freshness_confirmed_at=batch.freshness_confirmed_at,
        ),
        freshness_confirmed_at=batch.freshness_confirmed_at,
        last_confirmed_at=batch.last_confirmed_at,
        revision=batch.revision,
    )


def _use_first_first(item: InventoryItem) -> tuple[bool, date, str, str]:
    return (
        item.est_use_first_date is None,
        item.est_use_first_date or date.max,
        item.display_name.lower(),
        str(item.id),
    )
