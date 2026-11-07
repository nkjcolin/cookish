"""Real catalogue -> engine integration, using the disposable Postgres fixture."""

import math
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app import clock
from app.auth import DEV_CLAIMS
from app.db import models as m
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.reco import new_session, new_shop_session, plan_shop, suggest
from app.reco.cook import filter_recipes
from app.reco.models import HardConstraints
from app.reco.shop import shopping_list
from app.schemas.common import Allergen, Diet, Equipment
from app.services.identity import get_or_create_user
from app.services.recommendation_inputs import SqlRecommendationInputs
from seed.demo import DEMO_HOUSEHOLD_ID, seed_demo
from seed.seed import seed


@pytest.fixture
def seeded():
    seed()
    seed_demo()
    return DEMO_HOUSEHOLD_ID


def test_seeded_catalogue_runs_both_engines_and_preserves_purchase_uncertainty(seeded):
    with transaction() as s:
        reader = SqlRecommendationInputs(s)
        catalogue = reader.catalogue(seeded)
        prefs, inventory = reader.preferences(seeded), reader.inventory(seeded)
        assert len(catalogue.recipes) == 48
        assert len(catalogue.ingredients) == 42
        assert sum(r.base_recipe_id is not None for r in catalogue.recipes) == 20
        names = {i.canonical_name: i.id for i in catalogue.ingredients.values()}
        assert not catalogue.purchases[names["water"]].buyable
        assert not catalogue.purchases[names["cooked rice"]].buyable
        tomato = catalogue.purchases[names["tomato"]]
        assert tomato.purchase_unit_measure == "pcs"  # bought by the piece, like it is kept
        assert all(r.reviewed and not r.starred for r in catalogue.recipes)

        result = suggest(
            catalogue.recipes,
            inventory,
            prefs,
            new_session(prefs),
            catalogue.ingredients,
            as_of=clock.now(),
        )
        assert result.selected is not None
        assert result.selected.recipe.id in {r.id for r in catalogue.recipes}
        plan = plan_shop(
            catalogue.recipes,
            inventory,
            prefs,
            new_shop_session(prefs),
            catalogue.ingredients,
            catalogue.purchases,
            as_of=clock.now(),
        )
        assert len(plan.planned_meals) == prefs.last_shop_meals
        assert all(line.ingredient_id in catalogue.ingredients for line in plan.items)
        assert names["water"] not in {line.ingredient_id for line in plan.items}
        # Recipes weigh tomatoes in grams; grams_per_piece turns that into whole tomatoes to buy.
        tomato_meal = next(
            r
            for r in catalogue.recipes
            if any(line.ingredient_id == names["tomato"] for line in r.ingredients)
        )
        needed = next(
            line for line in tomato_meal.ingredients if line.ingredient_id == names["tomato"]
        )
        assert needed.unit == "pcs"
        shopping = shopping_list(
            [tomato_meal],
            [],
            catalogue.ingredients,
            catalogue.purchases,
            tomato_meal.servings,
            as_of=clock.now(),
        )
        tomato_line = next(line for line in shopping.items if line.ingredient_id == names["tomato"])
        assert not tomato_line.needs_check
        assert tomato_line.suggested_packs == math.ceil(needed.quantity)


def test_unreviewed_recipes_never_enter_runtime_catalogue(seeded):
    with transaction() as s:
        recipe = s.scalars(select(m.Recipe).order_by(m.Recipe.id)).first()
        excluded_id = recipe.id
        recipe.reviewed = False
        s.flush()
        catalogue = SqlRecommendationInputs(s).catalogue(seeded)
        assert len(catalogue.recipes) == 47
        assert excluded_id not in {r.id for r in catalogue.recipes}


def test_optional_allergens_and_diets_come_from_current_ingredient_rows(seeded):
    with transaction() as s:
        line = s.scalars(
            select(m.RecipeIngredient).where(m.RecipeIngredient.essential.is_(False))
        ).first()
        assert line is not None
        ingredient = s.get(m.Ingredient, line.ingredient_id)
        ingredient.allergen_tags = ["peanut"]
        ingredient.diet_flags = []
        # Deliberately leave the recipe's cached aggregates unchanged.
        s.flush()
        catalogue = SqlRecommendationInputs(s).catalogue(seeded)
        recipe = next(r for r in catalogue.recipes if r.id == line.recipe_id)
        assert not filter_recipes(
            [recipe],
            HardConstraints(allergens=frozenset({Allergen.PEANUT}), equipment=frozenset(Equipment)),
            catalogue.ingredients,
        )
        assert not filter_recipes(
            [recipe],
            HardConstraints(diets=frozenset({Diet.VEGAN}), equipment=frozenset(Equipment)),
            catalogue.ingredients,
        )


def test_household_reads_do_not_leak_inventory_preferences_or_stars(seeded):
    with transaction() as s:
        other = get_or_create_user(s, uuid4(), "other@example.test")
        s.add(m.Preferences(household_id=other.household_id, household_size=5))
        recipe_id = s.scalar(select(m.Recipe.id).order_by(m.Recipe.id))
        now = clock.now()
        demo_user = UUID(DEV_CLAIMS["sub"])
        for household, user, signal, offset in (
            (seeded, demo_user, "starred", 0),
            (seeded, demo_user, "unstarred", 1),
            (seeded, demo_user, "like", 2),
            (other.household_id, other.user_id, "starred", 3),
        ):
            s.add(
                m.RecipeFeedback(
                    household_id=household,
                    user_id=user,
                    recipe_id=recipe_id,
                    signal=signal,
                    created_at=now + timedelta(seconds=offset),
                )
            )
        s.flush()
        reader = SqlRecommendationInputs(s)
        assert len(reader.inventory(seeded)) == 8
        assert reader.inventory(other.household_id) == []
        assert reader.preferences(seeded).household_size == 2
        assert reader.preferences(other.household_id).household_size == 5
        assert not next(r for r in reader.catalogue(seeded).recipes if r.id == recipe_id).starred
        assert next(
            r for r in reader.catalogue(other.household_id).recipes if r.id == recipe_id
        ).starred


def test_reader_uses_uncommitted_caller_state_and_does_not_commit(seeded):
    with pytest.raises(RuntimeError, match="rollback"):
        with transaction() as s:
            prefs = s.get(m.Preferences, seeded)
            prefs.household_size = 7
            s.flush()
            assert SqlRecommendationInputs(s).preferences(seeded).household_size == 7
            raise RuntimeError("rollback")
    with transaction() as s:
        assert SqlRecommendationInputs(s).preferences(seeded).household_size == 2


def test_first_use_has_empty_inventory_and_requires_onboarding():
    with transaction() as s:
        user = get_or_create_user(s, uuid4(), "new@example.test")
        reader = SqlRecommendationInputs(s)
        assert reader.inventory(user.household_id) == []
        with pytest.raises(ApiError) as error:
            reader.preferences(user.household_id)
        assert error.value.code == ErrorCode.NOT_FOUND
