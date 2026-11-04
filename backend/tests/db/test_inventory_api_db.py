"""The inventory write endpoints over HTTP, against a real Postgres.

test_contract.py checks that every endpoint exists and answers in the right shape, using fake
IDs. These three act on a real item, so they are exercised here from add to undo.
"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _key() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid4())}


def _add(name: str = "Sambal", key: dict[str, str] | None = None):
    return client.post(
        "/api/inventory/items", json={"items": [{"display_name": name}]}, headers=key or _key()
    )


def test_add_edit_remove_and_undo_over_http():
    added = _add()
    assert added.status_code == 201
    item = added.json()["items"][0]
    assert (item["display_name"], item["revision"]) == ("Sambal", 1)

    edited = client.patch(
        f"/api/inventory/items/{item['id']}",
        json={"revision": 1, "count": 2},
        headers=_key(),
    )
    assert edited.status_code == 200
    assert edited.json()["items"][0]["count"] == 2
    assert edited.json()["items"][0]["revision"] == 2

    removed = client.delete(f"/api/inventory/items/{item['id']}?revision=2", headers=_key())
    assert removed.status_code == 200 and removed.json()["items"] == []
    assert client.get("/api/inventory").json()["groups"] == []

    events = client.get("/api/stock-events").json()["events"]
    assert [e["type"] for e in events] == ["adjust", "adjust", "purchase"]

    undone = client.post(f"/api/stock-events/{removed.json()['event']['id']}/undo", headers=_key())
    assert undone.status_code == 200 and undone.json()["conflicts"] == []
    (group,) = client.get("/api/inventory").json()["groups"]
    assert group["batches"][0]["id"] == item["id"]
    assert group["batches"][0]["count"] == 2


def test_a_stale_revision_is_a_409_with_the_current_revision():
    item = _add().json()["items"][0]
    response = client.patch(
        f"/api/inventory/items/{item['id']}", json={"revision": 7, "count": 2}, headers=_key()
    )
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "STALE_REVISION"
    assert error["details"]["current_revision"] == 1


def test_repeating_a_request_with_the_same_key_changes_nothing_more():
    key = _key()
    first, again = _add(key=key), _add(key=key)
    assert first.status_code == again.status_code == 201
    assert first.json()["event"]["id"] == again.json()["event"]["id"]
    (group,) = client.get("/api/inventory").json()["groups"]
    assert len(group["batches"]) == 1


def test_an_unknown_item_is_a_404_and_a_reused_key_is_a_409():
    missing = client.patch(
        f"/api/inventory/items/{uuid4()}", json={"revision": 1, "count": 2}, headers=_key()
    )
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"

    key = _key()
    item = _add(key=key).json()["items"][0]
    reused = client.delete(f"/api/inventory/items/{item['id']}?revision=1", headers=key)
    assert reused.status_code == 409 and reused.json()["error"]["code"] == "CONFLICT"
