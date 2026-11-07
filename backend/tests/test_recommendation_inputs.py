"""Validate the real seed data at the database-to-engine boundary without I/O."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.db import models as m
from app.services.recommendation_inputs import (
    ingredient_metadata,
    piece_weights,
    purchase_metadata,
    recipe_candidate,
)
from seed.seed import INGREDIENTS_CSV, RECIPES_DIR, read_ingredients, read_recipes


@pytest.fixture
def rows():
    ingredients, errors = read_ingredients(INGREDIENTS_CSV)
    recipes, links, recipe_errors = read_recipes(RECIPES_DIR, ingredients)
    assert not errors and not recipe_errors
    return (
        [m.Ingredient(**r) for r in ingredients],
        [m.Recipe(**r) for r in recipes],
        [m.RecipeIngredient(**r) for r in links],
    )


def test_all_delivered_recipes_are_loadable_with_authoritative_ingredients(rows):
    ingredients, recipes, links = rows
    metadata = {r.id: ingredient_metadata(r) for r in ingredients}
    assert len(metadata) == 42
    assert len(recipes) == 48
    for recipe in recipes:
        candidate = recipe_candidate(
            recipe,
            [line for line in links if line.recipe_id == recipe.id],
            metadata,
            False,
            piece_weights(ingredients),
        )
        assert candidate.reviewed
        assert candidate.ingredients
        assert all(
            line.name == metadata[line.ingredient_id].canonical_name
            for line in candidate.ingredients
        )
    for ingredient in ingredients:
        pack = purchase_metadata(ingredient)
        assert pack.shelf_life_days == getattr(
            ingredient, f"shelf_life_days_{ingredient.default_storage}"
        )


def test_missing_allergen_metadata_fails_instead_of_becoming_allergen_free(rows):
    ingredient = rows[0][0]
    ingredient.allergen_tags = None
    with pytest.raises(ValidationError):
        ingredient_metadata(ingredient)


def test_partial_pack_metadata_is_not_guessed(rows):
    ingredient = rows[0][0]
    ingredient.purchase_unit_size = None
    with pytest.raises(ValidationError):
        purchase_metadata(ingredient)


def test_unknown_pack_size_and_shelf_life_stay_unknown(rows):
    water = next(r for r in rows[0] if r.canonical_name == "water")
    pack = purchase_metadata(water)
    assert not pack.buyable
    assert pack.purchase_unit_size is None
    assert pack.shelf_life_days is None


def test_missing_active_time_is_reported_not_fabricated(rows):
    ingredients, recipes, links = rows
    recipe = recipes[0]
    recipe.active_minutes = None
    with pytest.raises(ValueError, match="active_minutes"):
        recipe_candidate(
            recipe, links, {r.id: ingredient_metadata(r) for r in ingredients}, False, {}
        )


def test_seeded_pack_sizes_preserve_measures_and_decimal_values(rows):
    chickpeas = next(r for r in rows[0] if r.canonical_name == "canned chickpea")
    chickpeas.purchase_unit_size = Decimal("240.5")
    pack = purchase_metadata(chickpeas)
    assert pack.purchase_unit_size == 240.5
    assert pack.purchase_unit_measure == "g"


def test_gram_amounts_of_piece_counted_foods_become_quarter_pieces(rows):
    ingredients, recipes, links = rows
    by_name = {r.canonical_name: r for r in ingredients}
    recipe = recipes[0]
    lines = [
        m.RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=by_name[name].id,
            quantity=Decimal(q),
            unit=unit,
            essential=True,
        )
        for name, q, unit in [
            ("cabbage", "200", "g"),  # 800 g each: exactly a quarter
            ("tomato", "100", "g"),  # 120 g each: 0.83, rounded up to 1
            ("egg", "2", "pcs"),  # already in pieces
            ("garlic", "10", "g"),  # kept as a state: grams stay grams
        ]
    ]
    metadata = {r.id: ingredient_metadata(r) for r in ingredients}
    candidate = recipe_candidate(recipe, lines, metadata, False, piece_weights(ingredients))
    amounts = {line.name: (line.quantity, line.unit) for line in candidate.ingredients}
    assert amounts == {
        "cabbage": (0.25, "pcs"),
        "tomato": (1, "pcs"),
        "egg": (2, "pcs"),
        "garlic": (10, "g"),
    }
