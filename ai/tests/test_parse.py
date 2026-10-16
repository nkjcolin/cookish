"""The pipeline around the model, tested with scripted model answers."""

import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.model_client import ModelReply, ModelRequest, ModelUnavailable, get_client

EGG = UUID("0b4f3c9e-5c55-4c49-9a35-6f1e2d3b7a01")
KANGKONG = UUID("0b4f3c9e-5c55-4c49-9a35-6f1e2d3b7a03")


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


def _item(display_name: str, ingredient_id: UUID | None = None) -> dict[str, object]:
    return {
        "raw_text": display_name.upper(),
        "ingredient_id": str(ingredient_id) if ingredient_id else None,
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


def test_ingredient_ids_are_checked_against_the_catalogue(use_model) -> None:
    use_model(
        {
            "items": [
                _item("Egg", EGG),  # known id: kept
                _item("Kangkong", uuid4()),  # invented id: replaced through the alias
                _item("Sambal", uuid4()),  # invented id, unknown name: null
            ]
        }
    )

    response = client.post("/ai/parse-items", json={"text": "eggs, kangkong, sambal"})

    ids = [item["ingredient_id"] for item in response.json()["items"]]
    assert ids == [str(EGG), str(KANGKONG), None]


def test_prompt_contains_the_catalogue(use_model) -> None:
    model = use_model({"items": []})

    client.post("/ai/parse-image", json={"kind": "receipt", "image_base64": "aGVsbG8="})

    request = model.requests[0]
    assert request.task == "receipt"
    assert f"{EGG} | egg" in request.system
    assert request.image is not None and request.image.base64 == "aGVsbG8="


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


def test_model_failure_means_upstream_unavailable(use_model) -> None:
    use_model(ModelUnavailable("timeout"))

    response = client.post("/ai/parse-image", json={"kind": "photo", "image_base64": "aGVsbG8="})

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
