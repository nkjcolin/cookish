"""Shop sessions and baskets. STUB — Role 5 replaces the function bodies."""

from uuid import UUID

from app import mock
from app.auth import CurrentUser
from app.schemas.shop import (
    Basket,
    BasketConfirm,
    BasketConfirmResult,
    ShopAdjust,
    ShopSessionCreate,
)
from app.schemas.stock_events import StockEventType, StockRefType


def start_session(user: CurrentUser, body: ShopSessionCreate) -> Basket:
    prefs = mock.preferences()
    return mock.basket(
        people=body.people or prefs.last_shop_people, meals=body.meals or prefs.last_shop_meals
    )


def adjust(user: CurrentUser, session_id: UUID, body: ShopAdjust) -> Basket:
    return mock.basket(people=body.people or 2, meals=body.meals or 3, tags=body.tags)


def confirm_basket(
    user: CurrentUser, basket_id: UUID, body: BasketConfirm, idempotency_key: UUID
) -> BasketConfirmResult:
    """Add what was actually bought through `apply_stock_event`."""
    items = [mock.item("cabbage"), mock.item("tofu")]
    event = mock.stock_event(
        StockEventType.PURCHASE,
        items,
        ref_type=StockRefType.BASKET,
        ref_id=basket_id,
        created=True,
    )
    return BasketConfirmResult(event=event, items=items, basket_id=basket_id)
