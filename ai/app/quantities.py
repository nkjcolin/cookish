"""Private model evidence: extract printed factors, calculate totals in Python."""

import math
import re
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.drafts import normalize_unit
from app.schemas import DraftItem, DraftResult

_MEASURE = re.compile(
    r"(?<![\d.$])\d+(?:\.\d+)?\s*"
    r"(kilograms?|kg|grams?|g|millilit(?:er|re)s?|ml|lit(?:er|re)s?|l)\b",
    re.IGNORECASE,
)
_SCALES = {"kg": ("mass", 1000), "g": ("mass", 1), "l": ("volume", 1000), "ml": ("volume", 1)}


def _restore_source_scale(item: DraftItem) -> DraftItem:
    """Undo model rescaling only when the source gives one unambiguous scale.

    Numeric amounts are not used to infer purchase counts or package sizes.
    Price-per-unit notation does not match the number-followed-by-unit pattern.
    """
    unit = normalize_unit(item.unit)
    if unit not in _SCALES or not _positive(item.count) or not item.raw_text:
        return item
    dimension, scale = _SCALES[unit]
    originals = {
        normalized
        for match in _MEASURE.finditer(item.raw_text)
        if (normalized := normalize_unit(match.group(1))) in _SCALES
        and _SCALES[normalized][0] == dimension
    }
    if len(originals) != 1:
        return item
    original = originals.pop()
    if original == unit:
        return item
    count = float(Decimal(str(item.count)) * scale / _SCALES[original][1])
    return item.model_copy(update={"count": count, "unit": original})


class QuantityEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factors: list[float] | None = Field(
        description=(
            "Original numeric quantity factors, before multiplication or unit conversion. "
            "Copy measured amounts in their printed/stated scale. Never rescale kg to g "
            "or litres to ml. Use one factor for an explicit total; null if unknown."
        )
    )
    unit: str | None = Field(
        description=(
            "Original unit attached to the measured amount in the source. "
            "Keep kg as kg, g as g, litres as l and ml as ml. Do not substitute a "
            "different measurement scale. Null only when no unit is identifiable."
        )
    )


class ExtractedItem(DraftItem):
    count: float | None = Field(
        default=None, description="Return null; the app multiplies factors."
    )
    quantity: QuantityEvidence | None = None


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ExtractedItem]


def _positive(value: float | None) -> bool:
    return value is not None and math.isfinite(value) and value > 0


def resolve_quantities(result: ExtractionResult) -> DraftResult:
    """Multiply explicit factors rather than trusting model arithmetic.

    A missing evidence object supports older scripted clients. Real strict-schema
    calls request the evidence object. A single printed total is one factor;
    package counts and contents are separate factors. Original text is checked
    only to restore an unambiguous printed scale, never to infer package counts.
    Shared draft cleanup normalizes spelling without converting to base units.
    """
    items = []
    for extracted in result.items:
        item = DraftItem.model_validate(extracted.model_dump(exclude={"quantity"}))
        evidence = extracted.quantity
        if evidence is None:
            items.append(item)
            continue
        unit = evidence.unit or item.unit
        count = None
        if evidence.factors is not None:
            if evidence.factors and all(_positive(value) for value in evidence.factors):
                product = Decimal(1)
                for factor in evidence.factors:
                    product *= Decimal(str(factor))
                count = float(product)
            else:
                # Shared cleanup clears invalid quantities without promoting
                # them to the receipt default for a genuinely absent count.
                count = float("nan")
        items.append(_restore_source_scale(item.model_copy(update={"count": count, "unit": unit})))
    return DraftResult(items=items)
