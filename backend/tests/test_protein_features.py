"""Explicit catalogue protein features and compatibility with saved meal evidence."""

from dataclasses import replace
from uuid import UUID

import pytest

from app.reco.cook import recipe_features, score_recipe
from app.reco.learning import LearningState, MealEvidence, learn, taste_weights
from app.reco.models import CookSession
from app.reco.protein import PROTEIN_INGREDIENTS, protein_features
from app.schemas.common import Cuisine, TasteTag
from app.schemas.cook import CookRecordStatus, Rating
from app.schemas.recipes import RecipeIngredient
from evaluation.catalogue_review import load_catalogue
from tests.reco_fixtures import NOW, prefs, recipe, uid

HOUSEHOLD = uid("protein-household")
RECORD = uid("protein-record")
EGG = UUID("4ec6f234-be95-4bf6-a25c-53d8bf6dc9f3")
TOFU = UUID("3524a936-adb8-4288-9416-a710e209a9a9")
TEMPEH = UUID("ca4c852e-630d-4677-b976-4a9f46fcf594")
FISH = UUID("47ea5a95-1021-474e-a545-6cb82510ce1a")
SOY_SAUCE = UUID("7ad4c266-44c1-4c15-be3d-5cd9da236a79")


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue()


def line(ingredient_id, *, essential=True, name="Fixture ingredient"):
    return RecipeIngredient(
        ingredient_id=ingredient_id,
        name=name,
        quantity=1,
        unit="pcs",
        coarse_amount=None,
        essential=essential,
        prep_note=None,
    )


def update(state, meal, rating=None, *, record_id=RECORD):
    return learn(
        state,
        household_id=HOUSEHOLD,
        record_id=record_id,
        recipe=meal,
        status=CookRecordStatus.CONFIRMED,
        rating=rating,
    )


def test_mapping_is_an_explicit_subset_of_the_authoritative_catalogue(catalogue):
    _, ingredients, recipes, _, _ = catalogue
    expected = {
        "chicken thigh": "poultry",
        "egg": "egg",
        "firm tofu": "soy",
        "tempeh": "soy",
        "canned chickpea": "legume",
        "red lentil": "legume",
        "prawn": "shellfish",
        "cod fillet": "fish",
    }
    assert {name: category for name, category in PROTEIN_INGREDIENTS.values()} == expected
    for ingredient_id, (name, _) in PROTEIN_INGREDIENTS.items():
        assert ingredients[ingredient_id].canonical_name == name
    assert len(recipes) == 48
    for meal in recipes:
        # Independent name-based oracle is safe only for these validated seed rows.
        expected_features = {
            "protein:" + expected[item.name]
            for item in meal.ingredients
            if item.essential and item.name in expected
        }
        assert protein_features(meal) == expected_features


def test_mixed_dishes_include_each_essential_protein_category_only_once():
    meal = recipe(ingredients=["unused"]).model_copy(
        update={"ingredients": [line(EGG), line(TOFU), line(TEMPEH)]}
    )
    assert protein_features(meal) == {"protein:egg", "protein:soy"}


def test_optional_protein_condiments_and_unknown_ids_are_not_guessed():
    meal = recipe(
        name="Fish chicken tofu curry",
        ingredients=["unused"],
    ).model_copy(
        update={
            "ingredients": [
                line(FISH, essential=False),
                line(SOY_SAUCE, name="soy sauce"),
                line(uid("unknown"), name="chicken thigh"),
            ]
        }
    )
    assert protein_features(meal) == frozenset()


@pytest.mark.parametrize("rating,delta", [(Rating.LIKE, 0.25), (Rating.DISLIKE, -0.25)])
def test_new_feedback_changes_scores_for_other_meals_with_the_same_protein(
    catalogue, rating, delta
):
    _, _, recipes, metadata, _ = catalogue
    eggs = [meal for meal in recipes if protein_features(meal) == {"protein:egg"}]
    assert len(eggs) >= 2
    rated = update(LearningState(HOUSEHOLD), eggs[0], rating)
    weights = taste_weights(rated)
    assert weights["protein:egg"] == delta
    # Isolate the new contribution from the cuisine/tag updates.
    protein_only = {"protein:egg": weights["protein:egg"]}
    before = score_recipe(eggs[1], [], prefs(), CookSession(), metadata, as_of=NOW)
    after = score_recipe(
        eggs[1], [], prefs(), CookSession(), metadata, as_of=NOW, taste_weights=protein_only
    )
    assert after.score.preference - before.score.preference == delta


@pytest.mark.parametrize("rating", [None, Rating.LIKE, Rating.MAYBE, Rating.DISLIKE])
def test_legacy_confirmed_meal_keeps_frozen_features_without_protein_backfill(rating):
    meal = recipe(ingredients=["unused"], taste_tags=[TasteTag.LOW_OIL]).model_copy(
        update={"ingredients": [line(EGG)]}
    )
    old_features = frozenset({"cuisine:chinese", "tag:low_oil"})
    previous = MealEvidence(RECORD, meal.id, old_features, Rating.LIKE)
    state = LearningState(HOUSEHOLD, (previous,))
    result = update(state, meal, rating)
    assert result.meals[0].features == old_features
    assert not any(feature.startswith("protein:") for feature in taste_weights(result))
    if rating is None or rating == Rating.LIKE:
        assert result is state
    # A new cooking of the same recipe uses the new feature mapping.
    new = update(result, meal, Rating.LIKE, record_id=uid("new-protein-meal"))
    assert taste_weights(new)["protein:egg"] == 0.25


def test_current_protein_evidence_rejects_an_altered_protein_recipe():
    egg = recipe(ingredients=["unused"]).model_copy(update={"ingredients": [line(EGG)]})
    fish = egg.model_copy(update={"ingredients": [line(FISH)]})
    state = update(LearningState(HOUSEHOLD), egg, Rating.LIKE)
    assert "protein:egg" in state.meals[0].features
    with pytest.raises(ValueError, match="cannot change"):
        update(state, fish, Rating.DISLIKE)


@pytest.mark.parametrize(
    "patch", [{"cuisine": Cuisine.THAI}, {"taste_tags": [TasteTag.SPICY]}, {"id": uid("other")}]
)
def test_legacy_compatibility_does_not_allow_other_recipe_feature_changes(patch):
    meal = recipe(ingredients=["unused"]).model_copy(update={"ingredients": [line(EGG)]})
    evidence = MealEvidence(RECORD, meal.id, frozenset({"cuisine:chinese"}), Rating.LIKE)
    state = LearningState(HOUSEHOLD, (evidence,))
    with pytest.raises(ValueError, match="cannot change"):
        update(state, meal.model_copy(update=patch), Rating.DISLIKE)


def test_old_evidence_with_an_unknown_extra_feature_is_not_accepted_as_legacy():
    meal = recipe(ingredients=["unused"]).model_copy(update={"ingredients": [line(EGG)]})
    evidence = MealEvidence(
        RECORD, meal.id, frozenset({"cuisine:chinese", "unknown:feature"}), Rating.LIKE
    )
    with pytest.raises(ValueError, match="cannot change"):
        update(LearningState(HOUSEHOLD, (evidence,)), meal, Rating.DISLIKE)


def test_rating_changes_and_confirmation_retries_preserve_new_protein_evidence():
    meal = recipe(ingredients=["unused"]).model_copy(update={"ingredients": [line(EGG)]})
    confirmed = update(LearningState(HOUSEHOLD), meal)
    assert taste_weights(confirmed)["protein:egg"] == 0.0625
    liked = update(confirmed, meal, Rating.LIKE)
    assert taste_weights(liked)["protein:egg"] == 0.25
    assert update(liked, meal) is liked
    assert update(liked, meal, Rating.LIKE) is liked
    maybe = update(liked, meal, Rating.MAYBE)
    assert taste_weights(maybe) == {}
    assert maybe.meals[0].features == recipe_features(meal)
    assert replace(maybe.meals[0], rating=Rating.LIKE) == liked.meals[0]
