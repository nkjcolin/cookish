import pytest

from app.drafts import normalize_draft
from app.quantities import ExtractionResult, resolve_quantities
from app.receipts import finalize_receipt_quantities


def extracted(factors, unit, *, model_count=550):
    return ExtractionResult.model_validate(
        {
            "items": [
                {
                    "raw_text": "Original purchase and contents evidence",
                    "display_name": "Food",
                    "count": model_count,
                    "unit": unit,
                    "storage": None,
                    "confidence": 0.9,
                    "quantity": {"factors": factors, "unit": unit},
                }
            ]
        }
    )


@pytest.mark.parametrize(
    "factors,unit,count,expected_unit",
    [
        ([2, 225], "g", 450, "g"),
        ([2, 3, 125], "g", 750, "g"),
        ([2, 0.5], "kg", 1, "kg"),
        ([3, 0.25], "l", 0.75, "l"),
        ([2, 12], "pcs", 24, "pcs"),
        ([350], "g", 350, "g"),
        ([2], "pack", 2, "pack"),
    ],
)
def test_python_calculates_products_and_single_totals(factors, unit, count, expected_unit):
    source = extracted(factors, unit)
    draft = finalize_receipt_quantities(resolve_quantities(source))
    assert (draft.items[0].count, draft.items[0].unit) == (count, expected_unit)
    assert draft.items[0].raw_text == source.items[0].raw_text
    assert source.items[0].count == 550
    assert "quantity" not in draft.model_dump()["items"][0]
    assert finalize_receipt_quantities(draft) == draft


@pytest.mark.parametrize("unit", ["g", "ml", "kg", "l"])
def test_unknown_measurement_does_not_use_model_guess_or_one_gram_default(unit):
    draft = finalize_receipt_quantities(resolve_quantities(extracted(None, unit, model_count=1)))
    assert draft.items[0].count is None


@pytest.mark.parametrize("factors", [[], [0], [-1], [float("nan")], [float("inf")], [1e308, 1e308]])
@pytest.mark.parametrize("unit", ["g", "pack", None])
def test_invalid_factors_never_become_receipt_default(factors, unit):
    draft = finalize_receipt_quantities(resolve_quantities(extracted(factors, unit)))
    assert draft.items[0].count is None
    assert "NaN" not in draft.model_dump_json()
    assert "Infinity" not in draft.model_dump_json()


def test_missing_evidence_preserves_receipt_defaults_only_for_receipts():
    resolved = resolve_quantities(extracted(None, None, model_count=None))
    text = normalize_draft(resolved)
    receipt = finalize_receipt_quantities(resolved)
    assert (text.items[0].count, text.items[0].unit) == (None, None)
    assert (receipt.items[0].count, receipt.items[0].unit) == (1, "pcs")


def test_evidence_measurement_unit_is_not_replaced_by_model_package_unit():
    source = extracted([2, 250], "ml")
    source.items[0].unit = "bottle"
    item = finalize_receipt_quantities(resolve_quantities(source)).items[0]
    assert (item.count, item.unit) == (500, "ml")


@pytest.mark.parametrize(
    "raw,factors,unit,count,original_unit",
    [
        ("FOOD 1KG\n2X$3.50/Unit", [2, 1000], "g", 2, "kg"),
        ("FOOD 450G", [0.45], "kg", 450, "g"),
        ("FOOD 1L", [1000], "ml", 1, "l"),
        ("FOOD 250ML", [0.25], "l", 250, "ml"),
        ("FOOD 0.35 KG @ $8.00/KG", [350], "g", 0.35, "kg"),
        ("FOOD 1 kilogram", [1000], "g", 1, "kg"),
        ("FOOD 1KG / 1000G", [1000], "g", 1000, "g"),
        ("FOOD $3.50/KG", [350], "g", 350, "g"),
        ("FOOD $3.50KG", [350], "g", 350, "g"),
        (None, [1], "kg", 1, "kg"),
    ],
)
def test_original_measurement_scale_survives_model_rescaling(
    raw, factors, unit, count, original_unit
):
    source = extracted(factors, unit)
    source.items[0].raw_text = raw
    result = finalize_receipt_quantities(resolve_quantities(source)).items[0]
    assert (result.count, result.unit) == (count, original_unit)
    assert result.raw_text == raw
