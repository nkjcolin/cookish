"""Unit spelling and numeric consistency, without pretending to perform OCR."""

import math
import re

from app.schemas import DraftResult

_UNITS = {
    "gram": "g",
    "grams": "g",
    "g": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "kg": "kg",
    "milliliter": "ml",
    "milliliters": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    "ml": "ml",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    "litres": "l",
    "l": "l",
    "piece": "pcs",
    "pieces": "pcs",
    "pc": "pcs",
    "pcs": "pcs",
    "packs": "pack",
    "bottles": "bottle",
    "cans": "can",
    "jars": "jar",
}


# Words that say an amount exists without saying how much. "some onion" is an onion of
# unknown amount, not 1 of a unit called "some".
_VAGUE = {
    "some",
    "few",
    "a few",
    "several",
    "bit",
    "a bit",
    "little",
    "a little",
    "handful",
    "a handful",
    "any",
}
_STARTS_VAGUE = re.compile(
    r"^\s*(some|a few|several|a bit of|a little|a handful of)\b(?!.*\d)", re.IGNORECASE
)


def is_vague_amount(unit: str | None, raw_text: str | None) -> bool:
    """A vague quantifier used as the unit, or opening a description with no number in it."""
    word = (unit or "").strip().lower()
    return word in _VAGUE or bool(raw_text and _STARTS_VAGUE.match(raw_text))


def normalize_unit(unit: str | None) -> str | None:
    """Normalize spelling only; kg and g remain different units."""
    unit = (unit or "").strip().lower() or None
    return _UNITS.get(unit, unit)


def normalize_draft(draft: DraftResult) -> DraftResult:
    """Normalize spelling, preserving measurement scale and total quantity.

    A vague amount ("some onion", "a few eggs") stays unknown: count and unit are null.
    """
    items = []
    for item in draft.items:
        unit = normalize_unit(item.unit)
        count = item.count
        if count is not None and (not math.isfinite(count) or count <= 0):
            count = None
        if is_vague_amount(item.unit, item.raw_text):
            count, unit = None, None
        items.append(item.model_copy(update={"count": count, "unit": unit}))
    return DraftResult(items=items)
