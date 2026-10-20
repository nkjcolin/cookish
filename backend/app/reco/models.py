"""Internal recommendation inputs/results. These are not public API changes.

The service adapter must provide reviewed recipe records and authoritative
ingredient metadata. Tests can supply explicit fixtures without a database.
"""

import math
from dataclasses import dataclass, field
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.schemas.common import Allergen, Diet, Equipment, TasteTag
from app.schemas.cook import CookTag, FreshnessCheck, IngredientStatus
from app.schemas.identity import Preferences
from app.schemas.inventory import InventoryItem
from app.schemas.recipes import Recipe


class CatalogIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    canonical_name: str
    countable: StrictBool
    is_staple: StrictBool
    perishable: StrictBool
    # Required even when empty: unknown metadata is not "no allergens".
    allergens: frozenset[Allergen]
    diet_flags: frozenset[Diet]


class Candidate(Recipe):
    """A resolved recipe, including the seed/database review gate."""

    reviewed: StrictBool
    total_minutes: int = Field(ge=1)
    servings: int = Field(ge=1)

    @model_validator(mode="after")
    def valid_ingredients(self):
        if not self.ingredients:
            raise ValueError("a candidate needs ingredients")
        ids = [item.ingredient_id for item in self.ingredients]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate ingredient IDs must be unique")
        for item in self.ingredients:
            if item.quantity is not None:
                if (
                    not math.isfinite(item.quantity)
                    or item.quantity <= 0
                    or not item.unit
                    or item.coarse_amount is not None
                ):
                    raise ValueError("give a positive finite quantity and unit, or a coarse amount")
            elif not item.coarse_amount or item.unit is not None:
                raise ValueError("give a positive finite quantity and unit, or a coarse amount")
        return self


@dataclass(frozen=True)
class HardConstraints:
    allergens: frozenset[Allergen] = frozenset()
    diets: frozenset[Diet] = frozenset()
    equipment: frozenset[Equipment] = frozenset()
    strict_max_minutes: int | None = None

    @classmethod
    def from_preferences(cls, prefs: Preferences, strict_max_minutes: int | None = None):
        return cls(
            frozenset(prefs.allergens),
            frozenset(prefs.diets),
            frozenset(prefs.equipment),
            strict_max_minutes,
        )


@dataclass(frozen=True)
class CookSession:
    people: int = 2
    max_minutes: int | None = None
    max_difficulty: int | None = None
    # Explicit internal hard time bound; no existing public request field is invented.
    strict_max_minutes: int | None = None
    tags: tuple[CookTag, ...] = ()
    required_tags: frozenset[TasteTag] = frozenset()
    boosted_tags: frozenset[TasteTag] = frozenset()
    shown_recipe_ids: tuple[UUID, ...] = ()
    skipped_recipe_ids: frozenset[UUID] = frozenset()
    recent_recipe_ids: frozenset[UUID] = frozenset()
    current_recipe_id: UUID | None = None
    anchor_recipe_id: UUID | None = None

    def __post_init__(self):
        if isinstance(self.people, bool) or not isinstance(self.people, int):
            raise ValueError("people must be an integer")
        if not 1 <= self.people <= 12:
            raise ValueError("people must be between 1 and 12")
        for limit in (self.max_minutes, self.max_difficulty, self.strict_max_minutes):
            if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int)):
                raise ValueError("limits must be integers")
            if limit is not None and limit < 0:
                raise ValueError("limits cannot be negative")


@dataclass(frozen=True)
class IngredientAssessment:
    ingredient_id: UUID
    name: str
    essential: bool
    quantity: float | None
    unit: str | None
    amount: str
    status: IngredientStatus
    is_staple: bool
    known_quantity: float | None = None
    usable_batches: tuple[InventoryItem, ...] = ()
    needs_check: tuple[InventoryItem, ...] = ()
    freshness_check: tuple[FreshnessCheck, ...] = ()


@dataclass(frozen=True)
class ScoreBreakdown:
    """Raw feature values and their signed weighted contributions."""

    coverage: float
    expiry_urgency: float
    preference: float
    effort: float
    repetition: float
    unknown_essentials: float
    similarity: float
    terms: dict[str, float] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return sum(self.terms.values())


@dataclass(frozen=True)
class ScoredRecipe:
    recipe: Candidate
    ingredients: tuple[IngredientAssessment, ...]
    score: ScoreBreakdown
    preferred_variant: bool = False


@dataclass(frozen=True)
class Recommendation:
    selected: ScoredRecipe | None
    session: CookSession
    missing_essential_fallback: bool = False
    relaxable: tuple[str, ...] = ()
