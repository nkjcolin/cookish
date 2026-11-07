"""Reviewed AI/manual names become usable catalogue inventory without fuzzy guesses."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.db import models as m
from app.db.session import transaction
from app.main import app

client = TestClient(app)


def _ingredient(name, aliases=(), **kwargs):
    ingredient_id = uuid4()
    with transaction() as session:
        session.add(
            m.Ingredient(
                id=ingredient_id,
                canonical_name=name,
                aliases=list(aliases),
                category="egg",
                countable=True,
                default_unit="pcs",
                default_storage="fridge",
                **kwargs,
            )
        )
    return ingredient_id


def _add(items, key=None):
    return client.post(
        "/api/inventory/items",
        json={"source": "voice", "items": items},
        headers={"Idempotency-Key": str(key or uuid4())},
    )


def test_reviewed_egg_alias_is_linked_and_undo_removes_the_new_batch():
    egg = _ingredient("egg", ["eggs", "telur"])
    response = _add([{"display_name": " ＥＧＧＳ ", "count": 6, "unit": "pcs"}])
    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["ingredient_id"] == str(egg) and item["countable"]
    assert (item["count"], item["unit"], item["source"]) == (6, "pcs", "voice")
    group = client.get("/api/inventory").json()["groups"][0]
    assert group["ingredient_id"] == str(egg)
    undo = client.post(
        f"/api/stock-events/{response.json()['event']['id']}/undo",
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert undo.status_code == 200 and undo.json()["conflicts"] == []
    assert client.get("/api/inventory").json()["groups"] == []


def test_unknown_and_ambiguous_names_remain_free_text():
    _ingredient("egg", ["shared"])
    _ingredient("duck egg", ["shared", "egg"])
    response = _add([{"display_name": name} for name in ["egg", "shared", "eggplant", "eg"]])
    assert response.status_code == 201
    assert all(item["ingredient_id"] is None for item in response.json()["items"])


def test_explicit_id_wins_over_the_name_and_an_invalid_id_is_not_replaced():
    _ingredient("egg")
    duck = _ingredient("duck egg")
    response = _add([{"ingredient_id": str(duck), "display_name": "egg", "count": 2}])
    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["ingredient_id"] == str(duck) and item["unit"] == "pcs"
    missing = _add([{"ingredient_id": str(uuid4()), "display_name": "egg"}])
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "count,unit", [(None, None), (1, None), (500, "g"), (1, "ml"), (1, "pack")]
)
def test_name_matching_preserves_exact_amount_and_unit(count, unit):
    egg = _ingredient("egg")
    response = _add([{"display_name": "egg", "count": count, "unit": unit}])
    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["ingredient_id"] == str(egg)
    assert item["count"] == count and item["unit"] == unit


@pytest.mark.parametrize("unit", ["eggs", "egg", "pieces", "piece", "PCS"])
def test_reviewed_six_eggs_uses_the_catalogue_count_unit(unit):
    egg = _ingredient("egg", ["eggs"])
    response = _add([{"display_name": "Eggs", "count": 6, "unit": unit}])
    assert response.status_code == 201
    item = response.json()["items"][0]
    assert (item["ingredient_id"], item["count"], item["unit"]) == (str(egg), 6, "pcs")


def test_retry_keeps_original_link_when_the_catalogue_alias_changes():
    egg = _ingredient("egg", ["telur"])
    key = uuid4()
    request = [{"display_name": "telur", "count": 6, "unit": "pcs"}]
    first = _add(request, key)
    with transaction() as session:
        session.get(m.Ingredient, egg).aliases = []
    again = _add(request, key)
    assert first.status_code == again.status_code == 201
    assert first.json()["event"]["id"] == again.json()["event"]["id"]
    assert first.json()["items"][0]["id"] == again.json()["items"][0]["id"]
    assert again.json()["items"][0]["ingredient_id"] == str(egg)
    assert len(client.get("/api/inventory").json()["groups"][0]["batches"]) == 1


def test_linking_a_new_batch_does_not_backfill_existing_free_text():
    original = _add([{"display_name": "egg"}]).json()["items"][0]
    egg = _ingredient("egg")
    added = _add([{"display_name": "egg"}]).json()["items"][0]
    assert added["ingredient_id"] == str(egg)
    with transaction() as session:
        assert session.get(m.InventoryItem, UUID(original["id"])).ingredient_id is None
