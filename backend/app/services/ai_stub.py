"""Local stand-in for the `ai` Lambda. Role 4 builds the real one in /ai.

On AWS, API Gateway sends /ai/* to that Lambda, so this module is never reached there.
It exists so that one local server and one OpenAPI file cover the whole contract.
"""

from app import mock
from app.schemas.ai import (
    DraftItem,
    DraftResult,
    InterpretRequest,
    InterpretResult,
    ParseImageRequest,
    ParseItemsRequest,
)
from app.schemas.common import Storage
from app.schemas.cook import CookAdjust, CookTag


def _draft() -> DraftResult:
    ing = mock.INGREDIENTS
    return DraftResult(
        items=[
            DraftItem(
                raw_text="FP FRESH EGGS 10S",
                ingredient_id=ing["egg"].id,
                display_name="Egg",
                count=10,
                unit="pcs",
                storage=Storage.FRIDGE,
                confidence=0.94,
            ),
            DraftItem(
                raw_text="CABBAGE RND",
                ingredient_id=ing["cabbage"].id,
                display_name="Cabbage",
                count=None,
                unit=None,
                storage=Storage.FRIDGE,
                confidence=0.88,
            ),
            DraftItem(
                raw_text="KKM SAMBAL 230G",
                ingredient_id=None,
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
