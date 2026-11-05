"""Shop must cover essentials that cannot be replenished by its shopping list."""

from datetime import timedelta

import pytest

from app.reco import plan_shop, to_basket
from app.reco.config import ShopConfig
from app.reco.shop_models import ShopSession
from app.schemas.common import Diet, Equipment, FreshnessStatus, RemainingState
from evaluation.catalogue_review import NOW as REVIEW_NOW
from evaluation.catalogue_review import kitchens, load_catalogue, preferences
from tests.reco_fixtures import CATALOGUE, NOW, PURCHASES, batch, prefs, recipe, uid


def plan(meals, inventory=(), *, people=2, requested=3, **kwargs):
    purchases = {
        key: spec.model_copy(update={"buyable": False}) if key == uid("egg") else spec
        for key, spec in PURCHASES.items()
    }
    return plan_shop(
        meals,
        inventory,
        prefs(),
        ShopSession(people=people, meals=requested),
        CATALOGUE,
        purchases,
        as_of=NOW,
        **kwargs,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"count": 0},
        {"count": 2},
        {"count": None},
        {"unit": "g"},
        {"remaining_state": RemainingState.UNKNOWN},
        {"remaining_state": RemainingState.OUT},
        {"last_confirmed_at": NOW - timedelta(days=15)},
        {"last_confirmed_at": NOW + timedelta(hours=1)},
        {"freshness_status": FreshnessStatus.EXPIRED},
        {"freshness_status": FreshnessStatus.CHECK},
    ],
)
def test_unusable_nonbuyable_essential_excludes_recipe(changes):
    result = plan([recipe()], [batch(**changes)])
    assert not result.planned_meals
    assert not result.items


def test_missing_nonbuyable_essential_is_filtered_before_family_and_candidate_limit():
    blocked = recipe("blocked", starred=True)
    alternative = recipe("alternative", ingredients=("tomato",), base_recipe_id=blocked.id)
    result = plan([blocked, alternative], shop_config=ShopConfig(candidate_limit=1))
    assert [meal.id for meal in result.planned_meals] == [alternative.id]
    assert {item.ingredient_id for item in result.items} == {uid("tomato")}


@pytest.mark.parametrize("people,stock,expected", [(2, 3, 1), (2, 6, 2), (4, 6, 1), (4, 12, 2)])
def test_nonbuyable_counts_cover_the_whole_scaled_plan_once(people, stock, expected):
    meals = [recipe("one"), recipe("two")]
    inventory = [batch(count=stock - 1), batch(key="second", count=1)]
    result = plan(meals, inventory, people=people, requested=2)
    assert len(result.planned_meals) == expected
    assert not result.items
    assert to_basket(result, uid("session"), uid("basket")).meals == expected
    assert result == plan(list(reversed(meals)), inventory, people=people, requested=2)


def test_insufficient_shared_stock_uses_another_buyable_meal():
    meals = [recipe("one"), recipe("two"), recipe("other", ingredients=("tomato",))]
    result = plan(meals, [batch()], requested=2)
    assert len(result.planned_meals) == 2
    assert (
        sum(any(line.name == "egg" for line in meal.ingredients) for meal in result.planned_meals)
        == 1
    )
    assert {item.ingredient_id for item in result.items} == {uid("tomato")}


def test_uncertain_extra_batch_does_not_block_sufficient_confirmed_nonbuyable_stock():
    result = plan([recipe()], [batch(), batch(key="unknown", count=None)])
    assert len(result.planned_meals) == 1
    assert not result.items


def test_nonbuyable_combination_does_not_invent_conversion_between_recipe_units():
    pieces, grams = recipe("pieces"), recipe("grams")
    grams.ingredients[0].unit = "g"
    result = plan([pieces, grams], [batch(), batch(key="grams", unit="g")], requested=2)
    assert len(result.planned_meals) == 1


def test_nonbuyable_pantry_stock_still_needs_recent_confirmation():
    rice = uid("uncooked rice")
    purchases = {**PURCHASES, rice: PURCHASES[rice].model_copy(update={"buyable": False})}
    result = plan_shop(
        [recipe(ingredients=("uncooked rice",))],
        [batch("uncooked rice", last_confirmed_at=NOW - timedelta(days=15))],
        prefs(),
        ShopSession(),
        CATALOGUE,
        purchases,
        as_of=NOW,
    )
    assert not result.planned_meals


def test_optional_nonbuyable_and_assumed_staple_do_not_block_plans():
    optional = recipe("optional", ingredients=("egg", "tomato", "water"))
    optional.ingredients[0].essential = False
    result = plan([optional])
    assert result.planned_meals == (optional,)
    assert {item.ingredient_id for item in result.items} == {uid("tomato")}


def test_optional_demand_does_not_consume_stock_reserved_for_essential_requirement():
    essential = recipe("essential")
    optional = recipe("optional", ingredients=("egg", "tomato"))
    optional.ingredients[0].essential = False
    result = plan([essential, optional], [batch()], requested=2)
    assert len(result.planned_meals) == 2


@pytest.fixture(scope="module")
def real_catalogue():
    return load_catalogue()


@pytest.mark.parametrize(
    "changes,expected",
    [({}, 7), ({"diets": [Diet.HALAL]}, 7), ({"equipment": [Equipment.MICROWAVE]}, 0)],
)
def test_real_empty_kitchen_plans_never_depend_on_missing_cooked_rice(
    real_catalogue, changes, expected
):
    _, _, meals, metadata, purchases = real_catalogue
    result = plan_shop(
        meals,
        [],
        preferences(**changes),
        ShopSession(meals=7),
        metadata,
        purchases,
        as_of=REVIEW_NOW,
    )
    assert len(result.planned_meals) == expected
    # Independent catalogue check: none of these non-buyable essentials can be at home.
    assert all(
        purchases[line.ingredient_id].buyable or metadata[line.ingredient_id].is_staple
        for meal in result.planned_meals
        for line in meal.ingredients
        if line.essential
    )


@pytest.mark.parametrize(
    "changes,allowed",
    [
        ({}, True),
        ({"remaining_state": RemainingState.LOW}, False),
        ({"remaining_state": RemainingState.UNKNOWN}, False),
        ({"remaining_state": RemainingState.OUT}, False),
        ({"last_confirmed_at": REVIEW_NOW - timedelta(days=15)}, False),
        ({"freshness_status": FreshnessStatus.CHECK}, False),
        ({"freshness_status": FreshnessStatus.EXPIRED}, False),
    ],
)
def test_real_rice_recipes_require_confirmed_usable_cooked_rice(real_catalogue, changes, allowed):
    rows, orm, meals, metadata, purchases = real_catalogue
    rice_id = next(key for key, meta in metadata.items() if meta.canonical_name == "cooked rice")
    rice_meals = [
        meal
        for meal in meals
        if meal.title
        in {"Cucumber, tomato and chickpea rice salad", "Microwave broccoli and chickpea rice"}
    ]
    assert len(rice_meals) == 2
    rice = next(
        item for item in kitchens(rows, orm)["all_catalogue_units"] if item.ingredient_id == rice_id
    ).model_copy(update=changes)
    result = plan_shop(
        rice_meals,
        [rice],
        preferences(),
        ShopSession(meals=2),
        metadata,
        purchases,
        as_of=REVIEW_NOW,
    )
    assert len(result.planned_meals) == (2 if allowed else 0)
    assert all(item.ingredient_id != rice_id for item in result.items)
