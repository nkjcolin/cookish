import pytest

from app.receipts import finalize_receipt_quantities
from app.schemas import DraftItem, DraftResult


def reconcile(raw, count, unit):
    original = DraftResult(
        items=[
            DraftItem(
                raw_text=raw,
                display_name="Food",
                count=count,
                unit=unit,
                storage=None,
                confidence=0.9,
            )
        ]
    )
    result = finalize_receipt_quantities(original)
    assert result.items[0].raw_text == raw
    assert original.items[0].count == count
    assert finalize_receipt_quantities(result) == result
    return result.items[0].count, result.items[0].unit


@pytest.mark.parametrize(
    "raw,count,unit,expected",
    [
        ("CEREAL 500G", 1000, "g", (500, "g")),
        ("JUICE 750ML", 1, "ml", (750, "ml")),
        ("RICE 1KG", 1000, "kg", (1, "kg")),
        ("CEREAL 500G\n2X$3.50/Unit", 1000, "g", (1000, "g")),
        ("CEREAL 500G\n2 X 3.50/UNIT    7.00", 1, "g", (1000, "g")),
        ("CEREAL 500G\\n2X$3.50/Unit", 1, "g", (1000, "g")),
        ("2 CEREAL 500G\nUNIT PRICE 3.50", 1, "pcs", (1000, "g")),
        ("CEREAL 500G Qty: 3", 500, "g", (1500, "g")),
        ("CEREAL 500G\n3", 500, "g", (1500, "g")),
        ("CEREAL 500G x 3", 500, "g", (1500, "g")),
        ("CEREAL 2X3X125G", 1, "g", (750, "g")),
        ("CEREAL 500G\nNET 500G\nQTY 2\n2X$3.00/UNIT", 500, "g", (1000, "g")),
        ("CEREAL 500G\nTOTAL WEIGHT 1KG\nQTY 2", 2000, "g", (1, "kg")),
        ("BEANS NET 400G DRAINED 240G\nQTY 2", 800, "g", (480, "g")),
        ("TOFU 2S 350G", 700, "g", (350, "g")),
        ("FRUIT 6 PCS", 1, "pcs", (6, "pcs")),
        ("FOOD 0.45 KG @ $8.00/KG", 450, "g", (0.45, "kg")),
        ("FOOD 500G / 0.5KG", 0.5, "kg", (0.5, "kg")),
        ("FOOD $5.50/KG", 0.45, "kg", (0.45, "kg")),
        ("FOOD $5.50KG", 0.45, "kg", (0.45, "kg")),
        ("FOOD 500G\nUNIT PRICE $2.00/100G", 1, "g", (500, "g")),
        ("FOOD\nPRICE $ 5.50 KG", 0.45, "kg", (0.45, "kg")),
        ("FOOD\n$ 5.50KG", 0.45, "kg", (0.45, "kg")),
        ("FOOD", None, None, (1, "pcs")),
        ("FOOD 500G", None, "g", (500, "g")),
    ],
)
def test_explicit_receipt_evidence_corrects_totals_without_changing_scale(
    raw, count, unit, expected
):
    assert reconcile(raw, count, unit) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "FOOD 500G / 750G",
        "FOOD 500G\nQTY 2\n3X$2.00/UNIT",
        "FOOD 2X125G\nQTY 2",
        "FOOD 500G 3",
        "5 GRAIN BREAD 500G",
        "FOOD 0G",
        "FOOD 500G\nQTY 0",
        "FOOD 500G\nQTY 2.5",
    ],
)
def test_ambiguous_or_invalid_receipt_evidence_stays_unknown(raw):
    count, unit = reconcile(raw, 1, "g")
    assert count is None and unit == "g"
