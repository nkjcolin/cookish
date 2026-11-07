"""Advertised nudges must work on the real catalogue and current household snapshot."""

from copy import deepcopy
from dataclasses import replace

import pytest

from app.reco import adjust, available_nudges, new_session, suggest
from app.schemas.common import Allergen, Diet, Equipment, TasteTag
from app.schemas.cook import CookTag
from evaluation.catalogue_review import NOW, load_catalogue, preferences
from tests.reco_fixtures import CATALOGUE, batch, prefs, recipe


@pytest.fixture(scope="module")
def catalogue():
    _, _, recipes, metadata, _ = load_catalogue()
    return recipes, metadata


def start(catalogue, pref):
    recipes, metadata = catalogue
    result = suggest(recipes, [], pref, new_session(pref), metadata, as_of=NOW)
    assert result.selected is not None
    return result


def nudges(catalogue, pref, session, inventory=(), **kwargs):
    recipes, metadata = catalogue
    return available_nudges(recipes, inventory, pref, session, metadata, as_of=NOW, **kwargs)


def assert_advertised_actions_work(catalogue, pref, current):
    """Execute each advertised action and check its user-visible promise independently."""
    recipes, metadata = catalogue
    for tag in nudges(catalogue, pref, current.session):
        state = adjust(current.session, tag, current.selected.recipe)
        result = suggest(recipes, [], pref, state, metadata, as_of=NOW)
        assert result.selected is not None
        chosen = result.selected.recipe
        assert chosen.id != current.selected.recipe.id
        assert chosen.id not in state.skipped_recipe_ids
        assert set(chosen.equipment) <= set(pref.equipment)
        for line in chosen.ingredients:
            assert not metadata[line.ingredient_id].allergens.intersection(pref.allergens)
            assert set(pref.diets) <= metadata[line.ingredient_id].diet_flags
        if state.max_minutes is not None:
            assert chosen.total_minutes <= state.max_minutes
        if state.strict_max_minutes is not None:
            assert chosen.total_minutes <= state.strict_max_minutes
        if state.max_difficulty is not None:
            assert chosen.difficulty <= state.max_difficulty
        assert state.required_tags <= set(chosen.taste_tags)
        if tag == CookTag.QUICKER:
            assert chosen.total_minutes <= current.selected.recipe.total_minutes - 10
        elif tag == CookTag.EASIER:
            assert chosen.difficulty < current.selected.recipe.difficulty
        else:
            target = {
                CookTag.LESS_OIL: TasteTag.LOW_OIL,
                CookTag.MORE_PROTEIN: TasteTag.HIGH_PROTEIN,
                CookTag.MORE_VEGETABLES: TasteTag.VEGETABLE_RICH,
            }[tag]
            assert target in chosen.taste_tags


def test_cold_start_advertises_supported_changes_not_faster_or_easier_salad(catalogue):
    pref = preferences()
    current = start(catalogue, pref)
    assert current.selected.recipe.title == "Cucumber, tomato and chickpea rice salad"
    assert current.selected.recipe.total_minutes == 15
    assert current.selected.recipe.difficulty == 1
    assert nudges(catalogue, pref, current.session) == (
        CookTag.LESS_OIL,
        CookTag.MORE_PROTEIN,
    )
    assert_advertised_actions_work(catalogue, pref, current)


@pytest.mark.parametrize("restrictions", [{"diets": [Diet.VEGAN]}, {"allergens": [Allergen.EGG]}])
def test_real_protein_options_do_not_ignore_diet_or_egg_allergy(catalogue, restrictions):
    pref = preferences(**restrictions)
    current = start(catalogue, pref)
    options = nudges(catalogue, pref, current.session)
    assert CookTag.MORE_PROTEIN not in options
    assert CookTag.LESS_OIL in options
    assert_advertised_actions_work(catalogue, pref, current)


@pytest.mark.parametrize("restrictions", [{"equipment": []}, {"max_cook_minutes": 15}])
def test_only_eligible_salad_means_no_advertised_alternative(catalogue, restrictions):
    pref = preferences(**restrictions)
    current = start(catalogue, pref)
    assert nudges(catalogue, pref, current.session) == ()


def test_strict_time_and_accumulated_soft_time_are_preserved(catalogue):
    pref = preferences()
    current = start(catalogue, pref)
    assert nudges(catalogue, pref, replace(current.session, strict_max_minutes=15)) == ()
    limited = replace(current, session=replace(current.session, max_minutes=25))
    assert nudges(catalogue, pref, limited.session) == (CookTag.LESS_OIL,)
    assert_advertised_actions_work(catalogue, pref, limited)


def test_new_nudge_keeps_accumulated_low_oil_requirement(catalogue):
    recipes, metadata = catalogue
    pref = preferences()
    original = next(r for r in recipes if r.title == "Microwave broccoli and chickpea rice")
    state = replace(
        new_session(pref),
        current_recipe_id=original.id,
        max_minutes=25,
        tags=(CookTag.LESS_OIL,),
        required_tags=frozenset([TasteTag.LOW_OIL]),
    )
    assert nudges(catalogue, pref, state) == (CookTag.MORE_VEGETABLES,)
    result = suggest(
        recipes, [], pref, adjust(state, CookTag.MORE_VEGETABLES, original), metadata, as_of=NOW
    )
    assert result.selected is not None
    assert {TasteTag.LOW_OIL, TasteTag.VEGETABLE_RICH} <= set(result.selected.recipe.taste_tags)
    assert result.selected.recipe.total_minutes <= 25


@pytest.mark.parametrize(
    ("tag", "target"),
    [(CookTag.LESS_OIL, TasteTag.LOW_OIL), (CookTag.MORE_PROTEIN, TasteTag.HIGH_PROTEIN)],
)
def test_skipped_target_recipes_are_not_advertised_again(catalogue, tag, target):
    recipes, _ = catalogue
    pref = preferences()
    current = start(catalogue, pref)
    state = replace(
        current.session,
        skipped_recipe_ids=frozenset(r.id for r in recipes if target in r.taste_tags),
    )
    assert tag not in nudges(catalogue, pref, state)


@pytest.mark.parametrize(
    ("tag", "target"),
    [
        (CookTag.LESS_OIL, TasteTag.LOW_OIL),
        (CookTag.MORE_PROTEIN, TasteTag.HIGH_PROTEIN),
        (CookTag.MORE_VEGETABLES, TasteTag.VEGETABLE_RICH),
    ],
)
def test_already_satisfied_or_applied_binary_nudges_are_hidden(catalogue, tag, target):
    recipes, _ = catalogue
    pref = preferences()
    matching = next(r for r in recipes if target in r.taste_tags)
    state = replace(new_session(pref), current_recipe_id=matching.id)
    assert tag not in nudges(catalogue, pref, state)
    current = start(catalogue, pref)
    assert tag not in nudges(catalogue, pref, replace(current.session, tags=(tag,)))


def test_quicker_can_be_repeated_only_while_a_faster_recipe_exists(catalogue):
    recipes, metadata = catalogue
    pref = preferences()
    original = next(r for r in recipes if r.title == "Tomato and egg rice bowls")
    state = replace(new_session(pref), current_recipe_id=original.id)
    assert CookTag.QUICKER in nudges(catalogue, pref, state)
    quicker = suggest(
        recipes, [], pref, adjust(state, CookTag.QUICKER, original), metadata, as_of=NOW
    )
    assert quicker.selected.recipe.title == "Quick tomato and egg rice"
    assert quicker.selected.recipe.total_minutes == 20
    assert CookTag.QUICKER not in nudges(catalogue, pref, quicker.session)


def test_easier_offers_a_real_simpler_variant_then_stops_at_easy(catalogue):
    recipes, metadata = catalogue
    pref = preferences()
    original = next(r for r in recipes if r.title == "One-pot ginger chicken and bok choy rice")
    state = replace(new_session(pref), current_recipe_id=original.id)
    assert CookTag.EASIER in nudges(catalogue, pref, state)
    easier = suggest(
        recipes, [], pref, adjust(state, CookTag.EASIER, original), metadata, as_of=NOW
    )
    assert easier.selected.recipe.title == "One-pot tofu and mushroom rice"
    assert easier.selected.recipe.difficulty == 1
    assert CookTag.EASIER not in nudges(catalogue, pref, easier.session)


def test_available_tags_require_a_different_result_not_just_an_eligible_recipe():
    pref = prefs()
    current = recipe("current", ingredients=("tomato",), taste_tags=[TasteTag.LIGHT])
    protein = recipe("protein", taste_tags=[TasteTag.HIGH_PROTEIN])
    state = replace(new_session(pref), current_recipe_id=current.id)
    data = ([current, protein], CATALOGUE)
    assert CookTag.MORE_PROTEIN in nudges(data, pref, state)
    # The stock-first gate keeps the available tomato dish ahead of missing eggs.
    stocked = [batch("tomato", last_confirmed_at=NOW, est_use_first_date=NOW.date())]
    assert CookTag.MORE_PROTEIN not in nudges(data, pref, state, stocked)
    # Learned weights also influence what the action would actually return.
    assert CookTag.MORE_PROTEIN not in nudges(
        data, pref, state, taste_weights={"tag:high_protein": -2.0, "tag:light": 2.0}
    )
    assert nudges(([current], CATALOGUE), pref, state) == ()


def test_availability_is_deterministic_and_does_not_change_inputs(catalogue):
    recipes, metadata = catalogue
    pref = preferences(equipment=[Equipment.STOVE], max_cook_minutes=35, max_difficulty=1)
    current = start(catalogue, pref)
    inventory = []
    weights = {"tag:high_protein": 0.25}
    inputs = (recipes, inventory, pref, current.session, metadata, weights)
    before = deepcopy(inputs)
    first = nudges(catalogue, pref, current.session, inventory, taste_weights=weights)
    assert nudges(catalogue, pref, current.session, inventory, taste_weights=weights) == first
    assert inputs == before
    assert_advertised_actions_work(catalogue, pref, current)
