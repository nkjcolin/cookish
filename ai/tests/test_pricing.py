import base64
import json
import time
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from app.audio import wav_duration_seconds
from app.config import Settings
from app.main import app
from app.model_client import SchoolModelClient, get_client
from app.pricing import PricingCache, PricingUnavailable, nonnegative_decimal


def catalogue(model="school-model", **extra):
    return {
        "data": [
            {
                "id": model,
                "soclaas": {
                    "input_microdollars_per_million_tokens": 104000,
                    "output_microdollars_per_million_tokens": 416000,
                    "audio_microdollars_per_minute": 6000,
                    **extra,
                },
            }
        ]
    }


def completion(text='{"items":[]}', usage=True, **extra):
    return {
        "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1000, "completion_tokens": 200} if usage else None,
        **extra,
    }


def test_decimal_estimates_convert_microdollars_and_million_tokens_once():
    rate = PricingCache(lambda: catalogue()).snapshot()["school-model"]
    assert rate.chat_cost(1000, 200) == Decimal("0.0001872")
    assert rate.chat_cost(0, 0) == 0
    assert rate.chat_cost(None, 200) is None
    assert rate.chat_cost(1000, None) is None
    assert rate.audio_cost(Decimal("3.86")) == Decimal("0.000386")
    assert rate.audio_cost(None) is None
    assert rate.metadata()["input_microdollars_per_million_tokens"] == "104000"


@pytest.mark.parametrize("value", [None, True, False, -1, "NaN", "Infinity", "", {}, []])
def test_missing_or_invalid_rate_never_becomes_zero(value):
    assert nonnegative_decimal(value) is None
    rate = PricingCache(lambda: catalogue(input_microdollars_per_million_tokens=value)).snapshot()[
        "school-model"
    ]
    assert rate.chat_cost(1000, 200) is None


def test_cache_refresh_and_failure_backoff_never_reuse_expired_rates():
    now = [0.0]
    calls = []

    def load():
        calls.append(1)
        if len(calls) == 2:
            raise PricingUnavailable()
        return catalogue()

    cache = PricingCache(load, ttl=60, clock=lambda: now[0])
    first = cache.snapshot()
    now[0] = 59
    assert cache.snapshot() is first
    assert len(calls) == 1
    now[0] = 60
    assert cache.snapshot() == {}
    now[0] = 89
    assert cache.snapshot() == {}
    assert len(calls) == 2
    now[0] = 90
    assert "school-model" in cache.snapshot()
    assert len(calls) == 3


def test_wav_duration_uses_complete_recording_not_client_claims(audio_payload):
    data = base64.b64decode(audio_payload["audio_base64"])
    assert wav_duration_seconds(data, "audio/wav") == Decimal("0.1")
    assert wav_duration_seconds(data[:-2], "audio/wav") is None
    assert wav_duration_seconds(data, "audio/webm") is None
    assert wav_duration_seconds(b"bad", "audio/wav") is None


@pytest.fixture
def priced_school():
    clients = []

    def install(*answers, prices=None, pricing_delay=0, second_delay=0):
        requests = []
        remaining = iter(answers)

        def respond(request):
            requests.append(request)
            if request.method == "GET":
                time.sleep(pricing_delay)
                answer = catalogue() if prices is None else prices
            else:
                if sum(r.method == "POST" for r in requests) > 1:
                    time.sleep(second_delay)
                answer = next(remaining)
            if isinstance(answer, Exception):
                raise answer
            return (
                answer if isinstance(answer, httpx.Response) else httpx.Response(200, json=answer)
            )

        model = SchoolModelClient(
            Settings(
                provider="soclaas",
                base_url="https://school.example/v1/",
                model="school-model",
                audio_model="school-model",
                api_key="private-test-key",
            ),
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        )
        clients.append(model)
        app.dependency_overrides[get_client] = lambda: model
        return requests

    yield install
    app.dependency_overrides.clear()
    for client in clients:
        client.close()


def test_chat_cost_headers_logs_and_warm_cache(priced_school, caplog):
    requests = priced_school(completion(), completion())
    client = TestClient(app)
    response = client.post("/ai/parse-items", json={"text": "private food text"})
    assert response.status_code == 200
    assert response.json() == {"items": []}
    assert response.headers["x-ai-estimated-cost"] == "0.0001872"
    assert response.headers["x-ai-cost-status"] == "estimated"
    assert response.headers["x-ai-cost-unit"] == "provider_dollars"
    assert response.headers["x-ai-input-tokens"] == "1000"
    assert response.headers["x-ai-output-tokens"] == "200"
    assert response.headers["x-ai-pricing-fetched-at"]
    client.post("/ai/parse-items", json={"text": "eggs"})
    assert [r.method for r in requests] == ["GET", "POST", "POST"]
    assert str(requests[0].url) == "https://school.example/v1/models"
    assert requests[0].headers["Authorization"] == "Bearer private-test-key"
    assert 0 < requests[0].extensions["timeout"]["read"] <= 1
    events = [json.loads(r.message) for r in caplog.records if r.name == "app.parse"]
    assert events[0]["estimated_cost"] == "0.0001872"
    assert events[0]["pricing"]["model_id"] == "school-model"
    assert "private food text" not in caplog.text
    assert "private-test-key" not in caplog.text


def test_schema_repair_adds_both_attempts(priced_school):
    priced_school(completion("not JSON"), completion())
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert response.status_code == 200
    assert response.headers["x-ai-input-tokens"] == "2000"
    assert response.headers["x-ai-output-tokens"] == "400"
    assert response.headers["x-ai-estimated-cost"] == "0.0003744"
    assert response.headers["x-ai-attempts"] == "2"


@pytest.mark.parametrize(
    "first,second",
    [
        (completion("not JSON", usage=False), completion()),
        (completion("not JSON"), completion(usage=False)),
        (completion("not JSON"), httpx.ReadTimeout("secret upstream failure")),
    ],
)
def test_incomplete_attempts_expose_only_known_subtotal(priced_school, first, second):
    priced_school(first, second)
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert "x-ai-estimated-cost" not in response.headers
    assert response.headers["x-ai-known-estimated-cost"] == "0.0001872"
    assert response.headers["x-ai-cost-status"] == "partial"
    assert "x-ai-input-tokens" not in response.headers


@pytest.mark.parametrize(
    "prices",
    [
        httpx.Response(403, json={"error": "private price failure"}),
        httpx.ReadTimeout("private price failure"),
        httpx.Response(200, text="invalid"),
        {"unexpected": []},
        catalogue(input_microdollars_per_million_tokens=None),
    ],
)
def test_pricing_failure_preserves_successful_extraction(priced_school, prices, caplog):
    priced_school(completion(), prices=prices)
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert response.status_code == 200
    assert response.headers["x-ai-input-tokens"] == "1000"
    assert response.headers["x-ai-cost-status"] == "unknown"
    assert "x-ai-estimated-cost" not in response.headers
    assert "private price failure" not in caplog.text


def test_refusal_still_records_known_usage_and_estimate(priced_school):
    priced_school(completion(choices=[{"message": {"refusal": "no", "content": None}}]))
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert response.status_code == 503
    assert response.headers["x-ai-estimated-cost"] == "0.0001872"
    assert response.headers["x-ai-input-tokens"] == "1000"


def test_returned_model_selects_its_own_rate(priced_school):
    prices = catalogue()
    prices["data"].extend(
        catalogue("actual-model", input_microdollars_per_million_tokens=1000000)["data"]
    )
    priced_school(completion(model="actual-model"), prices=prices)
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert response.headers["x-ai-model"] == "actual-model"
    assert response.headers["x-ai-estimated-cost"] == "0.0010832"


def test_unrelated_returned_model_never_uses_default_price(priced_school):
    priced_school(completion(model="unlisted-model"))
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert response.status_code == 200
    assert response.headers["x-ai-cost-status"] == "unknown"


def test_alias_price_can_cover_its_declared_target(priced_school):
    priced_school(completion(model="actual-model"), prices=catalogue(alias_of="actual-model"))
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert response.headers["x-ai-model"] == "actual-model"
    assert response.headers["x-ai-estimated-cost"] == "0.0001872"


def test_wav_audio_has_duration_cost_without_fabricating_tokens(priced_school, audio_payload):
    priced_school({"text": "eggs"})
    response = TestClient(app).post("/ai/transcribe-audio", json=audio_payload)
    assert response.status_code == 200
    assert response.headers["x-ai-estimated-cost"] == "0.00001"
    assert response.headers["x-ai-cost-status"] == "estimated"
    assert "x-ai-input-tokens" not in response.headers


@pytest.mark.parametrize("duration,expected", [(None, None), (2, "0.0002")])
def test_webm_cost_requires_provider_duration(priced_school, duration, expected):
    priced_school({"text": "eggs", "duration": duration})
    response = TestClient(app).post(
        "/ai/transcribe-audio",
        json={
            "media_type": "audio/webm",
            "audio_base64": base64.b64encode(b"\x1aE\xdf\xa3" + b"x" * 20).decode(),
        },
    )
    assert response.status_code == 200
    assert response.headers.get("x-ai-estimated-cost") == expected


def test_fake_cost_is_explicitly_marked_fake():
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert response.headers["x-ai-estimated-cost"] == "0"
    assert response.headers["x-ai-cost-status"] == "fake"


def test_deadline_preserves_prior_attempt_subtotal(priced_school, monkeypatch):
    priced_school(completion(), completion("invalid"), completion(), second_delay=0.08)
    client = TestClient(app)
    assert client.post("/ai/parse-items", json={"text": "warm cache"}).status_code == 200
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "0.12")
    response = client.post("/ai/parse-items", json={"text": "eggs"})
    assert response.status_code == 503
    assert response.headers["x-ai-cost-status"] == "partial"
    assert response.headers["x-ai-known-estimated-cost"] == "0.0001872"
    assert "x-ai-estimated-cost" not in response.headers


def test_short_deadline_skips_optional_pricing_lookup(priced_school, monkeypatch):
    requests = priced_school(completion())
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "0.15")
    response = TestClient(app).post("/ai/parse-items", json={"text": "eggs"})
    assert response.status_code == 200
    assert [r.method for r in requests] == ["POST"]
    assert response.headers["x-ai-cost-status"] == "unknown"
