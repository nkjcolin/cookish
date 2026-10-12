"""Ingredient catalogue. STUB — Role 2 replaces the function bodies."""

from app import mock
from app.schemas.catalogue import IngredientSearchResult


def search_ingredients(q: str, limit: int) -> IngredientSearchResult:
    """Match canonical names and aliases (pg_trgm in the real version)."""
    needle = q.strip().lower()
    hits = [i for i in mock.INGREDIENTS.values() if needle in i.canonical_name]
    return IngredientSearchResult(items=hits[:limit])
