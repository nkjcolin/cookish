import base64
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import images
from app.main import app


@pytest.mark.parametrize(
    "media_type,format", [("image/jpeg", "JPEG"), ("image/png", "PNG"), ("image/webp", "WEBP")]
)
def test_supported_still_images(media_type, format) -> None:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format=format)
    images.validate_image(media_type, base64.b64encode(buffer.getvalue()).decode("ascii"))


@pytest.mark.parametrize(
    "encoded", ["!invalid!", "aGVsbG8=", "é", "data:image/png;base64,aGVsbG8="]
)
def test_invalid_image_returns_the_existing_error_envelope(encoded) -> None:
    response = TestClient(app).post(
        "/ai/parse-image", json={"kind": "receipt", "image_base64": encoded}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION"
    assert response.json()["error"]["details"] == {"field": "image_base64"}


def test_declared_type_must_match_image_content(image_payload) -> None:
    response = TestClient(app).post(
        "/ai/parse-image", json={**image_payload, "media_type": "image/jpeg"}
    )
    assert response.status_code == 422


def test_oversized_payload_is_rejected_before_decoding(monkeypatch, image_payload) -> None:
    monkeypatch.setattr(images, "MAX_IMAGE_BYTES", 10)
    response = TestClient(app).post("/ai/parse-image", json=image_payload)
    assert response.status_code == 422
    assert "limit" in response.json()["error"]["message"]


@pytest.mark.parametrize("limit", ["MAX_IMAGE_EDGE", "MAX_IMAGE_PIXELS"])
def test_dimension_limits(monkeypatch, image_payload, limit) -> None:
    monkeypatch.setattr(images, limit, 10)
    response = TestClient(app).post("/ai/parse-image", json=image_payload)
    assert response.status_code == 422
    assert "dimensions" in response.json()["error"]["message"]


def test_truncated_image_is_rejected(image_payload) -> None:
    data = base64.b64decode(image_payload["image_base64"])[:-15]
    response = TestClient(app).post(
        "/ai/parse-image",
        json={**image_payload, "image_base64": base64.b64encode(data).decode("ascii")},
    )
    assert response.status_code == 422
