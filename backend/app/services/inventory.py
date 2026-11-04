"""Inventory reads and edits. Role 2 owns this file.

Every change goes through `stock_events.apply_stock_event`, so that it is atomic, idempotent
and reversible (SPEC A6). This file only turns a request into stock-event lines.

`est_use_first_date` and `freshness_status` are computed when items are read, from
the label date, the purchase date and the ingredient's shelf life (services/freshness.py).
"""

from uuid import UUID

from app import clock
from app.auth import CurrentUser
from app.db.session import transaction
from app.schemas.inventory import (
    Inventory,
    InventoryGroup,
    InventoryItemsCreate,
    InventoryItemUpdate,
)
from app.schemas.stock_events import InventoryChange, StockEventType
from app.services.stock_events import (
    ChangeBatch,
    NewBatch,
    apply_stock_event,
    get_inventory_snapshot,
)


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
    lines = [NewBatch(item=item, source=body.source) for item in body.items]
    with transaction() as s:
        return apply_stock_event(s, user, StockEventType.PURCHASE, lines, idempotency_key)


def update_item(
    user: CurrentUser, item_id: UUID, body: InventoryItemUpdate, idempotency_key: UUID
) -> InventoryChange:
    # Only the fields the client sent: an absent field is left alone, a null one is cleared.
    changes = body.model_dump(exclude_unset=True, exclude={"revision", "freshness_confirmed"})
    if body.freshness_confirmed:
        changes["freshness_confirmed_at"] = clock.now()
    line = ChangeBatch(item_id=item_id, revision=body.revision, changes=changes)
    with transaction() as s:
        return apply_stock_event(s, user, StockEventType.ADJUST, [line], idempotency_key)


def delete_item(
    user: CurrentUser, item_id: UUID, revision: int, idempotency_key: UUID
) -> InventoryChange:
    line = ChangeBatch(item_id=item_id, revision=revision, changes={}, remove=True)
    with transaction() as s:
        return apply_stock_event(s, user, StockEventType.ADJUST, [line], idempotency_key)
