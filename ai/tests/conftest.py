import base64
import os
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.matching import get_catalogue
from app.model_client import get_client

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def offline_provider(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Tests never inherit a developer's real provider or credential settings."""
    for name in list(os.environ):
        if name.startswith("SOCLAAS_"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.delenv("AI_REQUEST_TIMEOUT_SECONDS", raising=False)
    get_client.cache_clear()
    yield
    get_client.cache_clear()


@pytest.fixture
def image_payload() -> dict[str, str]:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format="PNG")
    return {
        "kind": "receipt",
        "media_type": "image/png",
        "image_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
    }


@pytest.fixture(autouse=True)
def catalogue(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every test reads the small fixture catalogue, never the real seed file."""
    monkeypatch.setenv("INGREDIENTS_CSV", str(FIXTURES / "ingredients.csv"))
    get_catalogue.cache_clear()
    yield
    get_catalogue.cache_clear()
