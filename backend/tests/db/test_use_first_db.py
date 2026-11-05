"""Use-first HTTP reads use Role 2's real freshness snapshot and household scope."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import clock
from app.auth import DEV_CLAIMS
from app.db import models as m
from app.db.session import transaction
from app.main import app
from app.schemas.cook import UseFirstList
from app.services import cook
from app.services.identity import get_or_create_user
from app.services.stock_events import get_inventory_snapshot
from seed.seed import seed
from tests.reco_fixtures import NOW

client = TestClient(app)


@pytest.fixture
def kitchen(monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: NOW)
    seed()
    with transaction() as session:
        user = get_or_create_user(session, UUID(DEV_CLAIMS["sub"]), DEV_CLAIMS["email"])
        egg = session.scalar(select(m.Ingredient).where(m.Ingredient.canonical_name == "egg"))
        return user, egg.id, egg.shelf_life_days_fridge


def add(user, ingredient_id, **changes):
    item_id = uuid4()
    fields = dict(
        id=item_id,
        household_id=user.household_id,
        ingredient_id=ingredient_id,
        display_name="Eggs",
        count=3,
        unit="pcs",
        remaining_state="enough",
        storage="fridge",
        source="manual",
        acquired_at=NOW.date(),
        label_date=NOW.date() + timedelta(days=2),
        label_date_kind="use_by",
        last_confirmed_at=NOW,
    )
    with transaction() as session:
        session.add(m.InventoryItem(**{**fields, **changes}))
    return item_id


def test_use_first_empty_household_has_no_mock_batches(kitchen):
    response = client.get("/api/use-first")
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_snapshot_filters_freshness_stock_and_deleted_rows_and_orders_real_batches(kitchen):
    user, egg, _ = kitchen
    today = add(user, egg, label_date=NOW.date())
    last_day = add(user, egg, label_date=NOW.date() + timedelta(days=3))
    for changes in [
        {"label_date": NOW.date() + timedelta(days=4)},
        {"label_date": NOW.date() - timedelta(days=1)},
        {"label_date": NOW.date() - timedelta(days=1), "label_date_kind": "best_before"},
        {
            "label_date": NOW.date() - timedelta(days=1),
            "label_date_kind": "best_before",
            "freshness_confirmed_at": NOW,
        },
        {"remaining_state": "out"},
        {"remaining_state": "unknown"},
        {"count": 0},
        {"count": None},
        {"last_confirmed_at": NOW - timedelta(days=15)},
        {"deleted_at": NOW},
    ]:
        add(user, egg, **changes)
    response = client.get("/api/use-first")
    assert response.status_code == 200, response.text
    result = UseFirstList.model_validate(response.json())
    assert [row.item.id for row in result.items] == [today, last_day]
    assert [row.days_left for row in result.items] == [0, 3]
    assert all(row.item.freshness_status == "use_soon" for row in result.items)


def test_uses_computed_estimate_and_preserves_printed_label_fields(kitchen):
    user, egg, shelf_days = kitchen
    assert shelf_days is not None
    estimated = add(
        user,
        egg,
        label_date=None,
        label_date_kind=None,
        acquired_at=NOW.date() - timedelta(days=shelf_days - 2),
    )
    labelled = add(user, egg, label_date=NOW.date() + timedelta(days=1))
    result = cook.use_first(user)
    assert [row.item.id for row in result.items] == [labelled, estimated]
    assert [row.days_left for row in result.items] == [1, 2]
    assert result.items[0].item.label_date == NOW.date() + timedelta(days=1)
    assert result.items[1].item.label_date is None


def test_reads_are_household_scoped_and_never_change_inventory(kitchen):
    user, egg, _ = kitchen
    with transaction() as session:
        other = get_or_create_user(session, uuid4(), "other@example.test")
    own = add(user, egg)
    foreign = add(other, egg, label_date=NOW.date())
    with transaction() as session:
        before = get_inventory_snapshot(session, user.household_id)
    first = cook.use_first(user)
    assert [row.item.id for row in first.items] == [own]
    assert cook.use_first(user) == first
    assert [row.item.id for row in cook.use_first(other).items] == [foreign]
    with transaction() as session:
        assert get_inventory_snapshot(session, user.household_id) == before
