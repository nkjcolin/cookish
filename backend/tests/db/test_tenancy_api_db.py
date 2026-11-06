"""SPEC A6, tenant isolation: one household can never read or change another's data.

Every Role 2 route, called over HTTP as two different signed-in users.
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.db.session import transaction
from app.main import app
from app.services import identity

ALICE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
BOB_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")

client = TestClient(app)


def _login(user_id: UUID, email: str) -> CurrentUser:
    with transaction() as s:
        return identity.get_or_create_user(s, user_id, email)


@pytest.fixture
def people():
    alice = _login(ALICE_ID, "alice@cookish.test")
    bob = _login(BOB_ID, "bob@cookish.test")
    yield alice, bob
    app.dependency_overrides.pop(get_current_user, None)


def _as(user: CurrentUser) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid4())}


def _alice_has_an_item(people):
    alice, _ = people
    _as(alice)
    added = client.post(
        "/api/inventory/items", json={"items": [{"display_name": "Alice's rice"}]}, headers=_key()
    )
    assert added.status_code == 201
    return added.json()["items"][0], added.json()["event"]


def test_bob_cannot_see_alices_kitchen_or_activity(people):
    _, bob = people
    _alice_has_an_item(people)
    _as(bob)
    assert client.get("/api/inventory").json()["groups"] == []
    assert client.get("/api/stock-events").json()["events"] == []


def test_bob_cannot_change_remove_or_undo_alices_things(people):
    _, bob = people
    item, event = _alice_has_an_item(people)
    _as(bob)
    patched = client.patch(
        f"/api/inventory/items/{item['id']}", json={"revision": 1, "count": 9}, headers=_key()
    )
    deleted = client.delete(f"/api/inventory/items/{item['id']}?revision=1", headers=_key())
    undone = client.post(f"/api/stock-events/{event['id']}/undo", headers=_key())
    for response in (patched, deleted, undone):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
    alice, _ = people
    _as(alice)  # and nothing of Alice's changed
    (group,) = client.get("/api/inventory").json()["groups"]
    assert group["batches"][0]["revision"] == 1 and group["batches"][0]["count"] is None


def test_the_household_comes_from_the_login_not_the_request(people):
    alice, bob = people
    _as(bob)
    response = client.post(
        "/api/inventory/items",
        json={"items": [{"display_name": "Sneaky"}], "household_id": str(alice.household_id)},
        headers=_key(),
    )
    assert response.status_code == 422  # unknown fields are refused, not obeyed
    _as(alice)
    assert client.get("/api/inventory").json()["groups"] == []


def test_each_user_gets_their_own_household_and_preferences(people):
    alice, bob = people
    _as(alice)
    assert (
        client.put("/api/household/preferences", json={"allergens": ["peanut"]}).status_code == 200
    )
    mine = client.get("/api/me").json()
    _as(bob)
    theirs = client.get("/api/me").json()
    assert mine["household"] != theirs["household"]
    assert mine["preferences"]["allergens"] == ["peanut"]
    assert theirs["preferences"] is None  # Alice's saved preferences did not reach Bob
    client.put("/api/household/preferences", json={"allergens": ["milk"]})
    _as(alice)
    assert client.get("/api/me").json()["preferences"]["allergens"] == ["peanut"]


def test_the_ingredient_catalogue_is_shared_and_read_only(people):
    alice, bob = people
    _as(alice)
    first = client.get("/api/ingredients?q=a").json()
    _as(bob)
    assert client.get("/api/ingredients?q=a").json() == first
    assert client.post("/api/ingredients", json={"canonical_name": "x"}).status_code in (404, 405)
