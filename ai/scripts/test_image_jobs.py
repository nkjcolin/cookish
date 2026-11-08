"""No-cloud acceptance check: HTTP requests stay short during a 45-second worker call.

Run from ai/: uv run python scripts/test_image_jobs.py
Uses temporary local files and a fake model; never reads .env or AWS credentials.
"""

import argparse
import base64
import json
import multiprocessing
import os
import sys
import tempfile
import time
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import anyio  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.job_store import LocalJobStore  # noqa: E402
from app.job_worker import process_job  # noqa: E402
from app.main import app, job_store  # noqa: E402
from app.model_client import FakeModelClient  # noqa: E402


class DelayedModel(FakeModelClient):
    def __init__(self, delay: float):
        self.delay = delay

    def generate(self, request):
        time.sleep(self.delay)
        return super().generate(request)


def worker(directory: str, job_id: str, delay: float):
    context = SimpleNamespace(get_remaining_time_in_millis=lambda: 120000)
    assert anyio.run(
        process_job, job_id, LocalJobStore(Path(directory)), DelayedModel(delay), context
    )


async def lambda_http(scope, receive, send):
    if scope["type"] == "http":
        scope["aws.context"] = SimpleNamespace(get_remaining_time_in_millis=lambda: 120000)
        scope["aws.event"] = {
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "d041df63-1dc7-4f26-a88b-9b25757b0037"}}}
            }
        }
    await app(scope, receive, send)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delay", type=float, default=45)
    args = parser.parse_args()
    if not 27 < args.delay < 90:
        parser.error("--delay must exceed 27 seconds and be below 90")
    os.environ["AI_PROVIDER"] = "fake"
    os.environ["AI_REQUEST_TIMEOUT_SECONDS"] = "27"
    os.environ["AI_WORKER_TIMEOUT_SECONDS"] = "110"
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format="PNG")
    body = {
        "kind": "photo",
        "media_type": "image/png",
        "image_base64": base64.b64encode(buffer.getvalue()).decode(),
    }
    with tempfile.TemporaryDirectory(prefix="cookish-image-job-") as directory:
        store = LocalJobStore(Path(directory))
        app.dependency_overrides[job_store] = lambda: store
        process = None
        started = time.monotonic()
        try:
            with TestClient(lambda_http) as client:
                before = time.monotonic()
                submitted = client.post(
                    "/ai/image-jobs", json=body, headers={"Idempotency-Key": str(uuid4())}
                )
                submit_seconds = time.monotonic() - before
                assert submitted.status_code == 202, submitted.text
                assert submit_seconds < 5
                job_id = submitted.json()["job_id"]
                process = multiprocessing.get_context("spawn").Process(
                    target=worker, args=(directory, job_id, args.delay)
                )
                process.start()
                observed_past_27 = False
                max_poll_seconds = 0.0
                while time.monotonic() - started < args.delay + 20:
                    before = time.monotonic()
                    result = client.get(f"/ai/image-jobs/{job_id}")
                    max_poll_seconds = max(max_poll_seconds, time.monotonic() - before)
                    assert result.status_code == 200, result.text
                    value = result.json()
                    elapsed = time.monotonic() - started
                    if elapsed > 27 and value["status"] == "processing":
                        if not observed_past_27:
                            print(
                                "PASS: still processing beyond 27 seconds; polling works",
                                flush=True,
                            )
                        observed_past_27 = True
                    if value["status"] == "completed":
                        assert observed_past_27 and value["result"]["items"]
                        assert max_poll_seconds < 5
                        process.join(timeout=5)
                        assert process.exitcode == 0
                        print(
                            json.dumps(
                                {
                                    "passed": True,
                                    "provider": "delayed_fake",
                                    "separate_worker_process": True,
                                    "lambda_http_context": True,
                                    "http_budget_seconds": 27,
                                    "model_delay_seconds": args.delay,
                                    "submit_seconds": round(submit_seconds, 3),
                                    "max_poll_seconds": round(max_poll_seconds, 3),
                                    "elapsed_seconds": round(elapsed, 3),
                                    "status": value["status"],
                                }
                            ),
                            flush=True,
                        )
                        return
                    assert value["status"] != "failed", value
                    time.sleep(1)
                raise AssertionError("Job did not finish within the local acceptance window")
        finally:
            if process is not None and process.is_alive():
                process.terminate()
                process.join(timeout=5)
            app.dependency_overrides.clear()


if __name__ == "__main__":
    main()
