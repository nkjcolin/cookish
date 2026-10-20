"""Internal Shop inputs; purchase metadata is supplied by the catalogue adapter."""

import math
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.reco.models import Candidate
from app.schemas.common import IngredientCategory
from app.schemas.shop import ShopTag


class PurchaseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: IngredientCategory
    # Explicit catalogue decision, e.g. household tap water is not a purchase.
    buyable: StrictBool
    purchase_unit: str | None
    purchase_unit_size: float | None
    purchase_unit_measure: str | None
    # Estimate at default storage, NOT a food safety guarantee.
    shelf_life_days: int | None = Field(ge=1)

    @model_validator(mode="after")
    def valid_pack(self):
        fields = (self.purchase_unit, self.purchase_unit_size, self.purchase_unit_measure)
        if any(value is not None for value in fields):
            if (
                not self.purchase_unit
                or not self.purchase_unit_measure
                or self.purchase_unit_size is None
                or not math.isfinite(self.purchase_unit_size)
                or self.purchase_unit_size <= 0
            ):
                raise ValueError("supply a complete positive pack definition, or all null")
        return self


@dataclass(frozen=True)
class ShopSession:
    people: int = 2
    meals: int = 3
    tags: tuple[ShopTag, ...] = ()
    strict_max_minutes: int | None = None

    def __post_init__(self):
        for name, value, maximum in (("people", self.people, 12), ("meals", self.meals, 7)):
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be an integer between 1 and {maximum}")
        limit = self.strict_max_minutes
        if limit is not None and (
            isinstance(limit, bool) or not isinstance(limit, int) or limit < 0
        ):
            raise ValueError("strict time limit must be a nonnegative integer")


@dataclass(frozen=True)
class Purchase:
    ingredient_id: UUID
    name: str
    category: IngredientCategory
    amount: str
    suggested_packs: int | None
    needs_check: bool
    # Fraction of a pack left over; different physical units are never added.
    surplus_packs: float = 0.0


@dataclass(frozen=True)
class ShoppingList:
    items: tuple[Purchase, ...]
    confirmed_at_home: int


@dataclass(frozen=True)
class ShopPlan:
    session: ShopSession
    planned_meals: tuple[Candidate, ...]
    items: tuple[Purchase, ...]
    score_terms: dict[str, float]

    @property
    def score(self) -> float:
        return sum(self.score_terms.values())
