import json
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.model_client import (
    ModelRequest,
    ModelUnavailable,
    SchoolModelClient,
    get_client,
)

SETTINGS = Settings(
    provider="soclaas",
    base_url="https://school.example/v1/",
    model="default-model",
    api_key="private-test-key",
    image_model="vision-model",
    text_model="list-model",
    # Retain coverage for the previous prompt/schema as an explicit fallback.
    # Default and explicit per-instance photo routes are covered in test_photos.py.
    photo_quantity_mode="factors",
)


def completion(content, **extra):
    return {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30},
        **extra,
    }


def item(name="Egg", count=None, unit=None):
    return {
        "raw_text": name,
        "display_name": name,
        "count": count,
        "unit": unit,
        "storage": None,
        "confidence": 0.8,
    }


@pytest.fixture
def school():
    clients = []

    def install(*answers, settings=SETTINGS):
        requests = []
        remaining = iter(answers)

        def respond(request):
            if request.method == "GET":
                return httpx.Response(200, json={"data": []})
            requests.append(request)
            answer = next(remaining)
            if isinstance(answer, Exception):
                raise answer
            if isinstance(answer, httpx.Response):
                return answer
            return httpx.Response(200, json=answer)

        http = httpx.Client(transport=httpx.MockTransport(respond))
        model = SchoolModelClient(settings, http_client=http)
        clients.append(model)
        app.dependency_overrides[get_client] = lambda: model
        return model, requests

    yield install
    app.dependency_overrides.clear()
    for model in clients:
        model.close()


@pytest.mark.parametrize("source", ["typed", "voice"])
def test_text_route_passes_source_quantities_without_identifiers(school, source) -> None:
    answer = {"items": [item("Egg", 12, "pcs"), item("Tofu", 2, "pack"), item("Kangkong")]}
    _, requests = school(completion(json.dumps(answer)))
    response = TestClient(app).post(
        "/ai/parse-items",
        json={"text": "a dozen eggs, two packs of tofu, some kangkong", "source": source},
    )
    assert response.status_code == 200
    drafts = response.json()["items"]
    assert drafts[0]["count"] == 12
    assert all("ingredient_id" not in draft for draft in drafts)
    assert drafts[1]["count"] == 2 and drafts[1]["unit"] == "pack"
    assert drafts[2]["count"] is None and drafts[2]["unit"] is None
    request = requests[0]
    assert request.url == "https://school.example/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer private-test-key"
    payload = json.loads(request.content)
    assert payload["model"] == "list-model"
    assert f"Input source: {source}" in payload["messages"][1]["content"]
    assert "a dozen eggs" in payload["messages"][1]["content"]
    assert "catalogue" not in payload["messages"][0]["content"].lower()
    schema = payload["response_format"]["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["ExtractedItem"]["additionalProperties"] is False
    assert "ingredient_id" not in schema["$defs"]["ExtractedItem"]["properties"]
    assert "ingredient_id" not in schema["$defs"]["ExtractedItem"]["required"]
    assert "quantity" in schema["$defs"]["ExtractedItem"]["required"]


def test_receipt_route_sends_the_original_image_and_food_only_prompt(school, image_payload) -> None:
    _, requests = school(completion(json.dumps({"items": [item("Egg")]})))
    response = TestClient(app).post("/ai/parse-image", json=image_payload)
    assert response.status_code == 200
    payload = json.loads(requests[0].content)
    assert payload["model"] == "vision-model"
    assert "receipt" in payload["messages"][0]["content"]
    assert "non-food" in payload["messages"][0]["content"]
    assert "count: null; the application calculates" in payload["messages"][0]["content"]
    assert "A quantity line does not need a price" in payload["messages"][0]["content"]
    assert "default to 1" in payload["messages"][0]["content"]
    image = payload["messages"][1]["content"][1]["image_url"]["url"]
    assert image == "data:image/png;base64," + image_payload["image_base64"]
    assert response.json()["items"][0]["count"] == 1
    assert response.json()["items"][0]["unit"] == "pcs"
    assert "price" not in response.json()["items"][0]
    assert "ingredient_id" not in response.json()["items"][0]
    assert "ingredient_id" not in payload["messages"][0]["content"]


def test_empty_food_list_is_a_valid_result(school, image_payload) -> None:
    school(completion('{"items":[]}'))
    response = TestClient(app).post("/ai/parse-image", json=image_payload)
    assert response.status_code == 200 and response.json() == {"items": []}


@pytest.mark.parametrize("mode", ["receipt", "photo", "typed", "voice"])
def test_total_amounts_are_consistent_across_extraction_routes(school, image_payload, mode):
    totals = [
        {
            **item("Tofu", 550, "g"),
            "raw_text": "TOFU 225G\n2X$1.50/Unit",
            "quantity": {"factors": [2, 225], "unit": "g"},
        },
        item("Milk", 0.66, "l"),
        item("Egg", 20, "pcs"),
        item("Unknown measured food", None, "kg"),
        {**item("Rice", None, "kg"), "quantity": {"factors": [2, 0.5], "unit": "kg"}},
    ]
    school(completion(json.dumps({"items": totals})))
    if mode in {"receipt", "photo"}:
        response = TestClient(app).post("/ai/parse-image", json={**image_payload, "kind": mode})
    else:
        response = TestClient(app).post(
            "/ai/parse-items", json={"source": mode, "text": "food amounts"}
        )
    assert response.status_code == 200
    assert all("quantity" not in i for i in response.json()["items"])
    assert [(i["count"], i["unit"]) for i in response.json()["items"]] == [
        (450, "g"),
        (0.66, "l"),
        (20, "pcs"),
        (None, "kg"),
        (1, "kg"),
    ]


def test_bad_image_is_rejected_before_any_school_request(school) -> None:
    _, requests = school()
    response = TestClient(app).post(
        "/ai/parse-image", json={"kind": "receipt", "image_base64": "aGVsbG8="}
    )
    assert response.status_code == 422
    assert not requests


def test_invalid_model_json_gets_exactly_one_validation_retry(school) -> None:
    _, requests = school(completion("not json"), completion('{"items":[]}'))
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert response.status_code == 200
    assert len(requests) == 2


def test_two_invalid_answers_preserve_the_error_contract(school) -> None:
    _, requests = school(completion("not json"), completion('{"wrong":[]}'))
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    assert len(requests) == 2


@pytest.mark.parametrize("status", [401, 429, 500, 503])
def test_provider_errors_are_not_retried_or_exposed(school, status) -> None:
    _, requests = school(httpx.Response(status, json={"error": "private-provider-message"}))
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert response.status_code == 503
    assert "private-provider-message" not in response.text
    assert "private-test-key" not in response.text
    assert len(requests) == 1


def test_network_timeout_is_an_upstream_error(school) -> None:
    _, requests = school(httpx.ReadTimeout("private-provider-message"))
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert response.status_code == 503
    assert "private-provider-message" not in response.text
    assert len(requests) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"choices": []},
        {"choices": [{"message": {"refusal": "no", "content": None}}]},
        {"choices": [{"message": {"content": "{}"}, "finish_reason": "length"}]},
        {"choices": [{"message": {"content": []}}]},
    ],
)
def test_unusable_provider_envelopes_are_safe(school, body) -> None:
    model, _ = school(body)
    with pytest.raises(ModelUnavailable):
        model.generate(ModelRequest(task="items", system="JSON only", text="egg"))


def test_missing_usage_is_unknown_instead_of_zero(school) -> None:
    model, _ = school(completion('{"items":[]}', usage=None))
    reply = model.generate(ModelRequest(task="items", system="JSON only", text="egg"))
    assert reply.input_tokens is None and reply.output_tokens is None
    assert reply.model_id == "list-model"


def test_json_object_mode_is_explicit(school) -> None:
    model, requests = school(
        completion('{"items":[]}'), settings=replace(SETTINGS, output_mode="json_object")
    )
    reply = model.generate(ModelRequest(task="items", system="JSON only", text="egg"))
    assert reply.input_tokens == 120 and reply.output_tokens == 30
    assert json.loads(requests[0].content)["response_format"] == {"type": "json_object"}


def test_configured_timeout_reaches_the_transport(school) -> None:
    model, requests = school(
        completion('{"items":[]}'), settings=replace(SETTINGS, timeout_seconds=60)
    )
    model.generate(ModelRequest(task="items", system="JSON only", text="egg"))
    assert requests[0].extensions["timeout"] == {"connect": 5, "pool": 5, "read": 60, "write": 60}


def test_logs_record_the_selected_task_model(school, caplog) -> None:
    school(completion('{"items":[]}'))
    TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    events = [json.loads(record.message) for record in caplog.records if record.name == "app.parse"]
    assert events[0]["model_id"] == "list-model"
    assert events[0]["input_tokens"] == 120
    assert "private-test-key" not in caplog.text


def test_callers_cannot_select_models_or_send_credentials() -> None:
    response = TestClient(app).post(
        "/ai/parse-items", json={"text": "egg", "model": "other-model", "api_key": "user-value"}
    )
    assert response.status_code == 422


def test_blank_text_is_rejected_before_calling_the_provider(school) -> None:
    _, requests = school()
    response = TestClient(app).post("/ai/parse-items", json={"text": "   "})
    assert response.status_code == 422
    assert not requests


@pytest.mark.parametrize("count,unit", [(3, "PCS"), (None, None), (1, "pack")])
def test_photo_selects_prompt_and_preserves_visible_or_unknown_counts(
    school, image_payload, count, unit
) -> None:
    _, requests = school(completion(json.dumps({"items": [item("Food", count, unit)]})))
    response = TestClient(app).post("/ai/parse-image", json={**image_payload, "kind": "photo"})
    assert response.status_code == 200
    draft = response.json()["items"][0]
    assert draft["count"] == count
    assert draft["unit"] == (unit.lower() if unit else None)
    assert "freshness" not in draft and "expiry" not in draft
    payload = json.loads(requests[0].content)
    assert payload["model"] == "vision-model"
    assert "Never judge freshness" in payload["messages"][0]["content"]
    assert "visible groceries" in payload["messages"][1]["content"][0]["text"]


@pytest.mark.parametrize(
    "adjust",
    [
        {"tags": [tag]}
        for tag in ("quicker", "easier", "less_oil", "more_protein", "more_vegetables")
    ]
    + [{"people": 4}, {"max_minutes": 30}, {"max_difficulty": 1}],
)
def test_school_interpretation_uses_server_model_and_adjustment_schema(school, adjust) -> None:
    _, requests = school(
        completion(json.dumps(adjust)),
        settings=replace(SETTINGS, interpret_model="cooking-model"),
    )
    response = TestClient(app).post("/ai/interpret", json={"text": "a cooking adjustment"})
    assert response.status_code == 200
    for key, value in adjust.items():
        assert response.json()["adjust"][key] == value
    payload = json.loads(requests[0].content)
    assert payload["model"] == "cooking-model"
    assert payload["response_format"]["json_schema"]["name"] == "CookAdjust"
    assert "allergies and diets" in payload["messages"][0]["content"]
    assert "Do not invent numeric defaults" in payload["messages"][0]["content"]


@pytest.mark.parametrize(
    "adjust",
    [
        {"allergens": []},
        {"diets": []},
        {"recipe": "made up"},
        {"people": 0},
        {"people": 13},
        {"max_minutes": 4},
        {"max_minutes": 241},
        {"max_difficulty": 4},
        {"tags": ["unknown"]},
        {"tags": [], "people": None, "max_minutes": None, "max_difficulty": None},
    ],
)
def test_school_interpretation_rejects_unsupported_or_empty_adjustments(school, adjust) -> None:
    school(completion(json.dumps(adjust)), completion(json.dumps(adjust)))
    response = TestClient(app).post("/ai/interpret", json={"text": "a cooking adjustment"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"


def test_blank_interpretation_does_not_call_provider(school) -> None:
    _, requests = school()
    response = TestClient(app).post("/ai/interpret", json={"text": "   "})
    assert response.status_code == 422 and not requests
