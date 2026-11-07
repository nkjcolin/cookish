import pytest

from app.drafts import normalize_draft
from app.schemas import DraftItem, DraftResult


@pytest.mark.parametrize(
    "unit,expected,expected_count",
    [
        (" KG ", "kg", 2),
        ("litres", "l", 2),
        ("millilitres", "ml", 2),
        ("pieces", "pcs", 2),
        ("bottles", "bottle", 2),
        ("", None, 2),
        (None, None, 2),
    ],
)
def test_unit_normalization_does_not_convert_pack_contents(unit, expected, expected_count):
    item = DraftItem(
        raw_text="FOOD 500G",
        display_name="Food",
        count=2,
        unit=unit,
        storage=None,
        confidence=0.9,
    )
    result = normalize_draft(DraftResult(items=[item])).items[0]
    assert result.unit == expected and result.count == expected_count
    assert result.raw_text == item.raw_text


@pytest.mark.parametrize("count", [0, -1, float("nan"), float("inf")])
def test_invalid_numbers_are_unknown_without_receipt_defaults(count):
    item = DraftItem(
        raw_text=None,
        display_name="Food",
        count=count,
        unit="kg",
        storage=None,
        confidence=0.9,
    )
    assert normalize_draft(DraftResult(items=[item])).items[0].count is None


@pytest.mark.parametrize(
    "count,unit,expected_count,expected_unit",
    [(0.35, "kg", 0.35, "kg"), (0.66, "l", 0.66, "l"), (1e308, "kg", 1e308, "kg")],
)
def test_metric_totals_preserve_the_original_scale(count, unit, expected_count, expected_unit):
    item = DraftItem(
        raw_text="printed amount",
        display_name="Food",
        count=count,
        unit=unit,
        storage=None,
        confidence=0.9,
    )
    result = normalize_draft(DraftResult(items=[item])).items[0]
    assert (result.count, result.unit) == (expected_count, expected_unit)


def test_already_totalled_package_contents_are_not_multiplied_again():
    item = DraftItem(
        raw_text="FOOD 225G\n2X$1.50/Unit",
        display_name="Food",
        count=450,
        unit="g",
        storage=None,
        confidence=0.9,
    )
    once = normalize_draft(DraftResult(items=[item]))
    twice = normalize_draft(once)
    assert once == twice
    assert once.items[0].count == 450
    assert once.items[0].raw_text == item.raw_text


@pytest.mark.parametrize(
    "raw_text,count,unit",
    [
        ("some onion", 1, "some"),  # the model used the quantifier as a unit
        ("some onion", 1, "pcs"),  # or guessed a count the user never gave
        ("a few eggs", 3, "pcs"),
        ("A handful of spinach", 1, "handful"),
        ("onion", 1, "a bit"),
    ],
)
def test_vague_amounts_stay_unknown(raw_text, count, unit):
    item = DraftItem(
        raw_text=raw_text,
        display_name="Food",
        count=count,
        unit=unit,
        storage=None,
        confidence=0.9,
    )
    result = normalize_draft(DraftResult(items=[item])).items[0]
    assert (result.count, result.unit) == (None, None)
    assert result.raw_text == raw_text


@pytest.mark.parametrize(
    "raw_text,count,unit",
    [("2 onions", 2, "pcs"), ("some 500g of rice", 500, "g"), ("handful bag 200g", 200, "g")],
)
def test_stated_amounts_are_kept(raw_text, count, unit):
    item = DraftItem(
        raw_text=raw_text,
        display_name="Food",
        count=count,
        unit=unit,
        storage=None,
        confidence=0.9,
    )
    result = normalize_draft(DraftResult(items=[item])).items[0]
    assert (result.count, result.unit) == (count, unit)
