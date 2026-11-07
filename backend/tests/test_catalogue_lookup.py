"""Known inventory links resolve by identity even after the household renames a batch."""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from app.db import models as m
from app.services import catalogue


def test_known_id_resolves_even_when_display_name_is_not_a_catalogue_name(monkeypatch):
    egg_id = uuid4()
    egg = m.Ingredient(
        id=egg_id,
        canonical_name="egg",
        category="egg",
        countable=True,
        default_unit="pcs",
        default_storage="fridge",
        is_staple=False,
    )
    seen = []

    def get(model, ingredient_id):
        seen.append((model, ingredient_id))
        return egg if ingredient_id == egg_id else None

    @contextmanager
    def transaction():
        yield SimpleNamespace(get=get)

    monkeypatch.setattr(catalogue, "transaction", transaction)
    result = catalogue.search_ingredients("Grandma's breakfast box", 1, ingredient_id=egg_id)
    assert seen == [(m.Ingredient, egg_id)]
    assert [(item.id, item.canonical_name, item.default_unit) for item in result.items] == [
        (egg_id, "egg", "pcs")
    ]
    # An unknown explicit identity must not fall back to an unrelated fuzzy name match.
    assert catalogue.search_ingredients("egg", 1, ingredient_id=uuid4()).items == []
