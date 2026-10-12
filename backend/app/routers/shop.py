from uuid import UUID

from fastapi import APIRouter

from app.auth import User
from app.deps import IdempotencyKey
from app.schemas.shop import (
    Basket,
    BasketConfirm,
    BasketConfirmResult,
    ShopAdjust,
    ShopSessionCreate,
)
from app.services import shop

router = APIRouter(tags=["shop"])


@router.post("/shop/sessions", status_code=201)
def start_shop_session(user: User, body: ShopSessionCreate) -> Basket:
    return shop.start_session(user, body)


@router.post("/shop/sessions/{session_id}/adjust")
def adjust_shop_session(user: User, session_id: UUID, body: ShopAdjust) -> Basket:
    return shop.adjust(user, session_id, body)


@router.post("/shop/baskets/{basket_id}/confirm")
def confirm_basket(
    user: User, basket_id: UUID, body: BasketConfirm, idempotency_key: IdempotencyKey
) -> BasketConfirmResult:
    return shop.confirm_basket(user, basket_id, body, idempotency_key)
