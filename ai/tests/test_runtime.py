import json
import time
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app
from app.model_client import ModelReply, get_client
from app.runtime import RequestState, current_request, request_budget


class SlowClient:
    model_id = "slow-test"

    def __init__(self, delay, answers):
        self.delay, self.answers, self.calls = delay, iter(answers), 0

    def generate(self, request):
        self.calls += 1
        time.sleep(self.delay)
        return ModelReply(next(self.answers), 10, 5)


def test_hard_deadline_returns_without_waiting_for_sync_provider(monkeypatch):
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "0.05")
    model = SlowClient(0.3, ['{"items":[]}'])
    app.dependency_overrides[get_client] = lambda: model
    try:
        with TestClient(app) as client:
            started = time.monotonic()
            response = client.post("/ai/parse-items", json={"text": "food"})
            assert time.monotonic() - started < 0.25
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"
        assert "x-ai-input-tokens" not in response.headers
        assert model.calls == 1
    finally:
        app.dependency_overrides.clear()


def test_repair_attempt_shares_the_original_budget(monkeypatch):
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "0.12")
    model = SlowClient(0.08, ["invalid json", '{"items":[]}'])
    app.dependency_overrides[get_client] = lambda: model
    try:
        response = TestClient(app).post("/ai/parse-items", json={"text": "food"})
        assert response.status_code == 503
        assert model.calls == 2
        assert response.headers["x-ai-attempts"] == "2"
    finally:
        app.dependency_overrides.clear()


def test_request_and_model_logs_share_id_without_sensitive_input(caplog):
    secret_text = "private grocery contents never log this"
    response = TestClient(app).post(
        "/ai/parse-items",
        json={"text": secret_text},
        headers={"X-Request-ID": "not-a-uuid-or-a-secret-to-log"},
    )
    request_id = response.headers["x-request-id"]
    UUID(request_id)
    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.name in {"app.runtime", "app.parse"}
    ]
    assert {event["request_id"] for event in events} == {request_id}
    assert {event["event"] for event in events} == {"ai_request", "model_call"}
    assert secret_text not in caplog.text
    assert "not-a-uuid-or-a-secret-to-log" not in caplog.text
    assert response.headers["x-ai-provider"] == "fake"
    assert response.headers["x-ai-input-tokens"] == "0"


def test_invalid_budget_is_a_safe_configuration_error(monkeypatch):
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "private-bad-value")
    response = TestClient(app).post("/ai/parse-items", json={"text": "food"})
    assert response.status_code == 503
    assert "private-bad-value" not in response.text


def test_lambda_budget_is_capped_and_reserves_cleanup_time(monkeypatch):
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "90")
    assert (
        request_budget({"aws.context": SimpleNamespace(get_remaining_time_in_millis=lambda: 50000)})
        == 27
    )
    assert (
        request_budget({"aws.context": SimpleNamespace(get_remaining_time_in_millis=lambda: 4000)})
        == 3
    )


def test_uuid_correlation_is_accepted():
    value = "9d2a7f2d-4802-4e36-a89a-0b8cd786cf72"
    response = TestClient(app).post(
        "/ai/parse-items", json={"text": "food"}, headers={"X-Request-ID": value}
    )
    assert response.headers["x-request-id"] == value


def test_no_state_leaks_between_requests():
    first = TestClient(app).post("/ai/parse-items", json={"text": "food"})
    second = TestClient(app).post("/ai/parse-items", json={"text": "food"})
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
    assert current_request.get() is None


def test_worker_transport_is_clipped_to_remaining_budget():
    import httpx

    from app.config import Settings
    from app.model_client import ModelRequest, SchoolModelClient

    timeouts = []

    def respond(request):
        timeouts.append(request.extensions["timeout"])
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"items":[]}'}}]})

    token = current_request.set(RequestState("test", time.monotonic() + 0.5))
    model = SchoolModelClient(
        Settings(base_url="https://school.example/v1/", model="test", api_key="test"),
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    try:
        model.generate(ModelRequest(task="items", system="JSON", text="food"))
        assert 0 < timeouts[0]["read"] <= 0.5
    finally:
        model.close()
        current_request.reset(token)
