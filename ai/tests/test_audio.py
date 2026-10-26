import base64
import json
import time
from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.audio import MAX_AUDIO_BYTES
from app.config import Settings
from app.main import app
from app.model_client import SchoolModelClient, get_client

SETTINGS = Settings(
    provider="soclaas",
    base_url="https://school.example/v1/",
    model="vision-model",
    text_model="list-model",
    audio_model="speech-model",
    api_key="private-test-key",
)


@pytest.fixture
def speech():
    clients = []

    def install(*answers, settings=SETTINGS, delay=0):
        requests = []
        remaining = iter(answers)

        def respond(request):
            if request.method == "GET":
                return httpx.Response(200, json={"data": []})
            requests.append(request)
            time.sleep(delay)
            answer = next(remaining)
            if isinstance(answer, Exception):
                raise answer
            return (
                answer if isinstance(answer, httpx.Response) else httpx.Response(200, json=answer)
            )

        model = SchoolModelClient(
            settings, http_client=httpx.Client(transport=httpx.MockTransport(respond))
        )
        clients.append(model)
        app.dependency_overrides[get_client] = lambda: model
        return requests

    yield install
    app.dependency_overrides.clear()
    for client in clients:
        client.close()


def test_transcription_uploads_multipart_and_preserves_text(speech, audio_payload, caplog):
    transcript = "Four eggs, two hundred grams of rice, and four potatoes."
    requests = speech({"text": transcript})
    response = TestClient(app).post("/ai/transcribe-audio", json=audio_payload)
    assert response.status_code == 200
    assert response.json() == {"text": transcript}
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://school.example/v1/audio/transcriptions"
    assert request.headers["Authorization"] == "Bearer private-test-key"
    assert request.headers["Content-Type"].startswith("multipart/form-data;")
    assert base64.b64decode(audio_payload["audio_base64"]) in request.content
    assert b'filename="recording.wav"' in request.content
    assert b"Content-Type: audio/wav" in request.content
    assert b'name="model"\r\n\r\nspeech-model' in request.content
    assert b'name="language"\r\n\r\nen' in request.content
    assert b'name="response_format"\r\n\r\njson' in request.content
    assert response.headers["x-ai-model"] == "speech-model"
    assert response.headers["x-ai-provider"] == "soclaas"
    assert response.headers["x-ai-attempts"] == "1"
    assert "x-ai-input-tokens" not in response.headers
    assert transcript not in caplog.text
    assert audio_payload["audio_base64"] not in caplog.text
    assert "private-test-key" not in caplog.text


def test_language_detection_can_be_requested(speech, audio_payload):
    requests = speech({"text": "eggs"})
    response = TestClient(app).post(
        "/ai/transcribe-audio", json={**audio_payload, "language": None}
    )
    assert response.status_code == 200
    assert b'name="language"' not in requests[0].content


@pytest.mark.parametrize(
    "changes",
    [
        {"audio_base64": "%%%"},
        {"audio_base64": "data:audio/wav;base64,AAAA"},
        {"audio_base64": ""},
        {"audio_base64": base64.b64encode(b"not a valid audio file").decode()},
        {"media_type": "audio/webm"},
        {"media_type": "image/png"},
        {"language": "english"},
        {"model": "client-cannot-select-model"},
    ],
)
def test_invalid_input_never_reaches_school(speech, audio_payload, changes):
    requests = speech()
    response = TestClient(app).post("/ai/transcribe-audio", json={**audio_payload, **changes})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION"
    assert not requests


def test_oversized_audio_is_rejected_without_echoing_upload(speech):
    requests = speech()
    encoded = base64.b64encode(b"RIFF" + b"x" * MAX_AUDIO_BYTES).decode()
    response = TestClient(app).post(
        "/ai/transcribe-audio", json={"media_type": "audio/wav", "audio_base64": encoded}
    )
    assert response.status_code == 422
    assert encoded not in response.text
    assert not requests


@pytest.mark.parametrize(
    "answer",
    [
        {"text": ""},
        {"text": "  "},
        {"text": None},
        {"unexpected": "no transcript"},
        httpx.Response(200, text="not JSON"),
        httpx.Response(429, json={"error": "private upstream body"}),
        httpx.Response(500, json={"error": "private upstream body"}),
        httpx.ReadTimeout("private upstream body"),
    ],
)
def test_provider_errors_are_safe_and_not_retried(speech, audio_payload, answer):
    requests = speech(answer)
    response = TestClient(app).post("/ai/transcribe-audio", json=audio_payload)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    assert "private upstream body" not in response.text
    assert len(requests) == 1


def test_missing_speech_model_never_falls_back_to_vision_model(speech, audio_payload):
    requests = speech(settings=replace(SETTINGS, audio_model=None))
    response = TestClient(app).post("/ai/transcribe-audio", json=audio_payload)
    assert response.status_code == 503
    assert not requests


def test_request_deadline_applies_to_transcription(speech, audio_payload, monkeypatch):
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "0.05")
    requests = speech({"text": "eggs"}, delay=0.3)
    started = time.monotonic()
    response = TestClient(app).post("/ai/transcribe-audio", json=audio_payload)
    assert time.monotonic() - started < 0.25
    assert response.status_code == 503
    assert len(requests) == 1
    assert 0 < requests[0].extensions["timeout"]["read"] <= 0.05


def test_transcript_can_be_passed_to_existing_voice_parser(speech, audio_payload):
    transcript = "Four eggs, two hundred grams of rice, and four potatoes."
    requests = speech(
        {"text": transcript},
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "raw_text": name,
                                        "display_name": name,
                                        "count": count,
                                        "unit": unit,
                                        "storage": None,
                                        "confidence": 0.9,
                                    }
                                    for name, count, unit in [
                                        ("Egg", 4, "pcs"),
                                        ("Rice", 200, "g"),
                                        ("Potato", 4, "pcs"),
                                    ]
                                ]
                            }
                        )
                    }
                }
            ]
        },
    )
    client = TestClient(app)
    text_response = client.post("/ai/transcribe-audio", json=audio_payload)
    result = client.post(
        "/ai/parse-items", json={"text": text_response.json()["text"], "source": "voice"}
    )
    assert result.status_code == 200
    assert [(item["count"], item["unit"]) for item in result.json()["items"]] == [
        (4, "pcs"),
        (200, "g"),
        (4, "pcs"),
    ]
    assert "Input source: voice" in json.loads(requests[1].content)["messages"][1]["content"]
    assert json.loads(requests[1].content)["model"] == "list-model"


def test_fake_transcription_is_explicit_and_offline(audio_payload):
    response = TestClient(app).post("/ai/transcribe-audio", json=audio_payload)
    assert response.status_code == 200
    assert response.json()["text"].startswith("Four eggs")
    assert response.headers["x-ai-provider"] == "fake"
