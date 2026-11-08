"""Fast SDK-adapter checks with in-process mocks, not a local AWS deployment."""

import json
import time
from uuid import uuid4

import anyio
import boto3
import pytest
from moto import mock_aws

from app import image_jobs, job_worker
from app.job_store import AwsJobStore, get_job_store
from app.model_client import FakeModelClient
from app.schemas import ParseImageRequest

pytestmark = pytest.mark.usefixtures("lambda_event_loop")


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AI_JOB_BUCKET", "cookish-test-images")
    monkeypatch.setenv("AI_JOB_TABLE", "cookish-test-jobs")
    with mock_aws():
        boto3.client("s3").create_bucket(Bucket="cookish-test-images")
        queue = boto3.client("sqs").create_queue(QueueName="image-jobs")["QueueUrl"]
        monkeypatch.setenv("AI_JOB_QUEUE_URL", queue)
        boto3.client("dynamodb").create_table(
            TableName="cookish-test-jobs",
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield AwsJobStore()


def test_aws_store_delivers_and_persists_one_result_with_duplicate_suppression(
    store, image_payload
):
    key = uuid4()
    body = ParseImageRequest(**image_payload)
    job = image_jobs.submit_image_job(body, "alice", key, store)
    assert image_jobs.submit_image_job(body, "alice", key, store) == job
    messages = store.sqs.receive_message(QueueUrl=store.queue_url, MaxNumberOfMessages=10)[
        "Messages"
    ]
    assert all(json.loads(message["Body"]) == {"job_id": str(job.job_id)} for message in messages)
    assert anyio.run(job_worker.process_job, str(job.job_id), store, FakeModelClient())
    assert anyio.run(job_worker.process_job, str(job.job_id), store, FakeModelClient())
    record = store.get(str(job.job_id))
    assert record["status"] == "completed" and record["attempts"] == 1
    assert image_jobs.read_image_job(job.job_id, "alice", store).result.items
    assert store.s3.list_objects_v2(Bucket=store.bucket)["KeyCount"] == 0


def test_aws_store_conditional_lease_blocks_stale_worker_results(store, image_payload):
    job = image_jobs.submit_image_job(ParseImageRequest(**image_payload), "alice", uuid4(), store)
    now = int(time.time())
    first = store.claim(str(job.job_id), now, 120)
    assert first
    assert store.claim(str(job.job_id), now + 1, 120) is None
    second = store.claim(str(job.job_id), now + 121, 120)
    assert second["attempts"] == 2
    assert not store.update(str(job.job_id), {"status": "completed"}, first["lease_token"])
    assert store.update(str(job.job_id), {"status": "failed"}, second["lease_token"])


def test_lambda_never_falls_back_to_local_disk(monkeypatch):
    get_job_store.cache_clear()
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "cookish-ai")
    monkeypatch.delenv("AI_JOB_BACKEND", raising=False)
    with pytest.raises(ValueError, match="Lambda requires"):
        get_job_store()
    get_job_store.cache_clear()


def test_sqs_failure_shortens_visibility_and_keeps_the_message_for_retry(
    store, image_payload, monkeypatch
):
    from types import SimpleNamespace

    from app.model_client import ModelUnavailable

    class UnavailableClient:
        model_id = "unavailable"

        def generate(self, request):
            raise ModelUnavailable("Unavailable")

    image_jobs.submit_image_job(ParseImageRequest(**image_payload), "alice", uuid4(), store)
    message = store.sqs.receive_message(QueueUrl=store.queue_url)["Messages"][0]
    delays = []
    original = store.defer

    def defer(receipt, seconds):
        delays.append(seconds)
        original(receipt, seconds)

    monkeypatch.setattr(store, "defer", defer)
    monkeypatch.setattr(job_worker, "get_job_store", lambda: store)
    monkeypatch.setattr(job_worker, "get_client", UnavailableClient)
    response = job_worker.handler(
        {
            "Records": [
                {
                    "messageId": message["MessageId"],
                    "body": message["Body"],
                    "receiptHandle": message["ReceiptHandle"],
                }
            ]
        },
        SimpleNamespace(get_remaining_time_in_millis=lambda: 120000),
    )
    assert response == {"batchItemFailures": [{"itemIdentifier": message["MessageId"]}]}
    assert delays == [30]
