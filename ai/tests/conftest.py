from collections.abc import Iterator
from pathlib import Path

import pytest

from app.matching import get_catalogue

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def catalogue(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Every test reads the small fixture catalogue, never the real seed file."""
    monkeypatch.setenv("INGREDIENTS_CSV", str(FIXTURES / "ingredients.csv"))
    get_catalogue.cache_clear()
    yield
    get_catalogue.cache_clear()
