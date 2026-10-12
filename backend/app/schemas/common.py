"""Base classes and the closed vocabularies shared across the contract.

Changing a value here changes the contract for every role: the frontend's generated
types, the ingredient and recipe seed data, and the recommendation filters all use
these exact strings.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    """Base for request bodies: unknown fields are rejected instead of silently dropped."""

    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Allergen(StrEnum):
    PEANUT = "peanut"
    TREE_NUT = "tree_nut"
    MILK = "milk"
    EGG = "egg"
    FISH = "fish"
    SHELLFISH = "shellfish"
    SOY = "soy"
    GLUTEN = "gluten"
    SESAME = "sesame"


class Diet(StrEnum):
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    PESCATARIAN = "pescatarian"
    HALAL = "halal"
    NO_PORK = "no_pork"
    NO_BEEF = "no_beef"


class Equipment(StrEnum):
    STOVE = "stove"
    OVEN = "oven"
    MICROWAVE = "microwave"
    RICE_COOKER = "rice_cooker"
    AIR_FRYER = "air_fryer"
    STEAMER = "steamer"
    BLENDER = "blender"


class Cuisine(StrEnum):
    CHINESE = "chinese"
    MALAY = "malay"
    INDIAN = "indian"
    WESTERN = "western"
    JAPANESE = "japanese"
    KOREAN = "korean"
    THAI = "thai"
    OTHER = "other"


class IngredientCategory(StrEnum):
    PRODUCE = "produce"
    MEAT = "meat"
    SEAFOOD = "seafood"
    DAIRY = "dairy"
    EGG = "egg"
    GRAIN = "grain"
    PANTRY = "pantry"
    CONDIMENT = "condiment"
    FROZEN = "frozen"
    OTHER = "other"


class Storage(StrEnum):
    PANTRY = "pantry"
    FRIDGE = "fridge"
    FREEZER = "freezer"


class RemainingState(StrEnum):
    ENOUGH = "enough"
    LOW = "low"
    OUT = "out"
    UNKNOWN = "unknown"


class ItemSource(StrEnum):
    MANUAL = "manual"
    RECEIPT = "receipt"
    PHOTO = "photo"
    VOICE = "voice"
    SHOP_CONFIRM = "shop_confirm"


class LabelDateKind(StrEnum):
    USE_BY = "use_by"
    BEST_BEFORE = "best_before"


class FreshnessStatus(StrEnum):
    """Result of the freshness gate for one batch (SPEC B5)."""

    OK = "ok"
    USE_SOON = "use_soon"
    CHECK = "check"
    EXPIRED = "expired"


class TasteTag(StrEnum):
    """Describes a recipe. Role 5 owns the list; recipes in seed/ may only use these."""

    LIGHT = "light"
    RICH = "rich"
    SPICY = "spicy"
    SOUPY = "soupy"
    LOW_OIL = "low_oil"
    HIGH_PROTEIN = "high_protein"
    VEGETABLE_RICH = "vegetable_rich"
