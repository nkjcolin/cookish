"""Conservative name links must never imply a quantity conversion."""

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.auth import CurrentUser
from app.db import models as m
from app.schemas.inventory import InventoryItemsCreate
from app.services import inventory
from app.services.catalogue import match_exact_names
from app.services.stock_events import _new_item


def _session(*rows):
    return SimpleNamespace(execute=lambda query: rows)


def test_exact_names_normalize_unicode_case_and_whitespace_but_do_not_guess():
    egg, tofu = uuid4(), uuid4()
    session = _session((egg, "egg", ["eggs", "telur"]), (tofu, "firm tofu", ["tau kwa"]))
    assert match_exact_names(session, ["  ＥＧＧＳ  ", "TAU\t KWA", "egg", "eg", "tofu"]) == {
        "  ＥＧＧＳ  ": egg,
        "TAU\t KWA": tofu,
        "egg": egg,
    }


def test_colliding_aliases_or_canonical_names_are_not_automatically_chosen():
    first, second = uuid4(), uuid4()
    session = _session(
        (first, "soy bean", ["soy", "bean", "SOY BEAN"]),
        (second, "bean", ["soy"]),
    )
    assert match_exact_names(session, ["soy", "bean", "soy bean"]) == {"soy bean": first}


def test_empty_names_do_not_query_the_catalogue():
    assert match_exact_names(None, ["", "  "]) == {}


@pytest.mark.parametrize(
    ("explicit_id", "count", "unit", "expected_unit"),
    [
        (False, 6, "eggs", "pcs"),
        (False, 2, "pieces", "pcs"),
        (False, 500, "g", "g"),
        (False, 1, None, None),
        (False, None, None, None),
        (True, 6, None, "pcs"),
    ],
)
def test_add_links_names_without_reinterpreting_amounts(
    monkeypatch, explicit_id, count, unit, expected_unit
):
    egg = uuid4()
    session = _session((egg, "egg", ["eggs"]))
    ingredient = m.Ingredient(
        id=egg,
        canonical_name="egg",
        countable=True,
        default_unit="pcs",
        default_storage="fridge",
    )

    @contextmanager
    def transaction():
        yield session

    captured = []

    def apply(session, user, event_type, lines, key):
        captured.extend(lines)
        return _new_item(user.household_id, lines[0], ingredient, datetime(2026, 11, 7, tzinfo=UTC))

    monkeypatch.setattr(inventory, "transaction", transaction)
    monkeypatch.setattr(inventory, "apply_stock_event", apply)
    body = InventoryItemsCreate(
        items=[
            {
                "ingredient_id": egg if explicit_id else None,
                "display_name": "Custom label" if explicit_id else "Eggs",
                "count": count,
                "unit": unit,
                "storage": "freezer",
            }
        ]
    )
    result = inventory.add_items(CurrentUser(uuid4(), uuid4(), "test@example.test"), body, uuid4())
    assert result.ingredient_id == egg
    assert result.count == count and result.unit == expected_unit
    assert result.storage == "freezer"
    assert result.display_name == body.items[0].display_name
    assert body.items[0].ingredient_id == (egg if explicit_id else None)
    assert captured[0].use_default_unit == explicit_id


@pytest.mark.parametrize(
    ("name", "unit", "expected"),
    [
        ("egg", "egg", "pcs"),
        ("cabbage", "head", "pcs"),
        ("cabbage", "Cabbage", "pcs"),
        ("cabbage", "egg", "egg"),
        ("egg", "g", "g"),
        ("egg", "ml", "ml"),
        ("egg", "pack", "pack"),
        ("firm tofu", "eggs", "eggs"),
        ("firm tofu", None, None),
        (None, "eggs", "eggs"),
    ],
)
def test_count_words_do_not_convert_weights_packs_or_other_foods(name, unit, expected):
    from app.schemas.common import ItemSource
    from app.schemas.inventory import InventoryItemCreate
    from app.services.stock_events import NewBatch

    ingredient = (
        None
        if name is None
        else m.Ingredient(
            id=uuid4(),
            canonical_name=name,
            countable=True,
            default_unit="pack" if name == "firm tofu" else "pcs",
            default_storage="fridge",
        )
    )
    line = NewBatch(
        item=InventoryItemCreate(
            ingredient_id=ingredient.id if ingredient else None,
            display_name=name or "Unknown food",
            count=1,
            unit=unit,
        ),
        source=ItemSource.MANUAL,
        use_default_unit=False,
    )
    item = _new_item(uuid4(), line, ingredient, datetime(2026, 11, 7, tzinfo=UTC))
    assert item.count == 1 and item.unit == expected
