"""Shop development tests; independent of the reserved report scenarios."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.reco import adjust_shop, new_shop_session, plan_shop, shopping_list, to_basket
from app.reco.config import ShopConfig
from app.reco.models import Candidate
from app.reco.shop_models import PurchaseSpec, ShopSession
from app.schemas.common import (
    Allergen,
    Cuisine,
    Equipment,
    FreshnessStatus,
    IngredientCategory,
    RemainingState,
    TasteTag,
)
from app.schemas.recipes import RecipeIngredient
from app.schemas.shop import Basket, ShopAdjust, ShopTag
from tests.reco_fixtures import CATALOGUE, NOW, PURCHASES, batch, metadata, prefs, recipe, uid


def basket_list(meals=None, inventory=(), people=2, purchases=None, catalogue=None):
    return shopping_list(
        [recipe()] if meals is None else meals,
        inventory,
        CATALOGUE if catalogue is None else catalogue,
        PURCHASES if purchases is None else purchases,
        people,
        as_of=NOW,
    )


def plan(meals, inventory=(), preferences=None, session=None, **kwargs):
    return plan_shop(
        meals,
        inventory,
        prefs() if preferences is None else preferences,
        session or ShopSession(),
        CATALOGUE,
        PURCHASES,
        as_of=NOW,
        **kwargs,
    )


def test_counts_aggregate_all_meals_and_scale_before_subtracting_stock_once():
    # Two meals, each 6 eggs for four people = 12; five at home => one tray of ten.
    result = basket_list([recipe("one"), recipe("two")], [batch(count=5)], people=4)
    assert len(result.items) == 1
    assert result.items[0].suggested_packs == 1
    assert result.items[0].surplus_packs == pytest.approx(0.3)
    assert not result.items[0].needs_check
    assert result.confirmed_at_home == 1


def test_multiple_batches_summed_without_reusing_them_for_each_meal():
    result = basket_list(
        [recipe("one"), recipe("two")],
        [batch(count=2), batch(key="two", count=2)],
    )
    assert result.items[0].suggested_packs == 1  # Need six, have four.
    assert result.items[0].surplus_packs == pytest.approx(0.8)
    assert not basket_list(inventory=[batch(count=2), batch(key="two", count=2)]).items


@pytest.mark.parametrize(
    "changes",
    [
        {"count": None},
        {"remaining_state": RemainingState.UNKNOWN},
        {"unit": "g"},
        {"countable": False},
        {"last_confirmed_at": NOW - timedelta(days=15)},
        {"last_confirmed_at": NOW + timedelta(hours=1)},
        {"freshness_status": FreshnessStatus.CHECK},
    ],
)
def test_uncertain_counts_remain_visible_and_do_not_reduce_packs(changes):
    result = basket_list(
        inventory=[batch(count=30, **changes)] if "count" not in changes else [batch(**changes)]
    )
    assert result.items[0].needs_check
    assert result.items[0].suggested_packs == 1
    assert result.confirmed_at_home == 0


def test_uncertain_second_batch_stays_visible_even_when_confirmed_stock_covers_need():
    result = basket_list(inventory=[batch(), batch(key="unknown", count=None)])
    assert len(result.items) == 1
    assert result.items[0].needs_check
    assert result.items[0].suggested_packs is None
    assert "covers the plan" in result.items[0].amount


@pytest.mark.parametrize("state", list(RemainingState))
def test_state_stock_never_invents_numeric_amount_available(state):
    result = basket_list(
        [recipe(ingredients=("tomato",))], [batch("tomato", remaining_state=state)]
    )
    if state == RemainingState.ENOUGH:
        assert not result.items
    else:
        assert result.items[0].suggested_packs is None
        assert result.items[0].needs_check == (state == RemainingState.UNKNOWN)
        assert "300 g" in result.items[0].amount


def test_stale_nonperishable_state_must_still_be_checked_for_shop():
    result = basket_list(
        [recipe(ingredients=("uncooked rice",))],
        [batch("uncooked rice", last_confirmed_at=NOW - timedelta(days=15))],
    )
    assert result.items[0].needs_check


@pytest.mark.parametrize("countable", [True, False])
def test_expired_stock_never_reduces_purchases(countable):
    name = "egg" if countable else "tomato"
    result = basket_list(
        [recipe(ingredients=(name,))], [batch(name, freshness_status=FreshnessStatus.EXPIRED)]
    )
    assert result.items
    assert result.confirmed_at_home == 0
    assert not result.items[0].needs_check  # Definitely unusable, not waiting for confirmation.


def test_optional_ingredients_included_and_explicit_nonpurchase_water_omitted():
    meal = recipe(ingredients=("egg", "tomato", "water"))
    meal.ingredients[1].essential = False
    result = basket_list([meal])
    assert {item.ingredient_id for item in result.items} == {uid("egg"), uid("tomato")}


def test_untracked_staple_is_assumed_but_explicit_out_is_purchased():
    meal = recipe(ingredients=("salt",))
    assert not basket_list([meal]).items
    assert len(basket_list([meal], [batch("salt", remaining_state=RemainingState.OUT)]).items) == 1


@pytest.mark.parametrize("coarse", [False, True])
def test_conflicting_or_coarse_units_keep_a_check_instead_of_inventing_conversion(coarse):
    original = recipe("one")
    second = recipe("two")
    second.ingredients[0] = RecipeIngredient(
        ingredient_id=uid("egg"),
        name="egg",
        quantity=None if coarse else 100,
        unit=None if coarse else "g",
        coarse_amount="one handful" if coarse else None,
        essential=True,
        prep_note=None,
    )
    item = basket_list([original, second], [batch(count=10)]).items[0]
    assert item.needs_check
    assert item.suggested_packs is None
    assert "3 pcs" in item.amount
    assert ("one handful" if coarse else "100 g") in item.amount


@pytest.mark.parametrize(
    "pack",
    [
        {"purchase_unit": None, "purchase_unit_size": None, "purchase_unit_measure": None},
        {"purchase_unit": "bag", "purchase_unit_size": 500, "purchase_unit_measure": "g"},
    ],
)
def test_missing_or_incompatible_pack_metadata_is_an_explicit_check(pack):
    purchases = {
        **PURCHASES,
        uid("egg"): PurchaseSpec(**{**PURCHASES[uid("egg")].model_dump(), **pack}),
    }
    item = basket_list(purchases=purchases).items[0]
    assert item.needs_check
    assert item.suggested_packs is None


def test_fractional_quantities_do_not_round_a_whole_pack_up_due_to_float_error():
    meals = [recipe(str(n)) for n in range(3)]
    for meal in meals:
        meal.ingredients[0].quantity = 0.1
    purchases = {
        **PURCHASES,
        uid("egg"): PURCHASES[uid("egg")].model_copy(update={"purchase_unit_size": 0.3}),
    }
    item = basket_list(meals, purchases=purchases).items[0]
    assert item.suggested_packs == 1
    assert item.surplus_packs == 0


def test_large_purchase_does_not_return_unconfirmable_suggested_pack_count():
    meal = recipe()
    meal.ingredients[0].quantity = 501
    item = basket_list([meal]).items[0]
    assert item.suggested_packs is None
    assert item.needs_check
    assert "split purchase" in item.amount


def test_empty_kitchen_plans_meals_and_reuses_shared_ingredients():
    result = plan([recipe("one"), recipe("two"), recipe("three")])
    assert len(result.planned_meals) == 3
    assert len(result.items) == 1
    assert result.items[0].suggested_packs == 1


def test_hard_filters_precede_shopping_and_soft_time_does_not_prevent_results():
    eggs = recipe("egg")
    tomato = recipe("tomato", ingredients=("tomato",), total_minutes=90)
    result = plan([eggs, tomato], preferences=prefs(allergens=[Allergen.EGG], max_cook_minutes=5))
    assert [meal.id for meal in result.planned_meals] == [tomato.id]
    assert all(item.ingredient_id != uid("egg") for item in result.items)
    assert not plan([eggs], preferences=prefs(allergens=[Allergen.EGG])).planned_meals
    assert not plan([tomato], session=ShopSession(strict_max_minutes=10)).planned_meals


def test_unknown_metadata_and_unreviewed_recipes_never_enter_plan():
    unknown = recipe("unknown", ingredients=("not in catalogue",))
    unreviewed = recipe("draft", reviewed=False)
    assert not plan([unknown, unreviewed]).planned_meals


def test_variant_family_does_not_fill_multiple_meal_slots():
    base = recipe("base")
    variants = [recipe(f"variant-{n}", base_recipe_id=base.id, starred=True) for n in range(6)]
    different = recipe("different", ingredients=("tomato",))
    result = plan([base, *variants, different])
    assert len(result.planned_meals) == 2
    assert len({meal.base_recipe_id or meal.id for meal in result.planned_meals}) == 2
    basket = to_basket(result, uid("session"), uid("basket"))
    assert basket.meals == 2  # Actual coverage, not requested three.
    assert Basket.model_validate(basket.model_dump(mode="json")) == basket
    assert basket == to_basket(result, uid("session"), uid("basket"))
    assert basket.items[0].id != to_basket(result, uid("session"), uid("other")).items[0].id


def test_candidate_admission_ignores_stock_but_combination_score_uses_confirmed_stock():
    first, second = sorted([recipe("a"), recipe("b")], key=lambda meal: str(meal.id))
    # Both still need eggs; the one that loses the ID tie-break also uses tomato from home.
    second = recipe(second.title, ingredients=("egg", "tomato"))
    stocked = batch("tomato")
    result = plan(
        [first, second],
        [stocked],
        session=ShopSession(meals=1),
        shop_config=ShopConfig(candidate_limit=1),
    )
    assert result.planned_meals[0].id == first.id  # Pool admitted by preference, not stock.
    result = plan([first, second], [stocked], session=ShopSession(meals=1))
    assert result.planned_meals[0].id == second.id


def test_a_meal_the_kitchen_already_covers_is_left_to_cook():
    to_buy, covered = recipe("a"), recipe("b", ingredients=("tomato",))
    result = plan([to_buy, covered], [batch("tomato")], session=ShopSession(meals=2))
    assert [meal.id for meal in result.planned_meals] == [to_buy.id]
    assert result.items

    result = plan([covered], [batch("tomato")], session=ShopSession(meals=1))
    assert result.planned_meals == () and result.all_stocked


def test_meals_with_something_to_buy_beat_ones_that_only_need_a_check_at_home():
    unsure = batch("tomato", remaining_state=RemainingState.UNKNOWN)
    check_only = recipe("check-only", ingredients=("tomato",), starred=True)
    to_buy = recipe("to-buy")
    result = plan([check_only, to_buy], [unsure], session=ShopSession(meals=1))
    assert [meal.id for meal in result.planned_meals] == [to_buy.id]

    # With nothing else to buy for, a check is still worth a trip.
    result = plan([check_only, to_buy], [unsure], session=ShopSession(meals=2))
    assert {meal.id for meal in result.planned_meals} == {to_buy.id, check_only.id}
    result = plan([check_only], [unsure], session=ShopSession(meals=1))
    assert [meal.id for meal in result.planned_meals] == [check_only.id]
    assert all(item.needs_check for item in result.items)


def test_pinned_recipes_are_always_planned_first_and_the_rest_filled_as_usual():
    starred = recipe("starred", starred=True)
    asked = recipe("asked", ingredients=("tomato",))
    other = recipe("other", cuisine=Cuisine.THAI)
    session = ShopSession(meals=2, pinned_recipe_ids=(asked.id,))
    result = plan([starred, asked, other], session=session)
    assert result.planned_meals[0].id == asked.id
    assert len(result.planned_meals) == 2
    assert uid("tomato") in {item.ingredient_id for item in result.items}


def test_a_pinned_recipe_is_planned_even_when_already_covered():
    asked = recipe("asked", ingredients=("tomato",))
    session = ShopSession(meals=1, pinned_recipe_ids=(asked.id,))
    result = plan([asked, recipe("a")], [batch("tomato")], session=session)
    assert [meal.id for meal in result.planned_meals] == [asked.id]


def test_pins_raise_the_meal_count_and_survive_adjustment():
    pins = (uid("x"), uid("y"), uid("x"))
    session = new_shop_session(prefs(), 2, 1, pinned=pins)
    assert session.pinned_recipe_ids == (uid("x"), uid("y")) and session.meals == 2
    adjusted = adjust_shop(session, ShopAdjust(meals=1))
    assert adjusted.pinned_recipe_ids == session.pinned_recipe_ids and adjusted.meals == 2


def test_variety_and_pack_surplus_influence_combo_score():
    first = recipe("first", starred=True)
    same = recipe("same")
    varied = recipe("varied", cuisine=Cuisine.THAI)
    result = plan([first, same, varied], session=ShopSession(meals=2))
    assert {meal.id for meal in result.planned_meals} == {first.id, varied.id}
    assert result.score_terms["cuisine_variety"] > 0
    assert result.score_terms["pack_surplus"] < 0
    assert result.score_terms["shared_ingredients"] > 0


def test_lower_pack_surplus_can_overturn_recipe_id_tie_break():
    wasteful, efficient = sorted([recipe("left"), recipe("right")], key=lambda meal: str(meal.id))
    efficient.ingredients[0].quantity = 9  # One leftover, versus seven for the other meal.
    result = plan([wasteful, efficient], session=ShopSession(meals=1))
    assert result.planned_meals[0].id == efficient.id
    assert result.items[0].surplus_packs == pytest.approx(0.1)


def test_shop_tags_bias_preferences_without_becoming_fatal_filters():
    eggs = recipe("eggs")
    veg = recipe("veg", ingredients=("tomato",), taste_tags=[TasteTag.VEGETABLE_RICH])
    session = ShopSession(meals=1, tags=(ShopTag.MORE_VEGETABLES,))
    assert plan([eggs, veg], session=session).planned_meals[0].id == veg.id
    assert plan([eggs], session=session).planned_meals
    session = replace(session, tags=(ShopTag.LONGER_LASTING,))
    assert plan([eggs, veg], session=session).planned_meals[0].id == eggs.id


def test_adjustments_accumulate_and_cover_more_is_capped():
    session = new_shop_session(prefs(last_shop_people=4, last_shop_meals=6))
    assert (session.people, session.meals) == (4, 6)
    updated = adjust_shop(session, ShopAdjust(tags=[ShopTag.MORE_VEGETABLES]))
    updated = adjust_shop(updated, ShopAdjust(tags=[ShopTag.COVER_MORE_MEALS] * 2))
    assert updated.meals == 7
    assert session.meals == 6
    updated = adjust_shop(updated, ShopAdjust(tags=[ShopTag.COVER_MORE_MEALS]))
    assert updated.meals == 7
    updated = adjust_shop(updated, ShopAdjust(meals=2, people=3, tags=[ShopTag.COVER_MORE_MEALS]))
    assert (updated.people, updated.meals) == (3, 2)
    assert set(updated.tags) == {ShopTag.MORE_VEGETABLES, ShopTag.COVER_MORE_MEALS}


def test_order_independent_bounded_search_and_fewer_meals_only_for_short_pool():
    meals = [recipe(f"meal-{n}") for n in range(24)]
    result = plan(meals, session=ShopSession(meals=7), shop_config=ShopConfig(beam_width=1))
    reverse = plan(
        list(reversed(meals)), session=ShopSession(meals=7), shop_config=ShopConfig(beam_width=1)
    )
    assert result == reverse
    assert len(result.planned_meals) == 7


def test_invalid_input_is_distinct_from_no_safe_recipe():
    with pytest.raises(ValueError, match="duplicate recipe"):
        plan([recipe(), recipe()])
    with pytest.raises(ValueError, match="duplicate batch"):
        plan([recipe()], [batch(), batch()])
    with pytest.raises(ValueError, match="purchase metadata"):
        basket_list(purchases={})
    with pytest.raises(ValueError, match="no eligible"):
        to_basket(plan([]), uid("session"), uid("basket"))
    with pytest.raises(ValidationError):
        PurchaseSpec(**{**PURCHASES[uid("egg")].model_dump(), "purchase_unit_size": -1})
    with pytest.raises(ValueError):
        ShopConfig(beam_width=0)


def test_all_48_seed_recipes_can_feed_a_seven_meal_plan_with_explicit_fixture_metadata():
    # Structural integration only. Synthetic flags/pack sizes are NOT seed data
    # or evidence of allergen/diet correctness; Role 2 supplies that catalogue.
    meals, catalogue, purchases = [], {}, {}
    for path in sorted((Path(__file__).resolve().parents[1] / "seed/recipes").glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["base_recipe_id"] = data.pop("variant_of")
        data.setdefault("variant_label", None)
        data["starred"] = False
        data.pop("source")
        for line in data["ingredients"]:
            line["name"] = line.pop("canonical_name")
            ingredient_id = uid(line["name"])
            line["ingredient_id"] = ingredient_id
            for field in ("quantity", "unit", "coarse_amount", "prep_note"):
                line.setdefault(field, None)
            catalogue[ingredient_id] = metadata(
                line["name"], countable=line["name"] == "egg", staple=line["name"] == "water"
            )
            purchases[ingredient_id] = PurchaseSpec(
                category=IngredientCategory.OTHER,
                buyable=line["name"] != "water",
                purchase_unit=None,
                purchase_unit_size=None,
                purchase_unit_measure=None,
                shelf_life_days=None,
            )
        meals.append(Candidate(**data))
    assert len(meals) == 48
    result = plan_shop(
        meals,
        [],
        prefs(equipment=list(Equipment)),
        ShopSession(people=4, meals=7),
        catalogue,
        purchases,
        as_of=NOW,
    )
    assert len(result.planned_meals) == 7
    assert len({meal.base_recipe_id or meal.id for meal in result.planned_meals}) == 7
    expected = {
        line.ingredient_id
        for meal in result.planned_meals
        for line in meal.ingredients
        if purchases[line.ingredient_id].buyable
    }
    assert {item.ingredient_id for item in result.items} == expected
    basket = to_basket(result, uid("real-seed-session"), uid("real-seed-basket"))
    assert Basket.model_validate_json(basket.model_dump_json()) == basket


@settings(max_examples=80, derandomize=True, deadline=None)
@given(
    people=st.integers(1, 12),
    meals=st.integers(1, 7),
    stock=st.integers(0, 100),
    allergic=st.booleans(),
)
def test_generated_plans_preserve_allergens_and_round_aggregate_counts(
    people, meals, stock, allergic
):
    candidates = [recipe(f"egg-{n}") for n in range(meals)]
    result = plan(
        candidates,
        [batch(count=stock)],
        preferences=prefs(allergens=[Allergen.EGG] if allergic else []),
        session=ShopSession(people=people, meals=meals),
    )
    if allergic:
        assert not result.planned_meals
        assert not result.items
    else:
        from math import ceil

        if stock >= 3 * people / 2:
            # Any one of these meals can be cooked from stock already: left to Cook.
            assert not result.planned_meals and result.all_stocked
            return
        expected = ceil(max(0, meals * 3 * people / 2 - stock) / 10)
        assert len(result.planned_meals) == meals
        assert sum(item.suggested_packs or 0 for item in result.items) == expected
