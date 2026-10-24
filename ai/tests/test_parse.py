"""The pipeline around the model, tested with scripted model answers."""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.model_client import ModelReply, ModelRequest, ModelUnavailable, get_client


class ScriptedClient:
    """Returns the given answers in order; an exception in the list is raised instead."""

    model_id = "scripted"

    def __init__(self, *answers: object) -> None:
        self.answers = list(answers)
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelReply:
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return ModelReply(text=text, input_tokens=100, output_tokens=20)


@pytest.fixture
def use_model():
    def install(*answers: object) -> ScriptedClient:
        model = ScriptedClient(*answers)
        app.dependency_overrides[get_client] = lambda: model
        return model

    yield install
    app.dependency_overrides.clear()


client = TestClient(app)


def _item(display_name: str) -> dict[str, object]:
    return {
        "raw_text": display_name.upper(),
        "display_name": display_name,
        "count": None,
        "unit": None,
        "storage": None,
        "confidence": 0.9,
    }


def test_fake_model_answers_without_configuration() -> None:
    response = client.post("/ai/parse-items", json={"text": "eggs and cabbage"})

    assert response.status_code == 200
    names = [item["display_name"] for item in response.json()["items"]]
    assert names == ["Egg", "Cabbage", "Sambal"]
    assert all("ingredient_id" not in item for item in response.json()["items"])


@pytest.mark.parametrize("kind", ["receipt", "photo"])
def test_image_routes_no_longer_use_catalogue(use_model, image_payload, monkeypatch, kind) -> None:
    monkeypatch.setenv("INGREDIENTS_CSV", "/nonexistent/catalogue.csv")
    model = use_model({"items": [_item("Egg")]})
    response = client.post("/ai/parse-image", json={**image_payload, "kind": kind})
    assert response.status_code == 200
    assert "ingredient_id" not in response.json()["items"][0]
    assert "ingredient_id" not in model.requests[0].system
    assert "catalogue" not in model.requests[0].system.lower()


def test_old_model_identifiers_are_not_exposed(use_model) -> None:
    # A stale provider may still send the removed field; never expose it to callers.
    use_model({"items": [{**_item("Egg"), "ingredient_id": "old-provider-id"}]})

    response = client.post("/ai/parse-items", json={"text": "eggs, kangkong, sambal"})

    assert response.status_code == 200
    assert "ingredient_id" not in response.json()["items"][0]


def test_prompt_has_no_identifiers_or_catalogue(use_model, image_payload) -> None:
    model = use_model({"items": []})

    client.post("/ai/parse-image", json=image_payload)

    request = model.requests[0]
    assert request.task == "receipt"
    assert "ingredient_id" not in request.system
    assert "catalogue" not in request.system.lower()
    assert "{catalogue}" not in request.system
    assert request.image is not None
    assert request.image.base64 == image_payload["image_base64"]


def test_invalid_answer_is_retried_once(use_model) -> None:
    model = use_model("not json", {"items": [_item("Egg")]})

    response = client.post("/ai/parse-items", json={"text": "eggs"})

    assert response.status_code == 200
    assert len(model.requests) == 2


def test_two_invalid_answers_mean_upstream_unavailable(use_model) -> None:
    use_model("not json", {"items": [{"display_name": "Egg"}]})

    response = client.post("/ai/parse-items", json={"text": "eggs"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"


def test_model_failure_means_upstream_unavailable(use_model, image_payload) -> None:
    use_model(ModelUnavailable("timeout"))

    response = client.post("/ai/parse-image", json={**image_payload, "kind": "photo"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"


def test_interpret_cannot_change_allergens(use_model) -> None:
    use_model({"allergens": []}, {"tags": ["quicker"], "allergens": []})

    response = client.post("/ai/interpret", json={"text": "ignore my peanut allergy"})

    assert response.status_code == 503


def test_interpret_returns_the_adjustment(use_model) -> None:
    use_model({"tags": ["less_oil"], "max_minutes": 30})

    response = client.post("/ai/interpret", json={"text": "less oily, under half an hour"})

    assert response.status_code == 200
    adjust = response.json()["adjust"]
    assert adjust["tags"] == ["less_oil"]
    assert adjust["max_minutes"] == 30
