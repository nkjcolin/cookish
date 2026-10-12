from uuid import UUID

from fastapi import APIRouter

from app.auth import User
from app.deps import IdempotencyKey
from app.schemas.cook import (
    CookAdjust,
    CookConfirm,
    CookConfirmResult,
    CookFeedback,
    CookRecord,
    CookSessionCreate,
    Suggestion,
    UseFirstList,
)
from app.schemas.recipes import Recipe, StarResult, StarUpdate
from app.services import cook

router = APIRouter(tags=["cook"])


@router.post("/cook/sessions", status_code=201)
def start_cook_session(user: User, body: CookSessionCreate) -> Suggestion:
    return cook.start_session(user, body)


@router.post("/cook/sessions/{session_id}/adjust")
def adjust_cook_session(user: User, session_id: UUID, body: CookAdjust) -> Suggestion:
    return cook.adjust(user, session_id, body)


@router.post("/cook/sessions/{session_id}/next")
def next_cook_suggestion(user: User, session_id: UUID) -> Suggestion:
    return cook.next_suggestion(user, session_id)


@router.post("/cook/sessions/{session_id}/previous")
def previous_cook_suggestion(user: User, session_id: UUID) -> Suggestion:
    return cook.previous_suggestion(user, session_id)


@router.post("/cook/sessions/{session_id}/select", status_code=201)
def select_cook_suggestion(user: User, session_id: UUID) -> CookRecord:
    return cook.select(user, session_id)


@router.post("/cook/records/{record_id}/confirm")
def confirm_cook_record(
    user: User, record_id: UUID, body: CookConfirm, idempotency_key: IdempotencyKey
) -> CookConfirmResult:
    return cook.confirm(user, record_id, body, idempotency_key)


@router.post("/cook/records/{record_id}/feedback")
def rate_cook_record(user: User, record_id: UUID, body: CookFeedback) -> CookRecord:
    return cook.give_feedback(user, record_id, body)


@router.get("/recipes/{recipe_id}")
def get_recipe(user: User, recipe_id: UUID) -> Recipe:
    return cook.get_recipe(user, recipe_id)


@router.put("/recipes/{recipe_id}/star")
def star_recipe(user: User, recipe_id: UUID, body: StarUpdate) -> StarResult:
    return cook.set_star(user, recipe_id, body.starred)


@router.get("/use-first")
def list_use_first(user: User) -> UseFirstList:
    return cook.use_first(user)
