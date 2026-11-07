"""Shop: a basket for N people and M meals, then confirm what was actually bought."""

from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import IngredientCategory, RequestModel, ResponseModel
from app.schemas.identity import Meals, People
from app.schemas.recipes import RecipeSummary
from app.schemas.stock_events import InventoryChange


class ShopTag(StrEnum):
    MORE_VEGETABLES = "more_vegetables"
    LONGER_LASTING = "longer_lasting"
    COVER_MORE_MEALS = "cover_more_meals"


class BasketStatus(StrEnum):
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"
    ABANDONED = "abandoned"


class ShopSessionCreate(RequestModel):
    people: People | None = Field(default=None, description="Defaults to the last choice.")
    meals: Meals | None = Field(default=None, description="Defaults to the last choice.")
    recipe_ids: list[UUID] = Field(
        default_factory=list,
        max_length=7,
        description="Recipes the plan must include, such as the one being viewed; the rest"
        " are chosen as usual. meals is raised to at least this many.",
    )


class ShopAdjust(RequestModel):
    tags: list[ShopTag] = Field(default_factory=list)
    people: People | None = None
    meals: Meals | None = None

    @model_validator(mode="after")
    def _changes_something(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("an adjustment must change at least one field")
        return self


class BasketItem(ResponseModel):
    id: UUID
    ingredient_id: UUID
    name: str
    category: IngredientCategory
    amount: str = Field(description='Display text, e.g. "2 packs" or "1 bunch".')
    suggested_packs: int | None = Field(
        description="null for state-tracked ingredients, and for counted ones whose need is"
        " uncertain. Confirming a bought line without packs records it with an unknown amount."
    )
    needs_check: bool = Field(description='Stock is uncertain: show "Check at home".')


class Basket(ResponseModel):
    id: UUID
    session_id: UUID
    people: int
    meals: int
    status: BasketStatus
    applied_tags: list[ShopTag]
    planned_meals: list[RecipeSummary] = Field(description="Example meals the basket covers.")
    items: list[BasketItem]


class BoughtLine(RequestModel):
    basket_item_id: UUID
    bought: bool
    packs: Annotated[int, Field(ge=1, le=50)] | None = Field(
        default=None, description="Defaults to the suggested number."
    )


class BasketConfirm(RequestModel):
    lines: Annotated[list[BoughtLine], Field(min_length=1)]


class BasketConfirmResult(InventoryChange):
    basket_id: UUID
