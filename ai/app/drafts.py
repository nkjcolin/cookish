"""Unit spelling and numeric consistency, without pretending to perform OCR."""

import math

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


def normalize_unit(unit: str | None) -> str | None:
    """Normalize spelling only; kg and g remain different units."""
    unit = (unit or "").strip().lower() or None
    return _UNITS.get(unit, unit)


def normalize_draft(draft: DraftResult) -> DraftResult:
    """Normalize spelling, preserving measurement scale and total quantity."""
    items = []
    for item in draft.items:
        unit = normalize_unit(item.unit)
        count = item.count
        if count is not None and (not math.isfinite(count) or count <= 0):
            count = None
        items.append(item.model_copy(update={"count": count, "unit": unit}))
    return DraftResult(items=items)
