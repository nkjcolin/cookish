"""Conservative receipt checks for failures observed during local model testing.

These guards are not a general food classifier or independent OCR. Receipt layout,
quantity evidence and pack-size interpretation belong to the model prompt.
quantities.py multiplies extracted factors before these guards. Keep positive
total quantities; normalize unit spellings and default only an
unmeasured missing amount to one purchase unit. Unknown measured amounts and
invalid numeric values remain unknown for review. Only a null unit defaults to pcs.
"""

import re

from app.drafts import normalize_draft
from app.schemas import DraftItem, DraftResult

_NON_FOOD = re.compile(
    r"\b(?:toothpaste|toothbrush(?:es)?|dental floss|mouthwash|shampoo|hair conditioner|"
    r"shaving cream|razor blades?|disposable razors?|detergent|dishwashing|laundry|"
    r"bleach|batter(?:y|ies)|hangers?|table\s*ware|toilet paper|paper towels?|"
    r"pet food|dog food|cat food|alkaline\s+a{1,3})\b",
    re.IGNORECASE,
)
_NON_FOOD_NAMES = {
    "total",
    "subtotal",
    "sub total",
    "tax",
    "gst",
    "payment",
    "discount",
    "coupon",
    "deposit",
    "change",
    "plastic bag",
    "carrier bag",
    "shopping bag",
    "paper bag",
}


def _non_food(item: DraftItem) -> bool:
    raw = (item.raw_text or "").casefold()
    name = item.display_name.casefold()
    # Split compact product codes such as RAZOR2UP2S before checking whole words.
    original = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", raw)
    if _NON_FOOD.search(original) or _NON_FOOD.search(name):
        return True
    if " ".join(name.split()) in _NON_FOOD_NAMES:
        return True
    # A food name invented from a grooming product must not override its raw text.
    # Explicit RAZOR CLAMS on the receipt, however, is legitimate food.
    return bool(re.search(r"\brazors?\b", original)) and not bool(
        re.search(r"\bclams?\b", original)
    )


def default_receipt_units(draft: DraftResult) -> DraftResult:
    """Final fallback only: preserve every non-null unit returned by the model."""
    return DraftResult(
        items=[
            item.model_copy(update={"unit": "pcs"}) if item.unit is None else item
            for item in draft.items
        ]
    )


def finalize_receipt_quantities(draft: DraftResult) -> DraftResult:
    """Canonicalize resolved totals once without redoing package arithmetic."""
    normalized = normalize_draft(draft)
    purchase_units = {None, "pcs", "pack", "bottle", "can", "jar", "carton", "bag", "box", "tray"}
    items = []
    for original, item in zip(draft.items, normalized.items, strict=True):
        # A null measured amount is unknown, not one gram/millilitre. Invalid
        # numeric values also stay unknown instead of becoming a purchase default.
        if original.count is None and item.unit in purchase_units:
            item = item.model_copy(update={"count": 1.0})
        items.append(item)
    return default_receipt_units(DraftResult(items=items))


def clean_receipt(draft: DraftResult) -> DraftResult:
    return finalize_receipt_quantities(
        DraftResult(items=[item for item in draft.items if not _non_food(item)])
    )
