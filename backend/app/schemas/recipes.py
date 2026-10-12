from uuid import UUID

from pydantic import Field

from app.schemas.common import Cuisine, Equipment, RequestModel, ResponseModel, TasteTag


class RecipeSummary(ResponseModel):
    id: UUID
    title: str
    cuisine: Cuisine
    total_minutes: int
    difficulty: int = Field(ge=1, le=3)
    servings: int
    taste_tags: list[TasteTag]
    starred: bool


class RecipeIngredient(ResponseModel):
    ingredient_id: UUID
    name: str
    quantity: float | None
    unit: str | None
    coarse_amount: str | None = Field(description='e.g. "half a cabbage".')
    essential: bool
    prep_note: str | None


class Recipe(RecipeSummary):
    """Amounts are for `servings` people; Cook suggestions carry scaled amounts instead."""

    base_recipe_id: UUID | None
    variant_label: str | None
    active_minutes: int
    equipment: list[Equipment]
    ingredients: list[RecipeIngredient]
    steps: list[str]


class StarUpdate(RequestModel):
    starred: bool


class StarResult(ResponseModel):
    recipe_id: UUID
    starred: bool
