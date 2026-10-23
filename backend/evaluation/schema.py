"""Strict, versioned inputs for offline, synthetic-catalogue evaluation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.reco.shop_models import PurchaseSpec
from app.schemas.common import (
    Allergen,
    Cuisine,
    Diet,
    Equipment,
    FreshnessStatus,
    RemainingState,
    TasteTag,
)
from app.schemas.cook import CookAdjust, IngredientStatus
from app.schemas.shop import ShopAdjust


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PreferencesSpec(StrictModel):
    allergens: list[Allergen] = []
    diets: list[Diet] = []
    equipment: list[Equipment] = [Equipment.STOVE]
    cuisines: list[Cuisine] = []
    disliked_ingredients: list[str] = []
    max_cook_minutes: int | None = Field(default=60, ge=5, le=240)
    max_difficulty: int | None = Field(default=3, ge=1, le=3)
    household_size: int = Field(default=2, ge=1, le=12)
    last_cook_people: int = Field(default=2, ge=1, le=12)
    last_shop_people: int = Field(default=2, ge=1, le=12)
    last_shop_meals: int = Field(default=3, ge=1, le=7)


class IngredientSpec(StrictModel):
    countable: StrictBool
    is_staple: StrictBool
    perishable: StrictBool
    allergens: list[Allergen]
    diet_flags: list[Diet]
    purchase: PurchaseSpec


class RecipeLineSpec(StrictModel):
    ingredient: str
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = None
    coarse_amount: str | None = None
    essential: StrictBool = True


class RecipeSpec(StrictModel):
    title: str | None = None
    cuisine: Cuisine = Cuisine.CHINESE
    total_minutes: int = Field(ge=1)
    difficulty: int = Field(default=1, ge=1, le=3)
    servings: int = Field(default=2, ge=1, le=12)
    taste_tags: list[TasteTag] = []
    equipment: list[Equipment] = [Equipment.STOVE]
    reviewed: StrictBool = True
    starred: StrictBool = False
    base_recipe: str | None = None
    ingredients: list[RecipeLineSpec] = Field(min_length=1)


class Fixtures(StrictModel):
    version: Literal[1] = 1
    description: str
    as_of: datetime
    ingredients: dict[str, IngredientSpec]
    recipes: dict[str, RecipeSpec]

    @model_validator(mode="after")
    def aware_clock(self):
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("fixture as_of must include a timezone")
        return self


class BatchSpec(StrictModel):
    ingredient: str
    key: str = "one"
    count: float | None = Field(default=None, ge=0)
    unit: str | None = None
    remaining_state: RemainingState = RemainingState.ENOUGH
    freshness_status: FreshnessStatus = FreshnessStatus.OK
    confirmed_days_ago: int = 1
    acquired_days_ago: int = Field(default=2, ge=0)
    use_first_in_days: int | None = 2


class RequestSpec(StrictModel):
    people: int | None = Field(default=None, ge=1, le=12)
    meals: int | None = Field(default=None, ge=1, le=7)
    strict_max_minutes: int | None = Field(default=None, ge=0)


class ExpectedItem(StrictModel):
    packs: int | None = Field(ge=1)
    needs_check: StrictBool
    amount_contains: str | None = None


class Expectation(StrictModel):
    result: StrictBool
    # Cook: selection must belong to this nonempty allowed set on success.
    selected_any: list[str] = []
    ingredient_status: dict[str, IngredientStatus] = {}
    amounts: dict[str, str] = {}
    needs_check: list[str] | None = None
    freshness_check: list[str] | None = None
    relaxable: list[Literal["max_minutes", "tags"]] | None = None
    missing_essential_fallback: bool | None = None
    # Shop: exact basket item set and actual meal count are mandatory.
    meal_count: int | None = Field(default=None, ge=0, le=7)
    planned: list[str] | None = None
    items: dict[str, ExpectedItem] | None = None


class Refinement(StrictModel):
    patch: dict
    expect: Expectation


class Scenario(StrictModel):
    version: Literal[1] = 1
    id: str = Field(pattern=r"^DEV-(C|S)[0-9]{2}$")
    split: Literal["development"]
    mode: Literal["cook", "shop"]
    description: str = Field(min_length=15)
    categories: list[str] = Field(min_length=1)
    recipes: list[str] = Field(min_length=1)
    preferences: PreferencesSpec
    inventory: list[BatchSpec]
    request: RequestSpec
    expect: Expectation
    adjustments: list[Refinement] = Field(default_factory=list, max_length=3)
    taste_weights: dict[str, float] = {}

    @model_validator(mode="after")
    def mode_contract(self):
        if len(set(self.recipes)) != len(self.recipes):
            raise ValueError("scenario recipe aliases must be unique")
        if self.mode == "cook" and self.request.meals is not None:
            raise ValueError("Cook request cannot contain meals")
        for expectation in [self.expect, *(step.expect for step in self.adjustments)]:
            if self.mode == "cook":
                if expectation.result and not expectation.selected_any:
                    raise ValueError("successful Cook step requires selected_any")
                if any(
                    value is not None
                    for value in (
                        expectation.meal_count,
                        expectation.items,
                        expectation.planned,
                    )
                ):
                    raise ValueError("Cook expectations cannot contain Shop assertions")
                if not expectation.result and (
                    expectation.ingredient_status
                    or expectation.amounts
                    or expectation.needs_check is not None
                    or expectation.freshness_check is not None
                ):
                    raise ValueError("no-result Cook step cannot assert suggestion contents")
            else:
                if expectation.meal_count is None or expectation.items is None:
                    raise ValueError("every Shop step requires exact items and meal_count")
                if (
                    expectation.selected_any
                    or expectation.ingredient_status
                    or expectation.amounts
                    or expectation.needs_check is not None
                    or expectation.freshness_check is not None
                    or expectation.relaxable is not None
                    or expectation.missing_essential_fallback is not None
                ):
                    raise ValueError("Shop expectations cannot contain Cook assertions")
                if expectation.result != (expectation.meal_count > 0):
                    raise ValueError("Shop result must agree with meal_count")
                if not expectation.result and (expectation.items or expectation.planned):
                    raise ValueError("no-result Shop step cannot contain meals or items")
            if not expectation.result and expectation.selected_any:
                raise ValueError("no-result step cannot select a recipe")
        for step in self.adjustments:
            (CookAdjust if self.mode == "cook" else ShopAdjust).model_validate(step.patch)
        return self
