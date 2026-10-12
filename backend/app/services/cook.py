"""Cook sessions, recipes and ratings. STUB — Role 5 replaces the function bodies.

The real versions keep the logic in `app/reco/` (pure functions) and use this module
only to load and save: sessions, feedback, and inventory through Role 2's services.
"""

from uuid import UUID

from app import mock
from app.auth import CurrentUser
from app.errors import ApiError, ErrorCode
from app.schemas.cook import (
    CookAdjust,
    CookConfirm,
    CookConfirmResult,
    CookFeedback,
    CookRecord,
    CookRecordStatus,
    CookSessionCreate,
    Suggestion,
    UseFirstItem,
    UseFirstList,
)
from app.schemas.recipes import Recipe, StarResult
from app.schemas.stock_events import StockEventType, StockRefType


def start_session(user: CurrentUser, body: CookSessionCreate) -> Suggestion:
    return mock.suggestion(people=body.people or mock.preferences().last_cook_people)


def adjust(user: CurrentUser, session_id: UUID, body: CookAdjust) -> Suggestion:
    return mock.suggestion(
        "cabbage-tofu",
        people=body.people or 2,
        has_previous=True,
        tags=body.tags,
        max_minutes=body.max_minutes,
        max_difficulty=body.max_difficulty,
    )


def next_suggestion(user: CurrentUser, session_id: UUID) -> Suggestion:
    """ "Not this": record `skipped` and move forward."""
    return mock.suggestion("soy-chicken", has_previous=True)


def previous_suggestion(user: CurrentUser, session_id: UUID) -> Suggestion:
    return mock.suggestion("tomato-egg")


def select(user: CurrentUser, session_id: UUID) -> CookRecord:
    """ "Cook this": create the cook record and propose what will be used."""
    return mock.cook_record()


def confirm(
    user: CurrentUser, record_id: UUID, body: CookConfirm, idempotency_key: UUID
) -> CookConfirmResult:
    """Apply the confirmed consumption through `apply_stock_event`."""
    items = [p.item for p in mock.cook_record().proposed_consumption]
    event = mock.stock_event(
        StockEventType.CONSUME, items, ref_type=StockRefType.COOK_SESSION, ref_id=record_id
    )
    return CookConfirmResult(event=event, items=items, cook_record_id=record_id)


def give_feedback(user: CurrentUser, record_id: UUID, body: CookFeedback) -> CookRecord:
    """Only a confirmed cook record can be rated."""
    record = mock.cook_record(CookRecordStatus.CONFIRMED)
    return record.model_copy(update={"rating": body.rating, "proposed_consumption": []})


def get_recipe(user: CurrentUser, recipe_id: UUID) -> Recipe:
    found = mock.RECIPES.get(str(recipe_id))
    if found is None:
        raise ApiError(ErrorCode.NOT_FOUND, "Recipe not found")
    return found


def set_star(user: CurrentUser, recipe_id: UUID, starred: bool) -> StarResult:
    get_recipe(user, recipe_id)
    return StarResult(recipe_id=recipe_id, starred=starred)


def use_first(user: CurrentUser) -> UseFirstList:
    """Optional feature (SPEC A2)."""
    return UseFirstList(
        items=[
            UseFirstItem(item=mock.item("cabbage"), days_left=1),
            UseFirstItem(item=mock.item("egg-old"), days_left=2),
        ]
    )
