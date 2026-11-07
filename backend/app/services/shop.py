"""Shop services backed by the pure planner and transactional SQL workflow."""

from uuid import UUID

from app.auth import CurrentUser
from app.schemas.shop import (
    Basket,
    BasketConfirm,
    BasketConfirmResult,
    ShopAdjust,
    ShopSessionCreate,
)
from app.services.recommendation_sql import recommendation_workflow


def start_session(user: CurrentUser, body: ShopSessionCreate) -> Basket:
    return recommendation_workflow(user).start_shop(user, body)


def adjust(user: CurrentUser, session_id: UUID, body: ShopAdjust) -> Basket:
    return recommendation_workflow(user).adjust_shop(user, session_id, body)


def confirm_basket(
    user: CurrentUser, basket_id: UUID, body: BasketConfirm, idempotency_key: UUID
) -> BasketConfirmResult:
    """Add what was actually bought through `apply_stock_event`."""
    return recommendation_workflow(user).confirm_shop(user, basket_id, body, idempotency_key)
