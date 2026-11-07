"""Cook engine development tests, not the reserved held-out evaluation scenarios."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from app.reco import (
    adjust,
    new_session,
    score_recipe,
    skip_current,
    suggest,
    to_suggestion,
)
from app.reco.inventory import assess_ingredients
from app.reco.models import Candidate, CatalogIngredient, CookSession
from app.schemas.common import (
    Allergen,
    Cuisine,
    Diet,
    Equipment,
    FreshnessStatus,
    LabelDateKind,
    RemainingState,
    TasteTag,
)
from app.schemas.cook import CookAdjust, CookTag, FreshnessReason, IngredientStatus, Suggestion
from app.schemas.recipes import RecipeIngredient
from tests.reco_fixtures import CATALOGUE, NOW, batch, metadata, prefs, recipe, uid


def choose(recipes, inventory=(), preferences=None, session=None, catalogue=None, **kwargs):
    preferences = prefs() if preferences is None else preferences
    session = new_session(preferences) if session is None else session
    return suggest(
        recipes,
        inventory,
        preferences,
        session,
        CATALOGUE if catalogue is None else catalogue,
        as_of=NOW,
        **kwargs,
    )


def assessment(inventory, meal=None, people=2, catalogue=None):
    return assess_ingredients(
        meal or recipe(), inventory, catalogue or CATALOGUE, people, as_of=NOW
    )[0]


@pytest.mark.parametrize(
    "changes",
    [
        {"allergens": [Allergen.EGG]},
        {"diets": [Diet.VEGAN]},
        {"equipment": []},
    ],
)
def test_hard_restrictions_survive_empty_inventory_fallback(changes):
    result = choose([recipe(starred=True)], preferences=prefs(**changes))
    assert result.selected is None
    assert result.relaxable == ()


def test_optional_ingredients_participate_in_diet_and_allergen_checks():
    meal = recipe(ingredients=("tomato", "egg"))
    meal.ingredients[1].essential = False
    for preferences in [prefs(allergens=[Allergen.EGG]), prefs(diets=[Diet.VEGAN])]:
        assert choose([meal], preferences=preferences).selected is None


def test_missing_metadata_and_unreviewed_recipes_are_excluded():
    assert choose([recipe()], catalogue={}).selected is None
    assert choose([recipe(reviewed=False)]).selected is None
    wrong = {uid("egg"): CATALOGUE[uid("tomato")]}
    assert choose([recipe()], catalogue=wrong).selected is None
    with pytest.raises(ValidationError):
        CatalogIngredient(
            id=uid("new"),
            canonical_name="new",
            countable=False,
            is_staple=False,
            perishable=True,
        )


def test_equipment_requires_every_appliance_and_diets_require_every_flag():
    meal = recipe(equipment=[Equipment.STOVE, Equipment.STEAMER])
    assert choose([meal]).selected is None
    p = prefs(equipment=[Equipment.STOVE, Equipment.STEAMER], diets=[Diet.VEGETARIAN])
    assert choose([meal], preferences=p).selected is not None
    assert choose([meal], preferences=p.model_copy(update={"diets": [Diet.VEGAN]})).selected is None


def test_soft_time_can_be_relaxed_but_strict_time_cannot():
    p = prefs(max_cook_minutes=10)
    assert choose([recipe()], preferences=p).relaxable == ("max_minutes",)
    s = new_session(p, strict_max_minutes=10)
    result = choose([recipe()], preferences=p, session=s)
    assert result.selected is None
    assert result.relaxable == ()


def test_no_result_reports_only_soft_changes_that_actually_restore_a_candidate():
    s = CookSession(max_minutes=10, required_tags=frozenset([TasteTag.LOW_OIL]))
    result = choose([recipe()], session=s)
    assert result.relaxable == ("max_minutes", "tags")
    assert result.selected is None
    blocked = choose([recipe()], session=s, preferences=prefs(allergens=[Allergen.EGG]))
    assert blocked.relaxable == ()
    with pytest.raises(ValueError, match="NO_RESULT"):
        to_suggestion(blocked, uid("session"))


def test_counted_batches_are_summed_and_scaled_without_invented_conversions():
    items = [batch(key="a", count=2), batch(key="b", count=3)]
    item = assessment(items, people=4)
    assert item.quantity == 6
    assert item.amount == "6 pcs"
    assert item.known_quantity == 5
    assert item.status == IngredientStatus.LOW
    items.append(batch(key="c", count=1))
    assert assessment(items, people=4).status == IngredientStatus.HAVE
    assert assessment([batch(unit="pack", count=10)]).status == IngredientStatus.UNKNOWN
    assert assessment([batch(unit=None, count=10)]).status == IngredientStatus.UNKNOWN


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (RemainingState.ENOUGH, IngredientStatus.HAVE),
        (RemainingState.LOW, IngredientStatus.LOW),
        (RemainingState.UNKNOWN, IngredientStatus.UNKNOWN),
        (RemainingState.OUT, IngredientStatus.MISSING),
    ],
)
def test_state_tracking_does_not_invent_grams(state, expected):
    item = assessment([batch("tomato", remaining_state=state)], recipe(ingredients=("tomato",)), 12)
    assert item.quantity == 1800
    assert item.known_quantity is None
    assert item.status == expected


@pytest.mark.parametrize("count", [None, float("inf")])
def test_uncertain_counts_are_not_treated_as_known_stock(count):
    assert assessment([batch(count=count)]).status == IngredientStatus.UNKNOWN


def test_expired_and_out_batches_never_contribute_to_count_or_urgency():
    bad = batch(
        key="expired",
        count=99,
        freshness_status=FreshnessStatus.EXPIRED,
        label_date_kind=LabelDateKind.USE_BY,
        label_date=NOW.date() - timedelta(days=1),
        est_use_first_date=NOW.date() - timedelta(days=1),
    )
    out = batch(key="out", count=99, remaining_state=RemainingState.OUT)
    item = assessment([bad, out, batch(key="usable", count=1)])
    assert item.known_quantity == 1
    assert item.status == IngredientStatus.LOW
    assert [c.reason for c in item.freshness_check] == [FreshnessReason.PAST_USE_BY]
    assert [b.count for b in item.usable_batches] == [1]
    scored = choose([recipe()], [bad]).selected
    assert scored.score.expiry_urgency == 0
    assert scored.ingredients[0].status == IngredientStatus.MISSING


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        (
            {"label_date_kind": LabelDateKind.BEST_BEFORE, "label_date": NOW.date()},
            FreshnessReason.PAST_BEST_BEFORE,
        ),
        ({}, FreshnessReason.PAST_ESTIMATE),
        ({"est_use_first_date": None}, FreshnessReason.NO_DATE),
    ],
)
def test_check_batches_require_confirmation_without_becoming_missing(changes, reason):
    item = batch(freshness_status=FreshnessStatus.CHECK, count=99, **changes)
    result = choose([recipe()], [item])
    assert not result.missing_essential_fallback
    assert result.selected.ingredients[0].status == IngredientStatus.CHECK
    assert result.selected.score.coverage == 0
    assert result.selected.score.expiry_urgency == 0
    assert result.selected.score.unknown_essentials == 1
    api = to_suggestion(result, uid("session"))
    assert [c.reason for c in api.freshness_check] == [reason]
    assert api.needs_check == []


def test_suggestion_distinguishes_counted_shortage_from_state_tracked_low_stock():
    counted = to_suggestion(choose([recipe()], [batch(count=1)]), uid("counted-session"))
    assert counted.ingredients[0].status == IngredientStatus.LOW
    assert counted.ingredients[0].countable is True
    state_tracked = to_suggestion(
        choose([recipe(ingredients=("tomato",))], [batch("tomato", remaining_state="low")]),
        uid("state-session"),
    )
    assert state_tracked.ingredients[0].status == IngredientStatus.LOW
    assert state_tracked.ingredients[0].countable is False


def test_freshness_confirmation_is_owned_by_snapshot_not_recomputed():
    # Role 2 may mark a checked best-before batch usable for 24h.
    item = batch(
        est_use_first_date=NOW.date() - timedelta(days=1),
        label_date=NOW.date() - timedelta(days=1),
        label_date_kind=LabelDateKind.BEST_BEFORE,
        freshness_status=FreshnessStatus.OK,
        freshness_confirmed_at=NOW,
    )
    result = choose([recipe()], [item])
    assert result.selected.ingredients[0].status == IngredientStatus.HAVE
    assert result.selected.score.expiry_urgency == 0  # past dates never earn a bonus
    # Even a recent confirmation cannot override EXPIRED supplied by Role 2.
    item.freshness_status = FreshnessStatus.EXPIRED
    assert choose([recipe()], [item]).selected.ingredients[0].status == IngredientStatus.MISSING


def test_stale_perishable_confirmation_is_unknown_but_dry_goods_are_not():
    old = NOW - timedelta(days=14, seconds=1)
    item = assessment([batch(last_confirmed_at=old)])
    assert item.status == IngredientStatus.UNKNOWN
    assert len(item.needs_check) == 1
    assert (
        assessment([batch(last_confirmed_at=NOW - timedelta(days=14))]).status
        == IngredientStatus.HAVE
    )
    rice = recipe(ingredients=("uncooked rice",))
    assert (
        assessment([batch("uncooked rice", last_confirmed_at=old)], rice).status
        == IngredientStatus.HAVE
    )


def test_unknown_check_uses_existing_earliest_batch_and_no_fake_item_for_absence():
    early = batch(key="early", count=None, est_use_first_date=NOW.date())
    later = batch(key="later", count=None, est_use_first_date=NOW.date() + timedelta(days=2))
    api = to_suggestion(choose([recipe()], [later, early]), uid("session"))
    assert [c.item.id for c in api.needs_check] == [early.id]
    empty = choose([recipe()])
    assert empty.missing_essential_fallback
    assert to_suggestion(empty, uid("session")).needs_check == []
    assert empty.selected.ingredients[0].status == IngredientStatus.MISSING


def test_confirmed_sufficient_stock_beats_uncertain_batch_without_counting_it():
    items = [batch(count=3), batch(key="unknown", count=None)]
    item = assessment(items)
    assert item.status == IngredientStatus.HAVE
    assert item.known_quantity == 3
    assert not item.needs_check


def test_staples_assume_availability_only_without_explicit_stock_evidence():
    meal = recipe(ingredients=("salt",))
    assert assessment([], meal).status == IngredientStatus.STAPLE
    assert (
        assessment([batch("salt", remaining_state=RemainingState.OUT)], meal).status
        == IngredientStatus.MISSING
    )
    assert (
        assessment([batch("salt", freshness_status=FreshnessStatus.CHECK)], meal).status
        == IngredientStatus.CHECK
    )


def test_stocked_recipe_wins_over_missing_essential_even_with_large_preference():
    missing = recipe("favourite", ingredients=("tomato",), taste_tags=[TasteTag.RICH])
    stocked = recipe()
    result = choose([missing, stocked], [batch()], taste_weights={"tag:rich": 1000})
    assert result.selected.recipe.id == stocked.id
    assert not result.missing_essential_fallback
    result = choose([missing, stocked], taste_weights={"tag:rich": 1000})
    assert result.missing_essential_fallback
    assert result.selected.recipe.id == missing.id


def test_cold_start_is_deterministic_with_zero_history_and_explainable_score():
    a, b = recipe("a"), recipe("b")
    result = choose([b, a], [batch()])
    other = choose([a, b], [batch()], taste_weights={})
    assert result.selected.recipe.id == other.selected.recipe.id
    score = result.selected.score
    assert score.preference == 0
    assert score.repetition == 0
    assert score.total == pytest.approx(sum(score.terms.values()))
    assert score.coverage == 1
    assert result.session.shown_recipe_ids == (result.selected.recipe.id,)


def test_learned_preferences_cuisine_star_dislikes_and_history_affect_score():
    p = prefs(cuisines=[Cuisine.CHINESE], disliked_ingredient_ids=[uid("egg")])
    meal = recipe(starred=True, taste_tags=[TasteTag.LIGHT])
    s = replace(new_session(p), shown_recipe_ids=(meal.id,), recent_recipe_ids=frozenset([meal.id]))
    result = score_recipe(
        meal,
        [batch()],
        p,
        s,
        CATALOGUE,
        as_of=NOW,
        taste_weights={"tag:light": 2, "cuisine:chinese": 0.5},
    )
    assert result.score.preference == pytest.approx(3)
    assert result.score.repetition == 2
    assert result.score.terms["repetition"] < 0
    with pytest.raises(ValueError, match="finite"):
        choose([meal], taste_weights={"tag:light": float("nan")})


def test_adjustments_accumulate_and_cannot_relax_existing_limits():
    current = recipe(total_minutes=35, difficulty=3)
    s = replace(new_session(prefs(max_cook_minutes=50)), current_recipe_id=current.id)
    first = adjust(s, CookAdjust(tags=[CookTag.LESS_OIL, CookTag.QUICKER], people=4), current)
    assert first.people == 4 and first.max_minutes == 25
    second = adjust(first, CookAdjust(tags=[CookTag.MORE_PROTEIN], max_minutes=60), current)
    assert second.max_minutes == 25
    assert second.required_tags == frozenset([TasteTag.LOW_OIL])
    assert second.boosted_tags == frozenset([TasteTag.HIGH_PROTEIN])
    third = adjust(second, CookTag.EASIER, current)
    assert third.max_difficulty == 2
    assert s.max_minutes == 50 and s.people == 2
    with pytest.raises(ValueError, match="current recipe"):
        adjust(s, CookTag.LESS_OIL, recipe("wrong"))


def test_exhausted_quicker_and_easier_requests_do_not_silently_relax():
    current = recipe(total_minutes=5)
    s = replace(new_session(prefs()), current_recipe_id=current.id)
    assert adjust(s, CookTag.QUICKER, current).max_minutes == 0
    assert choose([current], session=adjust(s, CookTag.QUICKER, current)).selected is None
    assert adjust(s, CookTag.EASIER, current).max_difficulty == 0
    assert choose([current], session=adjust(s, CookTag.EASIER, current)).relaxable == ()


def test_adjustment_prefers_eligible_same_family_over_unrelated_high_score():
    base = recipe()
    variant = recipe("less-oil", base_recipe_id=base.id, taste_tags=[TasteTag.LOW_OIL])
    unrelated = recipe("unrelated", taste_tags=[TasteTag.LOW_OIL, TasteTag.RICH])
    s = replace(new_session(prefs()), current_recipe_id=base.id)
    s = adjust(s, CookTag.LESS_OIL, base)
    result = choose(
        [base, variant, unrelated], [batch()], session=s, taste_weights={"tag:rich": 100}
    )
    assert result.selected.recipe.id == variant.id
    assert result.selected.preferred_variant
    assert result.session.anchor_recipe_id is None
    # A family link never bypasses a hard filter.
    variant.ingredients.append(
        RecipeIngredient(
            ingredient_id=uid("firm tofu"),
            name="tofu",
            quantity=300,
            unit="g",
            coarse_amount=None,
            essential=False,
            prep_note=None,
        )
    )
    blocked = choose(
        [base, variant, unrelated],
        [batch()],
        session=s,
        preferences=prefs(allergens=[Allergen.SOY]),
    )
    assert blocked.selected.recipe.id == unrelated.id


def test_more_protein_is_a_boost_not_a_requirement_and_avoids_wrong_family_variant():
    base = recipe()
    wrong_variant = recipe("less-oil", base_recipe_id=base.id, taste_tags=[TasteTag.LOW_OIL])
    protein = recipe("protein", taste_tags=[TasteTag.HIGH_PROTEIN])
    s = adjust(replace(new_session(prefs()), current_recipe_id=base.id), CookTag.MORE_PROTEIN, base)
    assert (
        choose([base, wrong_variant, protein], [batch()], session=s).selected.recipe.id
        == protein.id
    )
    assert choose([base], [batch()], session=s).selected is not None


def test_skip_excludes_only_current_recipe_and_does_not_change_learned_weights():
    meals = [recipe("a"), recipe("b")]
    weights = {"tag:light": 1.0}
    first = choose(meals, taste_weights=weights)
    second = choose(meals, session=skip_current(first.session), taste_weights=weights)
    assert second.selected.recipe.id != first.selected.recipe.id
    assert to_suggestion(second, uid("session")).has_previous
    final = choose(meals, session=skip_current(second.session), taste_weights=weights)
    assert final.selected is None and not final.relaxable
    assert weights == {"tag:light": 1.0}


def test_coarse_amounts_are_not_silently_converted_and_inputs_are_unchanged():
    meal = recipe()
    meal.ingredients[0].quantity = None
    meal.ingredients[0].unit = None
    meal.ingredients[0].coarse_amount = "a little"
    before = meal.model_dump()
    result = choose([meal], [batch()], session=CookSession(people=4))
    item = result.selected.ingredients[0]
    assert item.quantity is None and item.status == IngredientStatus.UNKNOWN
    assert "original serves 2" in item.amount
    assert meal.model_dump() == before


def test_duplicate_batches_and_recipes_cannot_inflate_availability():
    with pytest.raises(ValueError, match="duplicate batch"):
        choose([recipe()], [batch(), batch()])
    with pytest.raises(ValueError, match="duplicate recipe"):
        choose([recipe(), recipe()])


def test_real_approved_recipe_selects_less_oil_variant_without_public_contract_changes():
    root = Path(__file__).resolve().parents[1] / "seed/recipes"
    meals = []
    for slug in ("tomato-egg-stir-fry", "tomato-egg-stir-fry-less-oil"):
        data = yaml.safe_load((root / f"{slug}.yaml").read_text(encoding="utf-8"))
        data["base_recipe_id"] = data.pop("variant_of")
        data.setdefault("variant_label", None)
        data["starred"] = slug == "tomato-egg-stir-fry"
        data.pop("source")
        for item in data["ingredients"]:
            item["name"] = item.pop("canonical_name")
            item["ingredient_id"] = uid(item["name"])
            for field in ("quantity", "unit", "coarse_amount", "prep_note"):
                item.setdefault(field, None)
        meals.append(Candidate(**data))
    items = [batch("egg", count=6), batch("tomato"), batch("uncooked rice"), batch("spring onion")]
    before = deepcopy([m.model_dump() for m in meals])
    first = choose(meals, items)
    assert first.selected.recipe.id == meals[0].id
    s = adjust(first.session, CookAdjust(tags=[CookTag.LESS_OIL], people=4), meals[0])
    second = choose(meals, items, session=s)
    assert second.selected.recipe.id == meals[1].id
    api = to_suggestion(second, uid("session"))
    assert Suggestion.model_validate_json(api.model_dump_json()) == api
    assert next(item.amount for item in api.ingredients if item.name == "egg") == "6 pcs"
    assert api.applied_constraints.tags == [CookTag.LESS_OIL]
    assert api.has_previous
    assert before == [m.model_dump() for m in meals]


@settings(max_examples=150, derandomize=True, deadline=None)
@given(
    allergen=st.sampled_from(list(Allergen)),
    state=st.sampled_from(list(RemainingState)),
    freshness=st.sampled_from(list(FreshnessStatus)),
    count=st.one_of(st.none(), st.integers(0, 20)),
    people=st.integers(1, 12),
    age=st.integers(0, 30),
    tags=st.lists(st.sampled_from(list(CookTag)), max_size=3),
)
def test_allergen_never_appears_before_or_after_generated_adjustments(
    allergen, state, freshness, count, people, age, tags
):
    catalogue = dict(CATALOGUE)
    catalogue[uid("egg")] = metadata("egg", allergens=[allergen], countable=True)
    safe = recipe("safe", ingredients=("tomato",), taste_tags=[TasteTag.LOW_OIL])
    unsafe = recipe("unsafe", ingredients=("tomato", "egg"), starred=True)
    unsafe.ingredients[-1].essential = False
    p = prefs(allergens=[allergen])
    items = [
        batch(
            count=count,
            remaining_state=state,
            freshness_status=freshness,
            last_confirmed_at=NOW - timedelta(days=age),
        ),
        batch("tomato", remaining_state=state, freshness_status=freshness),
    ]
    session = new_session(p, people)
    result = choose([unsafe, safe], items, p, session, catalogue)
    for index in range(len(tags) + 1):
        if result.selected is None:
            break
        assert all(
            allergen not in catalogue[item.ingredient_id].allergens
            for item in result.selected.recipe.ingredients
        )
        if index < len(tags):
            session = adjust(result.session, tags[index], result.selected.recipe)
            result = choose([unsafe, safe], items, p, session, catalogue)


def test_people_only_patch_does_not_prefer_an_unrequested_variant():
    base = recipe(starred=True)
    variant = recipe("variant", base_recipe_id=base.id)
    first = choose([base, variant], [batch(count=10)])
    s = adjust(first.session, CookAdjust(people=4), base)
    assert s.anchor_recipe_id is None
    assert s.people == 4


def test_use_first_urgency_uses_singapore_day_and_never_promotes_uncertain_batches():
    # 17:00 UTC on 19 Oct is 01:00 on 20 Oct in Singapore.
    when = datetime.fromisoformat("2026-10-19T17:00:00+00:00")
    meal = recipe()
    p = prefs()
    usable = batch(est_use_first_date=NOW.date(), last_confirmed_at=when - timedelta(hours=1))
    scored = score_recipe(meal, [usable], p, new_session(p), CATALOGUE, as_of=when)
    assert scored.score.expiry_urgency == 1
    usable.freshness_status = FreshnessStatus.CHECK
    scored = score_recipe(meal, [usable], p, new_session(p), CATALOGUE, as_of=when)
    assert scored.score.expiry_urgency == 0
    with pytest.raises(ValueError, match="timezone-aware"):
        score_recipe(meal, [usable], p, new_session(p), CATALOGUE, as_of=when.replace(tzinfo=None))


def test_optional_missing_does_not_trigger_essential_fallback():
    meal = recipe(ingredients=("egg", "tomato"))
    meal.ingredients[1].essential = False
    result = choose([meal], [batch()])
    assert not result.missing_essential_fallback
    assert result.selected.ingredients[1].status == IngredientStatus.MISSING


def test_available_unrelated_meal_beats_missing_family_variant():
    base = recipe()
    variant = recipe(
        "variant", ingredients=("tomato",), base_recipe_id=base.id, taste_tags=[TasteTag.LOW_OIL]
    )
    other = recipe("other", taste_tags=[TasteTag.LOW_OIL])
    s = adjust(replace(new_session(prefs()), current_recipe_id=base.id), CookTag.LESS_OIL, base)
    result = choose([base, variant, other], [batch()], session=s)
    assert result.selected.recipe.id == other.id
    assert not result.missing_essential_fallback


@pytest.mark.parametrize("people", [0, 13, 1.5, True])
def test_invalid_people_is_rejected(people):
    with pytest.raises(ValueError):
        new_session(prefs(), people)


def test_three_refinements_preserve_diet_equipment_time_and_prior_tags():
    p = prefs(allergens=[Allergen.EGG], diets=[Diet.VEGAN], equipment=[Equipment.STOVE])
    base = recipe("base", ingredients=("firm tofu",), total_minutes=35)
    low = recipe(
        "low",
        ingredients=("firm tofu",),
        total_minutes=35,
        base_recipe_id=base.id,
        taste_tags=[TasteTag.LOW_OIL],
        starred=True,
    )
    quick = recipe(
        "quick",
        ingredients=("firm tofu",),
        total_minutes=25,
        base_recipe_id=base.id,
        taste_tags=[TasteTag.LOW_OIL],
    )
    veg = recipe(
        "veg",
        ingredients=("firm tofu",),
        total_minutes=25,
        difficulty=3,
        base_recipe_id=base.id,
        taste_tags=[TasteTag.LOW_OIL, TasteTag.VEGETABLE_RICH],
    )
    prohibited = recipe("egg-variant", base_recipe_id=base.id, starred=True)
    meals = [base, low, quick, veg, prohibited]
    s = replace(new_session(p, strict_max_minutes=40), current_recipe_id=base.id)
    current = base
    for tag, expected in [
        (CookTag.LESS_OIL, low),
        (CookTag.QUICKER, quick),
        (CookTag.MORE_VEGETABLES, veg),
    ]:
        s = adjust(s, tag, current)
        result = choose(meals, [batch("firm tofu")], p, s)
        current = result.selected.recipe
        assert current.id == expected.id
        assert current.total_minutes <= result.session.strict_max_minutes
        assert set(current.equipment) <= set(p.equipment)
        assert TasteTag.LOW_OIL in current.taste_tags
        assert all(
            Diet.VEGAN in CATALOGUE[item.ingredient_id].diet_flags
            and Allergen.EGG not in CATALOGUE[item.ingredient_id].allergens
            for item in current.ingredients
        )
        s = result.session
    assert s.tags == (CookTag.LESS_OIL, CookTag.QUICKER, CookTag.MORE_VEGETABLES)
