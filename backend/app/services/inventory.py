"""Inventory reads and edits. Role 2 owns this file.

`list_inventory` is real. `add_items`, `update_item` and `delete_item` are still STUBS
returning mock data until the write path is built.

Every change must go through `stock_events.apply_stock_event`, so that it is atomic,
idempotent and reversible (SPEC A6).

`est_use_first_date` and `freshness_status` are computed when items are read, from
the label date, the purchase date and the ingredient's shelf life (services/freshness.py).
"""

from uuid import UUID

from app import clock, mock
from app.auth import CurrentUser
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.schemas.inventory import (
    Inventory,
    InventoryGroup,
    InventoryItem,
    InventoryItemsCreate,
    InventoryItemUpdate,
)
from app.schemas.stock_events import InventoryChange, StockEventType
from app.services.stock_events import get_inventory_snapshot


def _find(item_id: UUID) -> InventoryItem:
    found = mock.inventory_items().get(str(item_id))
    if found is None:
        raise ApiError(ErrorCode.NOT_FOUND, "Inventory item not found")
    return found


def list_inventory(user: CurrentUser) -> Inventory:
    """The household's kitchen: one group per ingredient, each holding its batches.

    Batches within a group come earliest use-first date first. Groups are in name order.
    Free-text items have no ingredient, so they are grouped by name instead.
    """
    with transaction() as s:
        items = get_inventory_snapshot(s, user.household_id)  # already in use-first order

    groups: dict[object, InventoryGroup] = {}
    for item in items:
        key = item.ingredient_id or ("free text", item.display_name.strip().lower())
        if key in groups:
            groups[key].batches.append(item)
        else:
            groups[key] = InventoryGroup(
                ingredient_id=item.ingredient_id,
                name=item.display_name,
                category=item.category,
                countable=item.countable,
                batches=[item],
            )
    return Inventory(groups=sorted(groups.values(), key=lambda group: group.name.lower()))


def add_items(
    user: CurrentUser, body: InventoryItemsCreate, idempotency_key: UUID
) -> InventoryChange:
    items = [mock.item("tomato").model_copy(update={"source": body.source})] * len(body.items)
    return InventoryChange(
        event=mock.stock_event(StockEventType.PURCHASE, items, created=True), items=items
    )


def update_item(
    user: CurrentUser, item_id: UUID, body: InventoryItemUpdate, idempotency_key: UUID
) -> InventoryChange:
    current = _find(item_id)
    if body.revision != current.revision:
        raise ApiError(
            ErrorCode.STALE_REVISION,
            "This item was changed elsewhere",
            {"current_revision": current.revision},
        )
    changes = body.model_dump(exclude_unset=True, exclude={"revision", "freshness_confirmed"})
    if body.freshness_confirmed:
        changes["freshness_confirmed_at"] = clock.now()
    updated = current.model_copy(update={**changes, "revision": current.revision + 1})
    return InventoryChange(
        event=mock.stock_event(StockEventType.ADJUST, [updated]), items=[updated]
    )


def delete_item(
    user: CurrentUser, item_id: UUID, revision: int, idempotency_key: UUID
) -> InventoryChange:
    current = _find(item_id)
    return InventoryChange(
        event=mock.stock_event(StockEventType.ADJUST, [current], removed=True), items=[]
    )
