"""Cook sessions, recipes and ratings backed by the transactional SQL repository."""

from uuid import UUID

from app import clock
from app.auth import CurrentUser
from app.errors import ApiError, ErrorCode
from app.schemas.common import FreshnessStatus, RemainingState
from app.schemas.cook import (
    CookAdjust,
    CookConfirm,
    CookConfirmResult,
    CookFeedback,
    CookRecord,
    CookSessionCreate,
    Suggestion,
    UseFirstItem,
    UseFirstList,
)
from app.schemas.recipes import Recipe, StarResult
from app.services.recommendation_sql import recommendation_uow
from app.services.recommendation_workflow import RecommendationWorkflow

workflow = RecommendationWorkflow(recommendation_uow)


def start_session(user: CurrentUser, body: CookSessionCreate) -> Suggestion:
    return workflow.start_cook(user, body)


def adjust(user: CurrentUser, session_id: UUID, body: CookAdjust) -> Suggestion:
    return workflow.adjust_cook(user, session_id, body)


def next_suggestion(user: CurrentUser, session_id: UUID) -> Suggestion:
    return workflow.next_cook(user, session_id)


def previous_suggestion(user: CurrentUser, session_id: UUID) -> Suggestion:
    return workflow.previous_cook(user, session_id)


def select(user: CurrentUser, session_id: UUID) -> CookRecord:
    return workflow.select_cook(user, session_id)


def confirm(
    user: CurrentUser, record_id: UUID, body: CookConfirm, idempotency_key: UUID
) -> CookConfirmResult:
    return workflow.confirm_cook(user, record_id, body, idempotency_key)


def give_feedback(user: CurrentUser, record_id: UUID, body: CookFeedback) -> CookRecord:
    return workflow.feedback(user, record_id, body)


def get_recipe(user: CurrentUser, recipe_id: UUID) -> Recipe:
    with recommendation_uow() as repo:
        candidate = next(
            (
                recipe
                for recipe in repo.catalogue(user.household_id).recipes
                if recipe.id == recipe_id
            ),
            None,
        )
        if candidate is None:
            raise ApiError(ErrorCode.NOT_FOUND, "Recipe not found")
        return Recipe.model_validate(candidate.model_dump())


def set_star(user: CurrentUser, recipe_id: UUID, starred: bool) -> StarResult:
    with recommendation_uow() as repo:
        repo.set_star(user, recipe_id, starred)
    return StarResult(recipe_id=recipe_id, starred=starred)


def use_first(user: CurrentUser) -> UseFirstList:
    with recommendation_uow() as repo:
        items = repo.inventory(user.household_id)
    today = clock.today()
    return UseFirstList(
        items=[
            UseFirstItem(item=item, days_left=(item.est_use_first_date - today).days)
            for item in items
            if item.est_use_first_date is not None
            and item.freshness_status == FreshnessStatus.USE_SOON
            and item.remaining_state != RemainingState.OUT
        ]
    )
