"""Cook ranking refreshes household history instead of trusting a saved session."""

from contextlib import contextmanager
from datetime import timedelta
from itertools import count

import pytest

from app.auth import CurrentUser
from app.errors import ApiError, ErrorCode
from app.schemas.cook import CookAdjust, CookSessionCreate
from app.services.recommendation_workflow import RecommendationWorkflow
from tests.reco_fixtures import NOW, recipe, uid
from tests.recommendation_repository_fake import HOUSEHOLD, FakeDatabase, set_recipes

USER = CurrentUser(uid("history-user"), HOUSEHOLD, "history@example.test")


def setup():
    database = FakeDatabase()
    set_recipes(database, recipe("first"), recipe("second"), recipe("third"))
    ids = count()
    time = [NOW]
    workflow = RecommendationWorkflow(
        database.transaction, now=lambda: time[0], new_id=lambda: uid(f"history/{next(ids)}")
    )
    return database, workflow, time


def test_new_cook_session_penalises_confirmed_history_without_excluding_recipe():
    database, workflow, _ = setup()
    first = workflow.start_cook(USER, CookSessionCreate())
    database.state["recent"][HOUSEHOLD] = frozenset({first.recipe.id})
    another_session = workflow.start_cook(USER, CookSessionCreate())
    assert another_session.recipe.id != first.recipe.id
    # History is a scoring penalty, not an eligibility restriction.
    only = next(r for r in database.state["catalogue"].recipes if r.id == first.recipe.id)
    set_recipes(database, only)
    assert workflow.start_cook(USER, CookSessionCreate()).recipe.id == first.recipe.id


def test_active_session_refreshes_history_when_another_meal_is_cooked_or_ages_out():
    database, workflow, time = setup()
    first = workflow.start_cook(USER, CookSessionCreate())
    database.state["recent"][HOUSEHOLD] = frozenset({first.recipe.id})
    workflow.adjust_cook(USER, first.session_id, CookAdjust(people=3))
    saved = database.state["cook_sessions"][HOUSEHOLD, first.session_id]
    assert saved.state.recent_recipe_ids == frozenset({first.recipe.id})
    time[0] += timedelta(minutes=1)
    database.state["recent"][HOUSEHOLD] = frozenset()
    workflow.next_cook(USER, first.session_id)
    saved = database.state["cook_sessions"][HOUSEHOLD, first.session_id]
    assert saved.state.recent_recipe_ids == frozenset()


def test_failed_ranking_keeps_refreshed_history_without_appending_a_suggestion():
    database, workflow, _ = setup()
    set_recipes(database, recipe("only"))
    first = workflow.start_cook(USER, CookSessionCreate())
    database.state["recent"][HOUSEHOLD] = frozenset({first.recipe.id})
    with pytest.raises(ApiError) as caught:
        workflow.next_cook(USER, first.session_id)
    assert caught.value.code == ErrorCode.NO_RESULT
    saved = database.state["cook_sessions"][HOUSEHOLD, first.session_id]
    assert saved.state.recent_recipe_ids == frozenset({first.recipe.id})
    assert len(saved.history) == 1


@pytest.mark.parametrize("operation", ["start", "adjust", "next"])
def test_ranking_includes_confirmation_committed_while_waiting_for_lock(monkeypatch, operation):
    database, workflow, time = setup()
    first = workflow.start_cook(USER, CookSessionCreate())
    confirmed_at = NOW + timedelta(seconds=1)
    lookup_times = []

    def recent_recipe_ids(household_id, *, as_of):
        assert household_id == HOUSEHOLD
        lookup_times.append(as_of)
        # Mirror the SQL upper time bound: a request-start cutoff would omit
        # this confirmation, which committed while the request waited for the lock.
        return frozenset({first.recipe.id}) if confirmed_at <= as_of else frozenset()

    @contextmanager
    def delayed_transaction():
        time[0] += timedelta(seconds=2)
        with database.transaction() as repo:
            monkeypatch.setattr(repo, "recent_recipe_ids", recent_recipe_ids)
            yield repo

    workflow.unit_of_work = delayed_transaction
    if operation == "start":
        response = workflow.start_cook(USER, CookSessionCreate())
        assert response.recipe.id != first.recipe.id
    elif operation == "adjust":
        response = workflow.adjust_cook(USER, first.session_id, CookAdjust(people=3))
    else:
        response = workflow.next_cook(USER, first.session_id)

    assert lookup_times == [NOW + timedelta(seconds=2)]
    saved = database.state["cook_sessions"][HOUSEHOLD, response.session_id]
    assert saved.state.recent_recipe_ids == frozenset({first.recipe.id})
