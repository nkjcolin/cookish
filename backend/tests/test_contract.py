"""Endpoint inventory and contracts; persisted journeys have real-ID database tests."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import mock
from app.main import app

client = TestClient(app)

KEY = {"Idempotency-Key": str(uuid4())}
ITEM = mock.mock_id("item/tomato")
RECIPE = mock.mock_id("recipe/tomato-egg")
ANY = uuid4()

# (method, path template, concrete path, json body, needs Idempotency-Key, expected status)
ENDPOINTS = [
    ("GET", "/api/health", None, None, False, 200),
    ("GET", "/api/me", None, None, False, 200),
    ("PUT", "/api/household/preferences", None, {"allergens": ["peanut"]}, False, 200),
    ("GET", "/api/ingredients", "/api/ingredients?q=egg", None, False, 200),
    ("GET", "/api/inventory", None, None, False, 200),
    ("POST", "/api/inventory/items", None, {"items": [{"display_name": "Sambal"}]}, True, 201),
    (
        "PATCH",
        "/api/inventory/items/{item_id}",
        f"/api/inventory/items/{ITEM}",
        {"revision": 1, "count": 2},
        True,
        200,
    ),
    (
        "DELETE",
        "/api/inventory/items/{item_id}",
        f"/api/inventory/items/{ITEM}?revision=1",
        None,
        True,
        200,
    ),
    ("GET", "/api/stock-events", None, None, False, 200),
    (
        "POST",
        "/api/stock-events/{event_id}/undo",
        f"/api/stock-events/{ANY}/undo",
        None,
        True,
        200,
    ),
    ("GET", "/api/use-first", None, None, False, 200),
    ("POST", "/api/cook/sessions", None, {}, False, 201),
    (
        "POST",
        "/api/cook/sessions/{session_id}/adjust",
        f"/api/cook/sessions/{ANY}/adjust",
        {"tags": ["quicker"]},
        False,
        200,
    ),
    (
        "POST",
        "/api/cook/sessions/{session_id}/next",
        f"/api/cook/sessions/{ANY}/next",
        None,
        False,
        200,
    ),
    (
        "POST",
        "/api/cook/sessions/{session_id}/previous",
        f"/api/cook/sessions/{ANY}/previous",
        None,
        False,
        200,
    ),
    (
        "POST",
        "/api/cook/sessions/{session_id}/select",
        f"/api/cook/sessions/{ANY}/select",
        None,
        False,
        201,
    ),
    (
        "POST",
        "/api/cook/records/{record_id}/confirm",
        f"/api/cook/records/{ANY}/confirm",
        {"lines": [{"inventory_item_id": str(ITEM), "revision": 1, "new_count": 1}]},
        True,
        200,
    ),
    (
        "POST",
        "/api/cook/records/{record_id}/feedback",
        f"/api/cook/records/{ANY}/feedback",
        {"rating": "like"},
        False,
        200,
    ),
    ("GET", "/api/recipes/{recipe_id}", f"/api/recipes/{RECIPE}", None, False, 200),
    (
        "PUT",
        "/api/recipes/{recipe_id}/star",
        f"/api/recipes/{RECIPE}/star",
        {"starred": True},
        False,
        200,
    ),
    ("POST", "/api/shop/sessions", None, {}, False, 201),
    (
        "POST",
        "/api/shop/sessions/{session_id}/adjust",
        f"/api/shop/sessions/{ANY}/adjust",
        {"tags": ["longer_lasting"]},
        False,
        200,
    ),
    (
        "POST",
        "/api/shop/baskets/{basket_id}/confirm",
        f"/api/shop/baskets/{ANY}/confirm",
        {"lines": [{"basket_item_id": str(ANY), "bought": True}]},
        True,
        200,
    ),
    (
        "POST",
        "/ai/parse-image",
        None,
        {"kind": "receipt", "image_base64": "aGVsbG8="},
        False,
        200,
    ),
    ("POST", "/ai/image-jobs", None, {"kind": "photo", "image_base64": "test"}, True, 503),
    ("GET", "/ai/image-jobs/{job_id}", f"/ai/image-jobs/{ANY}", None, False, 503),
    ("POST", "/ai/parse-items", None, {"text": "two packs of tofu and some kangkong"}, False, 200),
    ("POST", "/ai/interpret", None, {"text": "something lighter"}, False, 200),
    (
        "POST",
        "/ai/transcribe-audio",
        None,
        {"media_type": "audio/webm", "audio_base64": "aGVsbG8="},
        False,
        200,
    ),
]

IDS = [f"{e[0]} {e[1]}" for e in ENDPOINTS]

# These endpoints use real database IDs now, so a made-up ID no longer works.
# They stay in ENDPOINTS so the spec check above still sees them, and are tested
# against the database in test_inventory_api_db.py and test_recipe_details_db.py.
REAL_DATABASE = {
    ("PATCH", "/api/inventory/items/{item_id}"),
    ("DELETE", "/api/inventory/items/{item_id}"),
    ("POST", "/api/stock-events/{event_id}/undo"),
    ("GET", "/api/recipes/{recipe_id}"),
    ("PUT", "/api/recipes/{recipe_id}/star"),
}
REAL_DATABASE.update(
    (method, template)
    for method, template, *_ in ENDPOINTS
    if template.startswith(("/api/cook/", "/api/shop/"))
)
STUBS = [e for e in ENDPOINTS if (e[0], e[1]) not in REAL_DATABASE]
STUB_IDS = [f"{e[0]} {e[1]}" for e in STUBS]


def test_spec_and_app_list_the_same_endpoints() -> None:
    documented = {(method, template) for method, template, *_ in ENDPOINTS}
    served = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }

    assert served == documented


@pytest.mark.parametrize(
    ("method", "_template", "path", "body", "keyed", "status"), STUBS, ids=STUB_IDS
)
def test_stub_answers(method, _template, path, body, keyed, status) -> None:
    response = client.request(method, path or _template, json=body, headers=KEY if keyed else {})

    assert response.status_code == status, response.text


@pytest.mark.parametrize(
    ("method", "_template", "path", "body", "keyed", "status"),
    [e for e in ENDPOINTS if e[4]],
    ids=[i for i, e in zip(IDS, ENDPOINTS, strict=True) if e[4]],
)
def test_inventory_changes_require_an_idempotency_key(
    method, _template, path, body, keyed, status
) -> None:
    response = client.request(method, path or _template, json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION"


def test_operation_ids_are_plain_function_names() -> None:
    operation = app.openapi()["paths"]["/api/cook/sessions"]["post"]

    assert operation["operationId"] == "start_cook_session"


def test_committed_openapi_file_is_current() -> None:
    from scripts.export_openapi import OPENAPI_PATH, render

    assert OPENAPI_PATH.read_text() == render(), (
        "docs/openapi.json is out of date. Run: uv run python scripts/export_openapi.py"
    )


def test_unknown_cook_session_is_not_a_sample_suggestion() -> None:
    response = client.post(f"/api/cook/sessions/{ANY}/adjust", json={"max_minutes": 15})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
