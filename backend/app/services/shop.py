"""Shop sessions and baskets backed by the transactional SQL repository."""

from uuid import UUID

from app.auth import CurrentUser
from app.schemas.shop import (
    Basket,
    BasketConfirm,
    BasketConfirmResult,
    ShopAdjust,
    ShopSessionCreate,
)
from app.services.recommendation_sql import recommendation_uow
from app.services.recommendation_workflow import RecommendationWorkflow

workflow = RecommendationWorkflow(recommendation_uow)


def start_session(user: CurrentUser, body: ShopSessionCreate) -> Basket:
    return workflow.start_shop(user, body)


def adjust(user: CurrentUser, session_id: UUID, body: ShopAdjust) -> Basket:
    return workflow.adjust_shop(user, session_id, body)


def confirm_basket(
    user: CurrentUser, basket_id: UUID, body: BasketConfirm, idempotency_key: UUID
) -> BasketConfirmResult:
    return workflow.confirm_shop(user, basket_id, body, idempotency_key)
