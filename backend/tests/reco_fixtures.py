"""Explicit synthetic recipe fixtures, never authoritative seed metadata."""

from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from app.clock import SINGAPORE
from app.reco.models import Candidate, CatalogIngredient
from app.reco.shop_models import PurchaseSpec
from app.schemas.common import (
    Allergen,
    Cuisine,
    Diet,
    Equipment,
    FreshnessStatus,
    IngredientCategory,
    ItemSource,
    RemainingState,
    Storage,
)
from app.schemas.identity import Preferences
from app.schemas.inventory import InventoryItem
from app.schemas.recipes import RecipeIngredient

NOW = datetime(2026, 10, 20, 12, tzinfo=SINGAPORE)


def uid(name):
    return uuid5(NAMESPACE_URL, "cookish-reco-test/" + name)


def metadata(name, *, allergens=(), diets=(), countable=False, staple=False, perishable=True):
    # Explicit synthetic metadata, never an authoritative ingredient catalogue.
    return CatalogIngredient(
        id=uid(name),
        canonical_name=name,
        allergens=frozenset(allergens),
        diet_flags=frozenset(diets),
        countable=countable,
        is_staple=staple,
        perishable=perishable,
    )


CATALOGUE = {
    meta.id: meta
    for meta in [
        metadata("egg", allergens=[Allergen.EGG], diets=[Diet.VEGETARIAN], countable=True),
        metadata("tomato", diets=[Diet.VEGETARIAN, Diet.VEGAN]),
        metadata("firm tofu", allergens=[Allergen.SOY], diets=[Diet.VEGETARIAN, Diet.VEGAN]),
        metadata("uncooked rice", diets=[Diet.VEGETARIAN, Diet.VEGAN], perishable=False),
        metadata("water", diets=[Diet.VEGETARIAN, Diet.VEGAN], staple=True, perishable=False),
        metadata("salt", diets=[Diet.VEGETARIAN, Diet.VEGAN], staple=True, perishable=False),
        metadata("canola oil", diets=[Diet.VEGETARIAN, Diet.VEGAN], staple=True, perishable=False),
        metadata("spring onion", diets=[Diet.VEGETARIAN, Diet.VEGAN]),
    ]
}


def prefs(**changes):
    values = dict(
        allergens=[],
        diets=[],
        equipment=[Equipment.STOVE],
        cuisines=[],
        disliked_ingredient_ids=[],
        max_cook_minutes=60,
        max_difficulty=3,
        household_size=2,
        last_cook_people=2,
        last_shop_people=2,
        last_shop_meals=3,
        updated_at=NOW,
    )
    values.update(changes)
    return Preferences(**values)


def recipe(name="egg-meal", ingredients=("egg",), **changes):
    values = dict(
        id=uid(name),
        title=name,
        cuisine=Cuisine.CHINESE,
        total_minutes=30,
        active_minutes=20,
        difficulty=1,
        servings=2,
        taste_tags=[],
        starred=False,
        base_recipe_id=None,
        variant_label=None,
        equipment=[Equipment.STOVE],
        ingredients=[
            RecipeIngredient(
                ingredient_id=uid(ingredient),
                name=ingredient,
                quantity=3 if ingredient == "egg" else 300,
                unit="pcs" if ingredient == "egg" else "g",
                coarse_amount=None,
                essential=True,
                prep_note=None,
            )
            for ingredient in ingredients
        ],
        steps=["Fixture method; not a public recipe."],
        reviewed=True,
    )
    values.update(changes)
    return Candidate(**values)


def batch(name="egg", key="one", **changes):
    meta = CATALOGUE[uid(name)]
    values = dict(
        id=uid("batch/" + name + "/" + key),
        ingredient_id=meta.id,
        display_name=name,
        category=IngredientCategory.OTHER,
        countable=meta.countable,
        count=3 if meta.countable else None,
        unit="pcs" if meta.countable else None,
        remaining_state=RemainingState.ENOUGH,
        storage=Storage.FRIDGE,
        source=ItemSource.MANUAL,
        acquired_at=NOW.date() - timedelta(days=1),
        label_date=None,
        label_date_kind=None,
        est_use_first_date=NOW.date() + timedelta(days=2),
        freshness_status=FreshnessStatus.OK,
        freshness_confirmed_at=None,
        last_confirmed_at=NOW - timedelta(days=1),
        revision=1,
    )
    values.update(changes)
    return InventoryItem(**values)


PURCHASES = {
    ingredient_id: PurchaseSpec(
        category=IngredientCategory.OTHER,
        buyable=meta.canonical_name != "water",
        purchase_unit="tray" if meta.countable else None,
        purchase_unit_size=10 if meta.countable else None,
        purchase_unit_measure="pcs" if meta.countable else None,
        shelf_life_days=28 if meta.countable else 3,
    )
    for ingredient_id, meta in CATALOGUE.items()
}
