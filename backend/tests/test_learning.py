"""Confirmed-meal learning and replacement semantics, independent of persistence."""

from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.reco import learn, plan_shop, score_recipe, taste_weights
from app.reco.config import LearningConfig
from app.reco.learning import LearningState
from app.reco.models import CookSession
from app.reco.shop_models import ShopSession
from app.schemas.common import Cuisine, TasteTag
from app.schemas.cook import CookRecordStatus, Rating
from tests.reco_fixtures import CATALOGUE, NOW, PURCHASES, prefs, recipe, uid

HOUSEHOLD = uid("household")


def update(state, *, record="record", meal=None, rating=None, status=CookRecordStatus.CONFIRMED):
    return learn(
        state,
        household_id=HOUSEHOLD,
        record_id=uid(record),
        recipe=meal or recipe(),
        status=status,
        rating=rating,
    )


def test_cold_start_is_zero_and_cooking_without_rating_has_small_provisional_reward():
    initial = LearningState(HOUSEHOLD)
    assert taste_weights(initial) == {}
    cooked = update(initial)
    assert taste_weights(cooked) == {"cuisine:chinese": 0.0625}
    assert initial.meals == ()
    assert update(cooked) is cooked


@pytest.mark.parametrize(
    "rating, expected", [(Rating.LIKE, 0.25), (Rating.MAYBE, 0), (Rating.DISLIKE, -0.25)]
)
def test_rating_replaces_provisional_reward_and_retries_are_noops(rating, expected):
    meal = recipe(taste_tags=[TasteTag.LOW_OIL, TasteTag.LOW_OIL])
    cooked = update(LearningState(HOUSEHOLD), meal=meal)
    rated = update(cooked, meal=meal, rating=rating)
    assert taste_weights(rated).get("cuisine:chinese", 0) == expected
    assert taste_weights(rated).get("tag:low_oil", 0) == expected
    assert update(rated, meal=meal, rating=rating) is rated
    assert update(rated, meal=meal) is rated  # Late confirmation retry cannot erase rating.
    direct = update(LearningState(HOUSEHOLD), meal=meal, rating=rating)
    assert taste_weights(direct) == taste_weights(rated)


def test_changed_ratings_replace_the_same_meal_instead_of_adding_training_samples():
    state = update(LearningState(HOUSEHOLD), rating=Rating.LIKE)
    state = update(state, rating=Rating.DISLIKE)
    assert taste_weights(state) == {"cuisine:chinese": -0.25}
    assert len(state.meals) == 1
    state = update(state, rating=Rating.MAYBE)
    assert taste_weights(state) == {}


def test_editing_after_saturation_replays_evidence_instead_of_subtracting_clipped_delta():
    state = LearningState(HOUSEHOLD)
    for index in range(12):
        state = update(state, record=str(index), rating=Rating.LIKE)
    assert taste_weights(state) == {"cuisine:chinese": 2}
    state = update(state, record="0", rating=Rating.MAYBE)
    # Eleven likes still saturate. Naively subtracting 0.25 would incorrectly give 1.75.
    assert taste_weights(state) == {"cuisine:chinese": 2}
    state = update(state, record="11", rating=Rating.DISLIKE)
    assert taste_weights(state) == {"cuisine:chinese": 1.75}


@pytest.mark.parametrize("status", [CookRecordStatus.SELECTED, CookRecordStatus.ABANDONED])
def test_selection_skip_and_abandonment_never_learn(status):
    state = LearningState(HOUSEHOLD)
    assert update(state, status=status) is state
    with pytest.raises(ValueError, match="only a confirmed"):
        update(state, status=status, rating=Rating.LIKE)


def test_household_and_cook_record_identity_cannot_be_swapped():
    state = update(LearningState(HOUSEHOLD))
    with pytest.raises(ValueError, match="different household"):
        learn(
            state,
            household_id=uid("another"),
            record_id=uid("record"),
            recipe=recipe(),
            status=CookRecordStatus.CONFIRMED,
            rating=Rating.LIKE,
        )
    with pytest.raises(ValueError, match="cannot change"):
        update(state, meal=recipe("another"), rating=Rating.LIKE)
    with pytest.raises(ValueError, match="cannot change"):
        update(state, meal=recipe(taste_tags=[TasteTag.SPICY]), rating=Rating.LIKE)
    with pytest.raises(ValueError, match="duplicate"):
        replace(state, meals=state.meals * 2)


def test_learned_features_change_future_cook_scores_and_shop_rankings():
    chinese = recipe("chinese", taste_tags=[TasteTag.LOW_OIL])
    thai = recipe("thai", cuisine=Cuisine.THAI)
    initial = LearningState(HOUSEHOLD)
    liked = update(initial, meal=chinese, rating=Rating.LIKE)
    weights = taste_weights(liked)
    before = score_recipe(chinese, [], prefs(), CookSession(), CATALOGUE, as_of=NOW)
    after = score_recipe(
        chinese, [], prefs(), CookSession(), CATALOGUE, as_of=NOW, taste_weights=weights
    )
    assert after.score.preference - before.score.preference == 0.5  # Cuisine + tag.
    shop = plan_shop(
        [thai, chinese],
        [],
        prefs(),
        ShopSession(meals=1),
        CATALOGUE,
        PURCHASES,
        as_of=NOW,
        taste_weights=weights,
    )
    assert shop.planned_meals[0].id == chinese.id
    disliked = update(liked, meal=chinese, rating=Rating.DISLIKE)
    shop = plan_shop(
        [thai, chinese],
        [],
        prefs(),
        ShopSession(meals=1),
        CATALOGUE,
        PURCHASES,
        as_of=NOW,
        taste_weights=taste_weights(disliked),
    )
    assert shop.planned_meals[0].id == thai.id


@pytest.mark.parametrize(
    "kwargs",
    [{"step": 0}, {"lower": 1}, {"upper": -1}, {"step": float("nan")}, {"upper": float("inf")}],
)
def test_learning_config_rejects_invalid_bounds(kwargs):
    with pytest.raises(ValueError):
        LearningConfig(**kwargs)


@settings(max_examples=80, derandomize=True, deadline=None)
@given(
    events=st.lists(
        st.tuples(st.integers(0, 5), st.sampled_from([None, *Rating])),
        min_size=1,
        max_size=50,
    )
)
def test_generated_retries_and_edits_match_replay_and_stay_bounded(events):
    state = LearningState(HOUSEHOLD)
    order, latest = [], {}
    for record, rating in events:
        key = str(record)
        if key not in latest:
            order.append(key)
            latest[key] = rating
        elif rating is not None:
            latest[key] = rating
        state = update(state, record=key, rating=rating)
        assert update(state, record=key, rating=rating) is state
        assert all(-2 <= weight <= 2 for weight in taste_weights(state).values())
    expected = LearningState(HOUSEHOLD)
    for record in order:
        expected = update(expected, record=record, rating=latest[record])
    assert state == expected
    assert taste_weights(state) == taste_weights(expected)
