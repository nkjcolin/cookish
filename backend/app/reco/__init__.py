"""Pure recommendation functions; persistence belongs in app.services."""

from app.reco.cook import (
    adjust,
    filter_recipes,
    new_session,
    recipe_features,
    score_recipe,
    skip_current,
    suggest,
    to_suggestion,
)
from app.reco.learning import learn, taste_weights
from app.reco.shop import adjust_shop, new_shop_session, plan_shop, shopping_list, to_basket

__all__ = [
    "adjust",
    "adjust_shop",
    "filter_recipes",
    "learn",
    "new_session",
    "new_shop_session",
    "plan_shop",
    "recipe_features",
    "score_recipe",
    "skip_current",
    "shopping_list",
    "suggest",
    "taste_weights",
    "to_basket",
    "to_suggestion",
]
