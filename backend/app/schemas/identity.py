from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from app.schemas.common import Allergen, Cuisine, Diet, Equipment, RequestModel, ResponseModel

People = Annotated[int, Field(ge=1, le=12)]
Meals = Annotated[int, Field(ge=1, le=7)]
Difficulty = Annotated[int, Field(ge=1, le=3)]


class User(ResponseModel):
    id: UUID
    email: str
    display_name: str | None


class Household(ResponseModel):
    id: UUID
    name: str


class PreferencesUpdate(RequestModel):
    """Everything the user sets in onboarding or settings. Replaces the stored values."""

    allergens: list[Allergen] = Field(default_factory=list)
    diets: list[Diet] = Field(default_factory=list)
    equipment: list[Equipment] = Field(default_factory=list)
    cuisines: list[Cuisine] = Field(default_factory=list)
    disliked_ingredient_ids: list[UUID] = Field(default_factory=list)
    max_cook_minutes: Annotated[int, Field(ge=5, le=240)] | None = None
    max_difficulty: Difficulty | None = None
    household_size: People = 2


class Preferences(ResponseModel):
    allergens: list[Allergen]
    diets: list[Diet]
    equipment: list[Equipment]
    cuisines: list[Cuisine]
    disliked_ingredient_ids: list[UUID]
    max_cook_minutes: int | None
    max_difficulty: int | None
    household_size: int
    # Remembered by Cook and Shop; not editable through PUT /household/preferences.
    last_cook_people: int
    last_shop_people: int
    last_shop_meals: int
    updated_at: datetime


class Me(ResponseModel):
    user: User
    household: Household
    preferences: Preferences | None = Field(
        description="null until onboarding is completed; the frontend shows onboarding then."
    )
