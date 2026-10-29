"""Category evidence must beat invented names without becoming a food whitelist."""

import json
import logging
from pathlib import Path

import pytest

from app.food_filter import (
    RULES_PATH,
    FoodCategory,
    _load_rules,
    classify_receipt_item,
    filter_receipt_foods,
    normalize_description,
)
from app.schemas import DraftItem, DraftResult


def item(raw, name="Food", confidence=1):
    return DraftItem(
        raw_text=raw,
        display_name=name,
        count=4.4,
        unit="l",
        storage=None,
        confidence=confidence,
    )


@pytest.mark.parametrize(
    "raw,name",
    [
        ("TT P-GUM HLTH 110G", "chewing gum"),
        ("TT P-GUM HLTH 110G", "p-gum hlth"),
        ("TT P-GUM HLTH 110G", "chewing gum"),
        ("FP L/LQ DTG-C.C 4.4L", "distilled water"),
        ("FP L/LQ DTG-C.C 4.4L", "coconut milk"),
        ("TT P-GUM HLTH 110G", "p-gum health"),
        ("tt p.gum hlth110g\\n1X$3.90", "chewing gum"),
        ("ＦＰ Ｌ／ＬＱ ＤＴＧ－Ｃ．Ｃ ４．４Ｌ", "coconut milk"),
        ("COLGATE PRO GUM HEALTH 110G", "Food"),
    ],
)
def test_confirmed_raw_non_food_wins_over_confident_food_name(raw, name):
    decision = classify_receipt_item(item(raw, name))
    assert decision.category is FoodCategory.NON_FOOD
    assert decision.rule_id.startswith("retail_")


@pytest.mark.parametrize(
    "raw,name",
    [
        ("TT CHEWING GUM 110G", "chewing gum"),
        ("GUM 110G", "gum"),
        ("DTG 500G", "specialty food"),
        ("FP L/LQ 4.4L", "coconut milk"),
        ("P-GUM HLTH 110G", "unidentified product"),
        ("COCONUT MILK 200ML", "coconut milk"),
        ("ALKALINE WATER 1L", "water"),
        ("RAZOR CLAMS 500G", "razor clams"),
        ("BAKING POWDER 100G", "baking powder"),
        ("RICE PAPER 200G", "rice paper"),
        ("HAIRY GOURD 500G", "hairy gourd"),
        ("BATTERED FISH 200G", "fish"),
        ("BAG OF RICE 5KG", "rice"),
        ("A NEW EDIBLE SPECIES", "ingredient outside recipe catalogue"),
        (None, "coconut milk"),
    ],
)
def test_uncertain_or_edible_descriptions_are_not_removed(raw, name):
    original = item(raw, name, confidence=0.1)
    assert classify_receipt_item(original).category is not FoodCategory.NON_FOOD
    result = filter_receipt_foods(DraftResult(items=[original]))
    assert result.items == [original]
    assert result.items[0] is original


@pytest.mark.parametrize(
    "raw,name",
    [
        ("DOG FOOD 500G", "beef"),
        ("FP ALKALINE AAA8/PS", "water"),
        ("G LB601 RAZOR2UP2S", "razor clams"),
        ("TOOTHPASTE CHEWING GUM FLAVOUR", "chewing gum"),
        (None, "Laundry detergent"),
        (None, "Total"),
    ],
)
def test_existing_exclusions_and_strong_negative_priority(raw, name):
    assert classify_receipt_item(item(raw, name)).category is FoodCategory.NON_FOOD


def test_raw_scope_rules_do_not_classify_invented_abbreviation_names():
    assert classify_receipt_item(item("UNIDENTIFIED", "TT P-GUM HLTH")).category is (
        FoodCategory.UNCLASSIFIED
    )


def test_filter_preserves_input_and_logs_only_aggregate_static_rule_ids(caplog):
    food = item("COCONUT MILK 200ML", "coconut milk")
    draft = DraftResult(
        items=[
            item("FP L/LQ DTG-C.C 4.4L", "distilled water"),
            food,
            item("TT P-GUM HLTH 110G", "chewing gum"),
        ]
    )
    before = draft.model_dump()
    with caplog.at_level(logging.INFO, logger="app.food_filter"):
        result = filter_receipt_foods(draft)
    assert result.items == [food]
    assert draft.model_dump() == before
    message = json.loads(caplog.records[-1].message)
    assert message == {
        "event": "receipt_food_filter",
        "removed_items": 2,
        "rule_counts": {
            "retail_laundry_liquid_abbreviation": 1,
            "retail_oral_health_abbreviation": 1,
        },
    }
    assert "distilled water" not in caplog.text
    assert "P-GUM" not in caplog.text


def test_rules_are_loaded_at_import_not_for_each_item(monkeypatch):
    def unexpected_read(*args, **kwargs):
        pytest.fail("Category rules must not be read for every request/item")

    monkeypatch.setattr(Path, "read_text", unexpected_read)
    assert classify_receipt_item(item("TT P-GUM HLTH 110G")).category is FoodCategory.NON_FOOD


@pytest.mark.parametrize(
    "change,error",
    [
        (lambda data: data.update(schema_version=99), "Unsupported"),
        (lambda data: data["non_food_rules"].append(data["non_food_rules"][0]), "Duplicate"),
        (lambda data: data["non_food_rules"][0].update(scope="name"), "identity/scope"),
        (lambda data: data["non_food_rules"][0].update(all_of=[]), "nonempty"),
    ],
)
def test_invalid_static_rules_fail_clearly(tmp_path, change, error):
    data = json.loads(RULES_PATH.read_text())
    change(data)
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=error):
        _load_rules(path)


def test_normalization_is_separate_from_source_evidence():
    raw = "ＦＰ L/LQ DTG-C.C 4.4L\\nQTY:2"
    assert normalize_description(raw) == "fp l lq dtg c c 4 4 l qty 2"
    assert item(raw).raw_text == raw
