import json
import time
from types import SimpleNamespace
from uuid import uuid4

import anyio
import pytest
from fastapi.testclient import TestClient

from app import image_jobs, job_worker
from app.errors import ApiError, ErrorCode
from app.job_store import LocalJobStore, get_job_store
from app.main import app, job_store
from app.model_client import FakeModelClient, ModelUnavailable
from app.schemas import ParseImageRequest

pytestmark = pytest.mark.usefixtures("lambda_event_loop")


@pytest.fixture
def store(tmp_path):
    value = LocalJobStore(tmp_path / "jobs")
    app.dependency_overrides[job_store] = lambda: value
    yield value
    app.dependency_overrides.clear()
    get_job_store.cache_clear()


def submit(store, image_payload, owner="alice", key=None):
    return image_jobs.submit_image_job(
        ParseImageRequest(**image_payload), owner, key or uuid4(), store
    )


def test_submission_does_not_call_model_and_repeated_key_returns_same_job(store, image_payload):
    key = uuid4()
    first = submit(store, image_payload, key=key)
    again = submit(store, image_payload, key=key)
    assert first == again
    assert first.status == "queued"
    assert store.pending(int(time.time())) == [str(first.job_id)]
    assert store.get(str(first.job_id))["attempts"] == 0


def test_key_cannot_be_reused_for_a_different_image_kind(store, image_payload):
    key = uuid4()
    submit(store, image_payload, key=key)
    with pytest.raises(ApiError) as caught:
        submit(store, {**image_payload, "kind": "photo"}, key=key)
    assert caught.value.code == ErrorCode.CONFLICT


def test_another_user_cannot_read_result_even_with_job_id(store, image_payload):
    job = submit(store, image_payload)
    with pytest.raises(ApiError) as caught:
        image_jobs.read_image_job(job.job_id, "bob", store)
    assert caught.value.code == ErrorCode.NOT_FOUND
    assert submit(store, image_payload, owner="bob").job_id != job.job_id


def test_completed_job_survives_new_store_instance_and_duplicate_delivery(store, image_payload):
    job = submit(store, image_payload)
    client = FakeModelClient()
    assert anyio.run(job_worker.process_job, str(job.job_id), store, client)
    record = store.get(str(job.job_id))
    assert record["status"] == "completed"
    assert record["attempts"] == 1
    assert not (store.root / "images" / str(job.job_id)).exists()
    reopened = LocalJobStore(store.root)
    assert image_jobs.read_image_job(job.job_id, "alice", reopened).result.items
    assert anyio.run(job_worker.process_job, str(job.job_id), reopened, client)
    assert reopened.get(str(job.job_id))["attempts"] == 1
    assert image_jobs.read_image_job(job.job_id, "alice", reopened).usage.input_tokens == 0


def test_active_lease_cannot_be_claimed_twice(store, image_payload):
    job_id = str(submit(store, image_payload).job_id)
    now = int(time.time())
    first = store.claim(job_id, now, 120)
    assert first
    assert store.claim(job_id, now + 1, 120) is None
    second = store.claim(job_id, now + 121, 120)
    assert second["attempts"] == 2
    assert not store.update(job_id, {"status": "completed"}, first["lease_token"])


def test_upload_failure_can_be_repaired_with_same_key(store, image_payload, monkeypatch):
    original = store.enqueue
    monkeypatch.setattr(store, "enqueue", lambda _: (_ for _ in ()).throw(OSError("queue down")))
    key = uuid4()
    with pytest.raises(OSError):
        submit(store, image_payload, key=key)
    monkeypatch.setattr(store, "enqueue", original)
    job = submit(store, image_payload, key=key)
    assert str(job.job_id) in store.pending(int(time.time()))


class UnavailableClient:
    model_id = "unavailable"

    def generate(self, request):
        raise ModelUnavailable("private upstream error must not reach the user")


def test_model_failures_retry_bounded_times_then_publish_safe_failure(store, image_payload):
    job = submit(store, image_payload)
    for expected in (False, False, True):
        assert (
            anyio.run(job_worker.process_job, str(job.job_id), store, UnavailableClient())
            is expected
        )
    result = image_jobs.read_image_job(job.job_id, "alice", store)
    assert result.status == "failed"
    assert result.error.code == ErrorCode.UPSTREAM_UNAVAILABLE
    assert "private" not in result.model_dump_json()
    assert not (store.root / "images" / str(job.job_id)).exists()


def test_worker_has_separate_budget_and_obeys_lambda_remaining_time(monkeypatch):
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "27")
    monkeypatch.setenv("AI_WORKER_TIMEOUT_SECONDS", "110")
    assert job_worker.worker_budget() == 110
    assert (
        job_worker.worker_budget(SimpleNamespace(get_remaining_time_in_millis=lambda: 120000))
        == 110
    )
    assert (
        job_worker.worker_budget(SimpleNamespace(get_remaining_time_in_millis=lambda: 20000)) == 15
    )


def test_worker_timeout_requeues_instead_of_leaving_permanent_processing(
    store, image_payload, monkeypatch
):
    class SlowClient(FakeModelClient):
        def generate(self, request):
            time.sleep(0.1)
            return super().generate(request)

    monkeypatch.setenv("AI_WORKER_TIMEOUT_SECONDS", "0.02")
    job = submit(store, image_payload)
    assert not anyio.run(job_worker.process_job, str(job.job_id), store, SlowClient())
    assert store.get(str(job.job_id))["status"] == "queued"


def test_abandoned_job_fails_and_ttl_expiration_hides_it(store, image_payload, monkeypatch):
    job = submit(store, image_payload)
    record = store.get(str(job.job_id))
    monkeypatch.setattr(image_jobs.time, "time", lambda: record["work_deadline"] + 1)
    assert image_jobs.read_image_job(job.job_id, "alice", store).status == "failed"
    monkeypatch.setattr(image_jobs.time, "time", lambda: record["expires_at"] + 1)
    with pytest.raises(ApiError) as caught:
        image_jobs.read_image_job(job.job_id, "alice", store)
    assert caught.value.code == ErrorCode.NOT_FOUND
    store.cleanup(record["expires_at"] + 1)
    assert store.get(str(job.job_id)) is None


def test_routes_require_key_reject_bad_images_and_return_job_status(store, image_payload):
    with TestClient(app) as client:
        assert client.post("/ai/image-jobs", json=image_payload).status_code == 422
        headers = {"Idempotency-Key": str(uuid4())}
        invalid = client.post(
            "/ai/image-jobs", json={**image_payload, "image_base64": "bad"}, headers=headers
        )
        assert invalid.status_code == 422
        response = client.post("/ai/image-jobs", json=image_payload, headers=headers)
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        assert client.get(f"/ai/image-jobs/{job_id}").json()["status"] == "queued"
        assert client.get(f"/ai/image-jobs/{uuid4()}").status_code == 404


def test_lambda_routes_fail_closed_without_gateway_claims(store, image_payload):
    async def lambda_app(scope, receive, send):
        if scope["type"] == "http":
            scope["aws.context"] = SimpleNamespace(get_remaining_time_in_millis=lambda: 120000)
            scope["aws.event"] = {"requestContext": {}}
        await app(scope, receive, send)

    with TestClient(lambda_app) as client:
        response = client.post(
            "/ai/image-jobs", json=image_payload, headers={"Idempotency-Key": str(uuid4())}
        )
        assert response.status_code == 401


def test_sqs_partial_failures_do_not_retry_successful_messages(store, image_payload, monkeypatch):
    job_id = str(submit(store, image_payload).job_id)
    monkeypatch.setattr(job_worker, "get_job_store", lambda: store)
    result = job_worker.handler(
        {
            "Records": [
                {"messageId": "good", "body": json.dumps({"job_id": job_id})},
                {"messageId": "bad", "body": "broken"},
            ]
        },
        SimpleNamespace(get_remaining_time_in_millis=lambda: 120000),
    )
    assert result == {"batchItemFailures": [{"itemIdentifier": "bad"}]}
    assert store.get(job_id)["status"] == "completed"


def test_usage_includes_retries_and_preserves_unknown_totals():
    from decimal import Decimal

    from app.runtime import RequestState

    first = RequestState(
        "job",
        100,
        input_tokens=10,
        output_tokens=5,
        known_input_tokens=10,
        known_output_tokens=5,
        estimated_cost=Decimal("0.01"),
        known_estimated_cost=Decimal("0.01"),
    )
    prior = job_worker.attempt_usage({"attempts": 1}, first)
    final = job_worker.attempt_usage({"attempts": 2, "usage_json": prior.model_dump_json()}, first)
    assert final.input_tokens == 20 and final.output_tokens == 10
    assert final.estimated_cost == "0.02"
    unknown = job_worker.attempt_usage({"attempts": 2}, first)
    assert unknown.input_tokens is None and unknown.estimated_cost is None
    assert unknown.known_input_tokens == 10 and unknown.known_estimated_cost == "0.01"
    assert unknown.cost_status == "partial"


def test_job_routes_through_mangum_preserve_claims_and_headers(store, image_payload):
    from app.lambda_handler import handler
    from scripts.test_lambda import gateway_event

    context = SimpleNamespace(get_remaining_time_in_millis=lambda: 120000)
    event = gateway_event("/ai/image-jobs", image_payload)
    event["headers"]["idempotency-key"] = str(uuid4())
    event["requestContext"]["authorizer"] = {"jwt": {"claims": {"sub": str(uuid4())}}}
    created = handler(event, context)
    assert created["statusCode"] == 202
    value = json.loads(created["body"])
    event["rawPath"] = event["requestContext"]["http"]["path"] = f"/ai/image-jobs/{value['job_id']}"
    event["requestContext"]["http"]["method"] = "GET"
    event["body"] = ""
    event["routeKey"] = "GET /ai/{proxy+}"
    result = handler(event, context)
    assert result["statusCode"] == 200
    assert json.loads(result["body"])["job_id"] == value["job_id"]
