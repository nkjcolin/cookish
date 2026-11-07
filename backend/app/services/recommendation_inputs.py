"""Database reads for Role 5, using the caller's existing transaction.

SqlRecommendationRepository delegates its catalogue, preference and inventory
reads here. Session, evidence and confirmation persistence live in that adapter.
"""

import math
from collections import defaultdict
from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as m
from app.reco.models import Candidate, CatalogIngredient
from app.reco.shop_models import PurchaseSpec
from app.schemas.identity import Preferences
from app.schemas.inventory import InventoryItem
from app.schemas.recipes import RecipeIngredient
from app.services.freshness import PERISHABLE_CATEGORIES
from app.services.identity import get_preferences
from app.services.recommendation_repository import RecipeCatalogue
from app.services.stock_events import get_inventory_snapshot


class SqlRecommendationInputs:
    """Pass only the authenticated household ID, as with Role 2's read services.

    No commits, new transactions, inventory writes, or cached household state.
    The SQL repository delegates these three methods to this reader.
    """

    def __init__(self, session: Session):
        self.session = session

    def preferences(self, household_id: UUID) -> Preferences:
        return get_preferences(self.session, household_id)

    def inventory(self, household_id: UUID) -> list[InventoryItem]:
        return get_inventory_snapshot(self.session, household_id)

    def catalogue(self, household_id: UUID) -> RecipeCatalogue:
        ingredients = list(self.session.scalars(select(m.Ingredient).order_by(m.Ingredient.id)))
        metadata = {row.id: ingredient_metadata(row) for row in ingredients}
        purchases = {row.id: purchase_metadata(row) for row in ingredients}
        weights = piece_weights(ingredients)
        recipes = list(
            self.session.scalars(
                select(m.Recipe).where(m.Recipe.reviewed.is_(True)).order_by(m.Recipe.id)
            )
        )
        lines = defaultdict(list)
        for line in self.session.scalars(
            select(m.RecipeIngredient)
            .join(m.Recipe, m.Recipe.id == m.RecipeIngredient.recipe_id)
            .where(m.Recipe.reviewed.is_(True))
            .order_by(m.RecipeIngredient.recipe_id, m.RecipeIngredient.ingredient_id)
        ):
            lines[line.recipe_id].append(line)

        # Ratings/cooked/skipped do not change stars. Resolve the last star event
        # separately for each recipe, scoped to this household. UUID is only a
        # deterministic tie-break for legacy events with identical timestamps.
        stars: dict[UUID, bool] = {}
        for recipe_id, signal in self.session.execute(
            select(m.RecipeFeedback.recipe_id, m.RecipeFeedback.signal)
            .where(
                m.RecipeFeedback.household_id == household_id,
                m.RecipeFeedback.signal.in_(("starred", "unstarred")),
            )
            .order_by(m.RecipeFeedback.created_at.desc(), m.RecipeFeedback.id.desc())
        ):
            stars.setdefault(recipe_id, signal == "starred")

        return RecipeCatalogue(
            recipes=tuple(
                recipe_candidate(row, lines[row.id], metadata, stars.get(row.id, False), weights)
                for row in recipes
            ),
            ingredients=metadata,
            purchases=purchases,
        )


def ingredient_metadata(row: m.Ingredient) -> CatalogIngredient:
    """Validate authoritative metadata; never replace missing fields with empty sets."""
    return CatalogIngredient(
        id=row.id,
        canonical_name=row.canonical_name,
        countable=row.countable,
        is_staple=row.is_staple,
        perishable=row.category in PERISHABLE_CATEGORIES,
        allergens=row.allergen_tags,
        diet_flags=row.diet_flags,
    )


def purchase_metadata(row: m.Ingredient) -> PurchaseSpec:
    """Apply Role 2's CSV convention: no purchase unit means not buyable.

    Counted ingredients are bought in the unit the kitchen counts them in (seed.py
    checks this), so a pack count always converts into stock.
    """
    return PurchaseSpec(
        category=row.category,
        buyable=bool(row.purchase_unit),
        purchase_unit=row.purchase_unit,
        purchase_unit_size=row.purchase_unit_size,
        purchase_unit_measure=row.purchase_unit_measure,
        shelf_life_days=getattr(row, f"shelf_life_days_{row.default_storage}"),
    )


def piece_weights(ingredients) -> dict[UUID, Decimal]:
    """grams_per_piece for the ingredients counted in pieces but used by the gram."""
    return {row.id: row.grams_per_piece for row in ingredients if row.grams_per_piece}


def in_pieces(quantity: Decimal, grams_per_piece: Decimal) -> Decimal:
    """Grams as pieces, rounded up to a quarter: a recipe takes ¼ of a cabbage, not 0.23."""
    return Decimal(math.ceil(quantity / grams_per_piece * 4)) / 4


def _ingredient(
    line: m.RecipeIngredient, name: str, weights: Mapping[UUID, Decimal]
) -> RecipeIngredient:
    quantity, unit = line.quantity, line.unit
    weight = weights.get(line.ingredient_id)
    if weight is not None and quantity is not None and unit == "g":
        quantity, unit = in_pieces(quantity, weight), "pcs"
    return RecipeIngredient(
        ingredient_id=line.ingredient_id,
        name=name,
        quantity=quantity,
        unit=unit,
        coarse_amount=line.coarse_amount,
        essential=line.essential,
        prep_note=line.prep_note,
    )


def recipe_candidate(
    row: m.Recipe,
    lines: list[m.RecipeIngredient],
    metadata: dict[UUID, CatalogIngredient],
    starred: bool,
    weights: Mapping[UUID, Decimal],
) -> Candidate:
    """`weights` is piece_weights(): those ingredients' gram amounts become pieces, so that
    Cook, Shop and the recipe page compare and show them in the kitchen's own unit."""
    # The API requires active_minutes, although the seed format permits null.
    # Refuse incomplete runtime content rather than inventing an active time.
    if row.active_minutes is None:
        raise ValueError(f"Recipe {row.id} needs active_minutes before recommendation loading")
    return Candidate(
        id=row.id,
        title=row.title,
        cuisine=row.cuisine,
        total_minutes=row.total_minutes,
        active_minutes=row.active_minutes,
        difficulty=row.difficulty,
        servings=row.servings,
        taste_tags=row.taste_tags,
        starred=starred,
        base_recipe_id=row.base_recipe_id,
        variant_label=row.variant_label,
        equipment=row.equipment,
        ingredients=[
            _ingredient(line, metadata[line.ingredient_id].canonical_name, weights)
            for line in lines
        ],
        steps=row.steps,
        reviewed=row.reviewed,
    )
