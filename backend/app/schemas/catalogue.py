from uuid import UUID

from app.schemas.common import IngredientCategory, ResponseModel, Storage


class Ingredient(ResponseModel):
    id: UUID
    canonical_name: str
    category: IngredientCategory
    countable: bool
    default_unit: str | None
    default_storage: Storage
    is_staple: bool


class IngredientSearchResult(ResponseModel):
    items: list[Ingredient]
