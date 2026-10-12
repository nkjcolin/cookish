from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.auth import User
from app.deps import IdempotencyKey
from app.schemas.inventory import Inventory, InventoryItemsCreate, InventoryItemUpdate
from app.schemas.stock_events import InventoryChange, StockEventList, UndoResult
from app.services import inventory, stock_events

router = APIRouter(tags=["inventory"])


@router.get("/inventory")
def list_inventory(user: User) -> Inventory:
    return inventory.list_inventory(user)


@router.post("/inventory/items", status_code=201)
def add_inventory_items(
    user: User, body: InventoryItemsCreate, idempotency_key: IdempotencyKey
) -> InventoryChange:
    return inventory.add_items(user, body, idempotency_key)


@router.patch("/inventory/items/{item_id}")
def update_inventory_item(
    user: User, item_id: UUID, body: InventoryItemUpdate, idempotency_key: IdempotencyKey
) -> InventoryChange:
    return inventory.update_item(user, item_id, body, idempotency_key)


@router.delete("/inventory/items/{item_id}")
def delete_inventory_item(
    user: User,
    item_id: UUID,
    revision: Annotated[int, Query(description="The revision the client last saw.")],
    idempotency_key: IdempotencyKey,
) -> InventoryChange:
    return inventory.delete_item(user, item_id, revision, idempotency_key)


@router.get("/stock-events")
def list_stock_events(
    user: User, limit: Annotated[int, Query(ge=1, le=100)] = 20
) -> StockEventList:
    return stock_events.list_events(user, limit)


@router.post("/stock-events/{event_id}/undo")
def undo_stock_event(user: User, event_id: UUID, idempotency_key: IdempotencyKey) -> UndoResult:
    return stock_events.undo_event(user, event_id, idempotency_key)
