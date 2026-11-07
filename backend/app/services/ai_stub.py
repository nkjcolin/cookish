"""Local stand-in for the `ai` Lambda. Role 4 builds the real one in /ai.

On AWS, API Gateway sends /ai/* to that Lambda, and `docker compose up` sends it to the
ai service, so this module only answers when the backend runs on its own. It exists so
that one OpenAPI file covers the whole contract.
"""

from app.schemas.ai import (
    DraftItem,
    DraftResult,
    InterpretRequest,
    InterpretResult,
    ParseImageRequest,
    ParseItemsRequest,
    TranscribeAudioRequest,
    TranscriptionResult,
)
from app.schemas.common import Storage
from app.schemas.cook import CookAdjust, CookTag


def _draft() -> DraftResult:
    return DraftResult(
        items=[
            DraftItem(
                raw_text="FP FRESH EGGS 10S",
                display_name="Egg",
                count=10,
                unit="pcs",
                storage=Storage.FRIDGE,
                confidence=0.94,
            ),
            DraftItem(
                raw_text="CABBAGE RND",
                display_name="Cabbage",
                count=None,
                unit=None,
                storage=Storage.FRIDGE,
                confidence=0.88,
            ),
            DraftItem(
                raw_text="KKM SAMBAL 230G",
                display_name="Sambal",
                count=1,
                unit="jar",
                storage=None,
                confidence=0.41,
            ),
        ]
    )


def parse_image(body: ParseImageRequest) -> DraftResult:
    return _draft()


def parse_items(body: ParseItemsRequest) -> DraftResult:
    return _draft()


def interpret(body: InterpretRequest) -> InterpretResult:
    return InterpretResult(adjust=CookAdjust(tags=[CookTag.QUICKER], max_minutes=20))


def transcribe_audio(body: TranscribeAudioRequest) -> TranscriptionResult:
    return TranscriptionResult(text="two packs of tofu and some kangkong")
