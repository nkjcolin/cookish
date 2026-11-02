import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.model_client import SchoolModelClient, get_client
from app.receipts import clean_receipt, default_receipt_units
from app.schemas import DraftItem, DraftResult


def draft_item(raw, name, count=None, unit=None):
    return DraftItem(
        raw_text=raw,
        display_name=name,
        count=count,
        unit=unit,
        storage=None,
        confidence=0.9,
    )


def test_clear_non_food_and_invented_food_names_are_removed() -> None:
    result = clean_receipt(
        DraftResult(
            items=[
                draft_item("IT P-GUM HLTH 110G", "Toothpaste", 2, "pack"),
                draft_item("G LB601 RAZOR2UP2S", "Razor clams", 1, "pack"),
                draft_item("FP ALKALINE AAA 8/PS", "Batteries"),
                draft_item("I 21839 HANGER", "Hanger"),
                draft_item("I 39058 TABLE WARE", "Tableware"),
                draft_item("TOTAL 12.50", "Total"),
                draft_item("MILK 946ML", "Milk"),
            ]
        )
    )
    assert [item.display_name for item in result.items] == ["Milk"]


def test_food_names_are_not_rejected_for_shared_words() -> None:
    result = clean_receipt(
        DraftResult(
            items=[
                draft_item("FRESH RAZOR CLAMS", "Razor clams"),
                draft_item("BAG OF RICE", "Rice"),
                draft_item("ALKALINE WATER 1L", "Water"),
                draft_item("BATTERED FISH", "Fish"),
                draft_item("CABBAGE", "Cabbage"),
            ]
        )
    )
    assert len(result.items) == 5


@pytest.mark.parametrize(
    "raw,count,unit",
    [
        ("FOOD\n2X$3.70/Unit", 2, "pack"),
        ("FOOD\n2X3.95", 2, "pack"),
        ("FOOD Qty: 2", 2, "pcs"),
        ("FOOD QUANTITY 3", 3, None),
        ("FOOD\n2 @ $1.50", 2, "pack"),
        ("3 FOOD", 3, "pcs"),
        ("FOOD 3", 3, "pcs"),
        ("3\nFOOD", 3, "pack"),
        ("FOOD\n3", 3, None),
        ("FOOD 4 2.50", 4, "pack"),
        ("FOOD\n0.35 KG @ $8.00/KG", 0.35, "kg"),
    ],
)
def test_model_counts_and_units_survive_all_receipt_layouts(raw, count, unit) -> None:
    result = clean_receipt(DraftResult(items=[draft_item(raw, "Food", count, unit)]))
    assert result.items[0].count == count
    assert result.items[0].unit == (unit or "pcs")
    assert result.items[0].raw_text == raw


@pytest.mark.parametrize("count", [None, 1])
@pytest.mark.parametrize(
    "raw,unit,expected_count",
    [("FOOD", None, 1), ("FOOD 500G", "g", 500), ("FOOD 1L", "l", 1), ("FOOD 10S", "pcs", 10)],
)
def test_printed_contents_override_missing_or_incorrect_model_counts(
    raw, unit, expected_count, count
) -> None:
    original = draft_item(raw, "Food", count, unit)
    result = clean_receipt(DraftResult(items=[original]))
    assert result.items[0].count == expected_count
    assert result.items[0].unit == (unit or "pcs")
    assert result.items[0].raw_text == raw
    assert original.count == count


@pytest.mark.parametrize("count", [None, 3])
def test_null_receipt_unit_defaults_to_pcs(count) -> None:
    result = clean_receipt(DraftResult(items=[draft_item("FOOD", "Food", count, None)]))
    assert result.items[0].count == (1 if count is None else count)
    assert result.items[0].unit == "pcs"


@pytest.mark.parametrize("count", [None, 1, 2])
@pytest.mark.parametrize("unit", ["g", "kg", "ml", "l", "pack", "bottle", "oz"])
def test_without_printed_contents_unknown_measured_amount_stays_null(count, unit):
    original = DraftResult(items=[draft_item("FOOD\n2X$1.50/Unit", "Food", count, unit)])
    result = clean_receipt(original)
    assert result.items[0].unit == unit
    if count is None:
        expected_count = 1 if unit in {"pack", "bottle"} else None
    else:
        expected_count = count
    assert result.items[0].count == expected_count
    assert original.items[0].count == count and original.items[0].unit == unit


@pytest.mark.parametrize("unit", ["", "   ", "\t"])
def test_blank_receipt_unit_is_normalized_to_null_before_final_fallback(unit):
    original = DraftResult(items=[draft_item("FOOD", "Food", 2, unit)])
    assert default_receipt_units(original).items[0].unit == unit
    assert clean_receipt(original).items[0].unit == "pcs"


def test_unit_fallback_does_not_apply_other_receipt_cleanup():
    original = DraftResult(items=[draft_item("FOOD", "Food", None, None)])
    result = default_receipt_units(original)
    assert result.items[0].unit == "pcs"
    assert result.items[0].count is None
    assert original.items[0].unit is None


@pytest.mark.parametrize("count", [0, -1, float("inf"), float("-inf"), float("nan")])
def test_invalid_numeric_counts_do_not_pass_through(count) -> None:
    result = clean_receipt(DraftResult(items=[draft_item("FOOD", "Food", count, "kg")]))
    assert result.items[0].count is None
    assert result.items[0].unit == "kg"


@pytest.mark.parametrize("unit", [None, "pcs", "pack"])
@pytest.mark.parametrize("count", [0, -1, float("nan"), float("inf")])
def test_invalid_counts_do_not_become_one_purchase_unit(count, unit):
    result = clean_receipt(DraftResult(items=[draft_item("FOOD", "Food", count, unit)]))
    assert result.items[0].count is None


@pytest.mark.parametrize("photo_mode", ["instances", "factors"])
def test_receipt_checks_apply_to_real_provider_route_only_for_receipts(
    image_payload, photo_mode
) -> None:
    answer = DraftResult(
        items=[
            draft_item("TOOTHPASTE", "Toothpaste", 1, "pack"),
            draft_item("MILK 1L", "Milk", 1, "carton"),
            draft_item("TOFU\n2X$1.50/Unit", "Tofu", 2, "pack"),
            draft_item("FOOD 250ML", "Food", None, "ml"),
            draft_item("3 APPLES", "Apple", 3, "pcs"),
            draft_item("PEARS\n4", "Pear", 4, None),
            draft_item("FP L/LQ DTG-C.C 4.4L", "Coconut milk", None, None),
            draft_item("TT P-GUM HLTH 110G", "Chewing gum", None, None),
        ]
    )

    def respond(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})
        payload = json.loads(request.content)
        content = answer.model_dump_json()
        if payload["response_format"]["json_schema"]["name"] == "PhotoExtractionResult":
            # Photo evidence can be unknown; receipt text must not fill it in.
            content = json.dumps(
                {
                    "items": [
                        {
                            "display_name": item.display_name,
                            "storage": item.storage,
                            "confidence": item.confidence,
                            "instances": [
                                {
                                    "position": "front",
                                    "basis": "unknown",
                                    "amount": None,
                                    "unit": item.unit,
                                    "label_text": None,
                                }
                            ],
                        }
                        for item in answer.items
                    ]
                }
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
            },
        )

    model = SchoolModelClient(
        Settings(
            base_url="https://school.example/v1/",
            model="vision",
            api_key="test-key",
            photo_quantity_mode=photo_mode,
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    app.dependency_overrides[get_client] = lambda: model
    try:
        receipt = TestClient(app).post("/ai/parse-image", json=image_payload)
        assert receipt.status_code == 200
        assert [
            (item["display_name"], item["count"], item["unit"]) for item in receipt.json()["items"]
        ] == [
            ("Milk", 1, "l"),
            ("Tofu", 2, "pack"),
            ("Food", 250, "ml"),
            ("Apple", 3, "pcs"),
            ("Pear", 4, "pcs"),
        ]
        text = TestClient(app).post("/ai/parse-items", json={"text": "milk"})
        # Receipt-only defaults and filtering must not affect text or photo routes.
        assert json.loads(text.content)["items"][1]["count"] == 1
        assert json.loads(text.content)["items"][3]["count"] is None
        assert text.json()["items"][-1]["unit"] is None
        assert len(text.json()["items"]) == 8
        photo = TestClient(app).post("/ai/parse-image", json={**image_payload, "kind": "photo"})
        assert photo.status_code == 200
        assert photo.json()["items"][3]["count"] is None
        assert photo.json()["items"][-1]["unit"] is None
        assert len(photo.json()["items"]) == 8
    finally:
        app.dependency_overrides.clear()
        model.close()
