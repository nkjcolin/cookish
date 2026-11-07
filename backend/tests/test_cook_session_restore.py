"""Restarting restores absolute limits without re-executing relative nudges."""

from dataclasses import replace
from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.auth import CurrentUser
from app.errors import ApiError, ErrorCode
from app.schemas.common import Allergen, TasteTag
from app.schemas.cook import CookAdjust, CookSessionConstraints, CookSessionCreate, CookTag
from app.services.recommendation_workflow import RecommendationWorkflow
from tests.reco_fixtures import NOW, prefs, recipe, uid
from tests.recommendation_repository_fake import HOUSEHOLD, FakeDatabase, set_recipes

USER = CurrentUser(uid("restore-user"), HOUSEHOLD, "fixture@example.test")


def setup(*recipes):
    db = FakeDatabase()
    set_recipes(db, *recipes)
    return db, RecommendationWorkflow(db.transaction, now=lambda: NOW)


def no_result(action):
    with pytest.raises(ApiError) as error:
        action()
    assert error.value.code == ErrorCode.NO_RESULT


def test_allow_more_time_after_skip_preserves_skip_and_returns_longer_recipe():
    short = recipe("salad", total_minutes=15, starred=True)
    long = recipe("soup", total_minutes=30)
    db, service = setup(short, long)
    first = service.start_cook(
        USER, CookSessionCreate(constraints=CookSessionConstraints(max_minutes=15))
    )
    no_result(lambda: service.next_cook(USER, first.session_id))
    relaxed = service.start_cook(
        USER,
        CookSessionCreate(
            previous_session_id=first.session_id,
            constraints=CookSessionConstraints(max_minutes=30),
        ),
    )
    assert relaxed.recipe.id == long.id
    assert relaxed.applied_constraints.max_minutes == 30
    assert not relaxed.has_previous
    saved = db.state["cook_sessions"][HOUSEHOLD, relaxed.session_id]
    assert saved.state.skipped_recipe_ids == {short.id}
    assert saved.selected_record_id is None
    # Reset deliberately starts fresh and permits the previously skipped dish.
    assert service.start_cook(USER, CookSessionCreate()).recipe.id == short.id


def test_numeric_failure_can_be_relaxed_without_replaying_other_constraints():
    meal = recipe("soup", total_minutes=20, taste_tags=[TasteTag.LOW_OIL])
    db, service = setup(meal)
    first = service.start_cook(USER, CookSessionCreate())
    no_result(lambda: service.adjust_cook(USER, first.session_id, CookAdjust(max_minutes=5)))
    relaxed = service.start_cook(
        USER,
        CookSessionCreate(
            previous_session_id=first.session_id,
            constraints=CookSessionConstraints(
                max_minutes=20, max_difficulty=1, tags=[CookTag.EASIER, CookTag.LESS_OIL]
            ),
        ),
    )
    assert relaxed.recipe.id == meal.id
    assert relaxed.applied_constraints.max_difficulty == 1
    assert relaxed.applied_constraints.tags == [CookTag.EASIER, CookTag.LESS_OIL]
    assert db.state["cook_sessions"][HOUSEHOLD, first.session_id].state.max_minutes == 5


def test_expired_session_restore_does_not_apply_relative_nudges_twice():
    medium = recipe("medium", starred=True, difficulty=2)
    easy = recipe("easy", total_minutes=20, difficulty=1)
    db, service = setup(medium, easy)
    first = service.start_cook(USER, CookSessionCreate())
    adjusted = service.adjust_cook(
        USER, first.session_id, CookAdjust(tags=[CookTag.EASIER, CookTag.QUICKER])
    )
    assert adjusted.recipe.id == easy.id
    set_recipes(db, medium, easy.model_copy(update={"starred": True}))
    row = db.state["cook_sessions"][HOUSEHOLD, first.session_id]
    db.state["cook_sessions"][HOUSEHOLD, first.session_id] = replace(
        row, expires_at=NOW - timedelta(seconds=1)
    )
    restored = service.start_cook(
        USER,
        CookSessionCreate(
            previous_session_id=first.session_id,
            constraints=CookSessionConstraints(**adjusted.applied_constraints.model_dump()),
        ),
    )
    assert restored.recipe.id == easy.id
    assert restored.applied_constraints.max_difficulty == 1
    assert restored.applied_constraints.max_minutes == 20


def test_restore_ranks_under_requested_limits_even_when_preference_default_has_no_match():
    db, service = setup(recipe("twenty", total_minutes=20))
    db.state["prefs"][HOUSEHOLD] = prefs(max_cook_minutes=15)
    no_result(lambda: service.start_cook(USER, CookSessionCreate()))
    restored = service.start_cook(
        USER,
        CookSessionCreate(
            previous_session_id=uid("deleted-session"),
            constraints=CookSessionConstraints(max_minutes=30),
        ),
    )
    assert restored.recipe.total_minutes == 20
    # Null explicitly removes the soft cap rather than silently using 15 again.
    unlimited = service.start_cook(
        USER, CookSessionCreate(constraints=CookSessionConstraints(max_minutes=None))
    )
    assert unlimited.applied_constraints.max_minutes is None


def test_restore_cannot_relax_strict_time_or_current_allergen_gate():
    db, service = setup(recipe("twenty", total_minutes=20))
    first = service.start_cook(USER, CookSessionCreate())
    row = db.state["cook_sessions"][HOUSEHOLD, first.session_id]
    db.state["cook_sessions"][HOUSEHOLD, first.session_id] = replace(
        row, state=replace(row.state, strict_max_minutes=15)
    )
    no_result(
        lambda: service.start_cook(
            USER,
            CookSessionCreate(
                previous_session_id=first.session_id,
                constraints=CookSessionConstraints(max_minutes=None),
            ),
        )
    )
    db.state["prefs"][HOUSEHOLD] = prefs(allergens=[Allergen.EGG])
    no_result(
        lambda: service.start_cook(USER, CookSessionCreate(constraints=CookSessionConstraints()))
    )


def test_restored_binary_tags_still_filter_and_boost_normally():
    db, service = setup(
        recipe("ordinary", starred=True),
        recipe("low-oil-vegetables", taste_tags=[TasteTag.LOW_OIL, TasteTag.VEGETABLE_RICH]),
    )
    restored = service.start_cook(
        USER,
        CookSessionCreate(
            constraints=CookSessionConstraints(
                tags=[CookTag.LESS_OIL, CookTag.MORE_VEGETABLES, CookTag.MORE_PROTEIN]
            )
        ),
    )
    assert restored.recipe.id == uid("low-oil-vegetables")
    state = db.state["cook_sessions"][HOUSEHOLD, restored.session_id].state
    assert state.required_tags == {TasteTag.LOW_OIL, TasteTag.VEGETABLE_RICH}
    assert state.boosted_tags == {TasteTag.HIGH_PROTEIN}


@pytest.mark.parametrize("already_skipped", [False, True])
def test_expired_not_tonight_skips_the_displayed_dish_once(already_skipped):
    rejected = recipe("rejected", starred=True)
    alternative = recipe("alternative")
    db, service = setup(rejected, alternative)
    first = service.start_cook(USER, CookSessionCreate())
    row = db.state["cook_sessions"][HOUSEHOLD, first.session_id]
    db.state["cook_sessions"][HOUSEHOLD, first.session_id] = replace(
        row,
        expires_at=NOW - timedelta(seconds=1),
        state=replace(
            row.state,
            skipped_recipe_ids=frozenset({rejected.id}) if already_skipped else frozenset(),
        ),
    )
    with pytest.raises(ApiError) as error:
        service.next_cook(USER, first.session_id)
    assert error.value.code == ErrorCode.NOT_FOUND
    recovered = service.start_cook(
        USER,
        CookSessionCreate(
            previous_session_id=first.session_id,
            skip_previous_recipe=True,
            constraints=CookSessionConstraints(**first.applied_constraints.model_dump()),
        ),
    )
    assert recovered.recipe.id == alternative.id
    saved = db.state["cook_sessions"][HOUSEHOLD, recovered.session_id]
    assert saved.state.skipped_recipe_ids == {rejected.id}


def test_skip_recovery_flag_requires_a_source_session():
    with pytest.raises(ValidationError, match="requires previous_session_id"):
        CookSessionCreate(skip_previous_recipe=True)
