"""Cook services backed by the pure engine and transactional SQL workflow."""

from uuid import UUID

from app import clock
from app.auth import CurrentUser
from app.db.session import transaction
from app.reco.use_first import use_first_items
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
from app.schemas.recipes import Recipe, StarResult
from app.services.freshness import PERISHABLE_CATEGORIES
from app.services.recipe_details import read_recipe, save_star
from app.services.recommendation_sql import recommendation_workflow
from app.services.stock_events import get_inventory_snapshot


def start_session(user: CurrentUser, body: CookSessionCreate) -> Suggestion:
    return recommendation_workflow(user).start_cook(user, body)


def adjust(user: CurrentUser, session_id: UUID, body: CookAdjust) -> Suggestion:
    return recommendation_workflow(user).adjust_cook(user, session_id, body)


def next_suggestion(user: CurrentUser, session_id: UUID) -> Suggestion:
    """ "Not this": record `skipped` and move forward."""
    return recommendation_workflow(user).next_cook(user, session_id)


def previous_suggestion(user: CurrentUser, session_id: UUID) -> Suggestion:
    return recommendation_workflow(user).previous_cook(user, session_id)


def select(user: CurrentUser, session_id: UUID) -> CookRecord:
    """ "Cook this": create the cook record and propose what will be used."""
    return recommendation_workflow(user).select_cook(user, session_id)


def confirm(
    user: CurrentUser, record_id: UUID, body: CookConfirm, idempotency_key: UUID
) -> CookConfirmResult:
    """Apply the confirmed consumption through `apply_stock_event`."""
    return recommendation_workflow(user).confirm_cook(user, record_id, body, idempotency_key)


def give_feedback(user: CurrentUser, record_id: UUID, body: CookFeedback) -> CookRecord:
    """Only a confirmed cook record can be rated."""
    return recommendation_workflow(user).feedback(user, record_id, body)


def get_recipe(user: CurrentUser, recipe_id: UUID) -> Recipe:
    with transaction() as session:
        return read_recipe(session, user.household_id, recipe_id)


def set_star(user: CurrentUser, recipe_id: UUID, starred: bool) -> StarResult:
    with transaction() as session:
        return save_star(session, user, recipe_id, starred)


def use_first(user: CurrentUser) -> UseFirstList:
    """Read the household's computed freshness and order usable soon-due stock."""
    with transaction() as session:
        inventory = get_inventory_snapshot(session, user.household_id)
        return use_first_items(
            inventory, as_of=clock.now(), perishable_categories=PERISHABLE_CATEGORIES
        )
