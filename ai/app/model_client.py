"""The one place that talks to the model provider (SPEC B4).

STUB (Role 4): only FakeModelClient exists, which answers without any network call. Add
the real provider (Bedrock, OpenRouter, ...) as another class with the same `generate`
method, and select it with the AI_PROVIDER environment variable. Nothing else in the app
needs to change when the provider does.
"""

import json
import os
from dataclasses import dataclass
from functools import cache
from typing import Protocol

# A model call that takes longer is treated as unavailable (SPEC B4, Degradation).
TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class Image:
    media_type: str
    base64: str


@dataclass(frozen=True)
class ModelRequest:
    task: str  # receipt, photo, items or interpret; for logs (and the fake)
    system: str  # instructions, from app/prompts/
    text: str | None = None  # what the user typed or said; data, never instructions
    image: Image | None = None


@dataclass(frozen=True)
class ModelReply:
    text: str  # JSON, validated by the caller
    input_tokens: int
    output_tokens: int


class ModelUnavailable(Exception):
    """Timeout, throttling or any provider error. Becomes UPSTREAM_UNAVAILABLE."""


class ModelClient(Protocol):
    model_id: str

    def generate(self, request: ModelRequest) -> ModelReply: ...


# The same three items as backend/app/services/ai_stub.py, so the review screen looks the
# same whichever of the two answers. ingredient_id is filled in by app/matching.py.
_FAKE_DRAFT = {
    "items": [
        {
            "raw_text": "FP FRESH EGGS 10S",
            "ingredient_id": None,
            "display_name": "Egg",
            "count": 10,
            "unit": "pcs",
            "storage": "fridge",
            "confidence": 0.94,
        },
        {
            "raw_text": "CABBAGE RND",
            "ingredient_id": None,
            "display_name": "Cabbage",
            "count": None,
            "unit": None,
            "storage": "fridge",
            "confidence": 0.88,
        },
        {
            "raw_text": "KKM SAMBAL 230G",
            "ingredient_id": None,
            "display_name": "Sambal",
            "count": 1,
            "unit": "jar",
            "storage": None,
            "confidence": 0.41,
        },
    ]
}
_FAKE_ADJUST = {"tags": ["quicker"], "max_minutes": 20}


class FakeModelClient:
    """Fixed answers and no network. Used locally and in CI until a provider is chosen."""

    model_id = "fake"

    def generate(self, request: ModelRequest) -> ModelReply:
        reply = _FAKE_ADJUST if request.task == "interpret" else _FAKE_DRAFT
        return ModelReply(text=json.dumps(reply), input_tokens=0, output_tokens=0)


@cache
def get_client() -> ModelClient:
    provider = os.environ.get("AI_PROVIDER", "fake")
    if provider == "fake":
        return FakeModelClient()
    raise RuntimeError(f"Unknown AI_PROVIDER {provider!r}")
