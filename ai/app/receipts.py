"""Conservative receipt checks for failures observed during local model testing.

These guards are not a general food classifier or independent OCR. Receipt layout,
quantity evidence first comes from the model. quantities.py multiplies extracted
factors; explicit copied receipt text then checks supported sizes and multipliers.
Normalize unit spellings and default only an
unmeasured missing amount to one purchase unit. Unknown measured amounts and
invalid numeric values remain unknown for review. Only a null unit defaults to pcs.
"""

from app.drafts import normalize_draft
from app.food_filter import filter_receipt_foods
from app.receipt_evidence import reconcile_receipt_amount
from app.schemas import DraftResult


def default_receipt_units(draft: DraftResult) -> DraftResult:
    """Final fallback only: preserve every non-null unit returned by the model."""
    return DraftResult(
        items=[
            item.model_copy(update={"unit": "pcs"}) if item.unit is None else item
            for item in draft.items
        ]
    )


def finalize_receipt_quantities(draft: DraftResult) -> DraftResult:
    """Normalize totals, then rebuild only quantities supported by copied text."""
    normalized = normalize_draft(draft)
    purchase_units = {None, "pcs", "pack", "bottle", "can", "jar", "carton", "bag", "box", "tray"}
    items = []
    for original, item in zip(draft.items, normalized.items, strict=True):
        # A null measured amount is unknown, not one gram/millilitre. Invalid
        # numeric values also stay unknown instead of becoming a purchase default.
        if original.count is None and item.unit in purchase_units:
            item = item.model_copy(update={"count": 1.0})
        items.append(reconcile_receipt_amount(item))
    return default_receipt_units(DraftResult(items=items))


def clean_receipt(draft: DraftResult) -> DraftResult:
    return finalize_receipt_quantities(filter_receipt_foods(draft))
