import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app
from app.model_client import SchoolModelClient, get_client
from app.photos import PhotoExtractionResult, resolve_photo_instances


def instance(position, amount=None, unit=None, basis="label", label_text="NET contents"):
    return dict(position=position, amount=amount, unit=unit, basis=basis, label_text=label_text)


def food(instances, name="Food", confidence=0.9):
    return dict(display_name=name, storage="pantry", confidence=confidence, instances=instances)


def resolve(*foods):
    source = PhotoExtractionResult.model_validate({"items": list(foods)})
    before = source.model_dump()
    result = resolve_photo_instances(source)
    assert source.model_dump() == before
    for item in result.model_dump()["items"]:
        assert set(item) == {"raw_text", "display_name", "count", "unit", "storage", "confidence"}
        assert item["raw_text"] is None
    return [(i.display_name, i.count, i.unit) for i in result.items]


@pytest.mark.parametrize(
    "amounts,unit,expected",
    [([250, 250], "g", 500), ([300, 750], "ml", 1050), ([0.5, 1.5], "kg", 2)],
)
def test_sum_each_package_once_and_keep_original_scale(amounts, unit, expected):
    result = resolve(food([instance(str(i), n, unit) for i, n in enumerate(amounts)]))
    assert result == [("Food", expected, unit)]


def test_count_individual_loose_objects_without_a_model_total():
    rows = [
        instance(p, 1, "pcs", "object", None)
        for p in ["front left", "front right", "rear left", "rear right"]
    ]
    assert resolve(food(rows, "Egg")) == [("Egg", 4, "pcs")]


def test_readable_carton_total_is_one_observation_not_inner_objects():
    assert resolve(food([instance("carton", 10, "pcs", label_text="10 EGGS")], "Egg")) == [
        ("Egg", 10, "pcs")
    ]


def test_inner_blocks_are_not_additional_package_factors():
    result = resolve(
        food(
            [
                instance("left tray", 450, "g", label_text="NET 450 g"),
                instance("right tray", 450, "g", label_text="NET 450 g"),
            ],
            "Tofu",
        )
    )
    assert result == [("Tofu", 900, "g")]


def test_mixed_scales_and_product_variants_are_not_silently_rescaled_or_merged():
    assert resolve(
        food(
            [
                instance("large carton", 1, "L"),
                instance("small carton", 500, "ml"),
            ],
            "Milk",
        )
    ) == [("Milk", 1, "l"), ("Milk", 500, "ml")]
    assert resolve(
        food([instance("left", 1, "l")], "Whole milk"),
        food([instance("right", 500, "ml")], "Low-fat milk"),
    ) == [("Whole milk", 1, "l"), ("Low-fat milk", 500, "ml")]


def test_repeated_food_groups_merge_only_matching_names():
    assert resolve(
        food([instance("left", 200, "grams")], "Food", 0.9),
        food([instance("right", 300, "g")], "FOOD", 0.8),
    ) == [("Food", 500, "g")]


def test_unreadable_contents_allow_counted_purchase_units():
    assert resolve(
        food(
            [
                instance("left", 1, "cans", "purchase_unit", None),
                instance("right", 1, "can", "purchase_unit", None),
            ]
        )
    ) == [("Food", 2, "can")]


@pytest.mark.parametrize("unknown_unit", [None, "g"])
def test_partly_unknown_group_does_not_return_misleading_partial_mass(unknown_unit):
    assert resolve(
        food(
            [
                instance("front", 250, "g"),
                instance("back", None, unknown_unit, "unknown", None),
            ]
        )
    ) == [("Food", None, "g")]


def test_known_mass_and_unknown_package_contents_require_review():
    assert resolve(
        food(
            [
                instance("front", 250, "g"),
                instance("back", 1, "pack", "purchase_unit", None),
            ]
        )
    ) == [("Food", None, "g")]


def test_duplicate_locations_are_uncertain_not_summed_or_silently_discarded():
    assert resolve(
        food(
            [
                instance("Front left", 250, "g"),
                instance(" front  LEFT ", 250, "g"),
            ]
        )
    ) == [("Food", None, "g")]


def test_all_unknown_stays_unknown_without_receipt_defaults():
    assert resolve(food([instance("partly hidden", None, None, "unknown", None)])) == [
        ("Food", None, None)
    ]


def test_overflowing_sum_remains_json_safe():
    assert resolve(
        food(
            [
                instance("left", 1e308, "g"),
                instance("right", 1e308, "g"),
            ]
        )
    ) == [("Food", None, "g")]


@pytest.mark.parametrize(
    "change",
    [
        {"amount": 0},
        {"amount": -1},
        {"amount": float("inf")},
        {"amount": float("nan")},
        {"amount": None},
        {"label_text": None},
        {"basis": "object", "amount": 4, "unit": "pcs", "label_text": None},
        {"basis": "object", "amount": 1, "unit": "g", "label_text": None},
        {"basis": "purchase_unit", "amount": 1, "unit": "g", "label_text": None},
        {"basis": "unknown", "amount": 1},
    ],
)
def test_uncertain_quantity_keeps_food_with_unknown_count(change):
    value = instance("front", 250, "g") | change
    result = PhotoExtractionResult.model_validate({"items": [food([value])]})
    assert result.items[0].instances[0].basis == "unknown"
    assert resolve_photo_instances(result).items[0].count is None


@pytest.mark.parametrize(
    "change",
    [
        {"position": " "},
        {"position": []},
        {"basis": "invented"},
        {"basis": []},
        {"unit": []},
        {"label_text": []},
        {"amount": "several"},
    ],
)
def test_invalid_instance_shape_still_requires_repair(change):
    value = instance("front", 250, "g") | change
    with pytest.raises(ValidationError):
        PhotoExtractionResult.model_validate({"items": [food([value])]})


@pytest.mark.parametrize(
    "basis,unit,expected",
    [
        ("purchase_unit", "loaf", "loaf"),
        ("purchase_unit", "net bag", "bag"),
        ("object", "bunch", "bunch"),
        ("object", "head", "pcs"),
        ("label", "pack", "pack"),
    ],
)
def test_purchase_and_whole_object_units_are_usable(basis, unit, expected):
    assert resolve(food([instance("front", 1, unit, basis, None)])) == [("Food", 1, expected)]


@pytest.mark.parametrize("sentinel", [0, -1, float("nan"), float("inf"), True])
def test_unknown_quantity_sentinels_do_not_drop_food(sentinel):
    assert resolve(food([instance("front", sentinel, "g", "unknown", None)])) == [
        ("Food", None, "g")
    ]


@pytest.mark.parametrize(
    "amount,unit,label,expected_count,expected_unit",
    [
        (1000, "g", "NET WT 1 kg", 1, "kg"),
        (0.45, "kg", "450G", 450, "g"),
        (1000, "ml", "1 L", 1, "l"),
        (700, "g", "700g", 700, "g"),
    ],
)
def test_photo_labels_restore_original_printed_scale(
    amount, unit, label, expected_count, expected_unit
):
    assert resolve(food([instance("front", amount, unit, label_text=label)])) == [
        ("Food", expected_count, expected_unit)
    ]


def test_empty_list_and_missing_instance_evidence_are_different():
    assert resolve_photo_instances(PhotoExtractionResult(items=[])).items == []
    with pytest.raises(ValidationError):
        PhotoExtractionResult.model_validate({"items": [food([])]})


@pytest.mark.parametrize("field", ["position", "basis", "amount", "unit", "label_text"])
def test_missing_private_fields_still_require_repair(field):
    value = instance("front", 250, "g")
    del value[field]
    with pytest.raises(ValidationError):
        PhotoExtractionResult.model_validate({"items": [food([value])]})


@pytest.mark.parametrize("settings_override", [{}, {"photo_quantity_mode": "instances"}])
def test_instances_route_uses_private_schema_and_preserves_other_routes(
    image_payload, settings_override
):
    requests = []
    answer = {
        "items": [
            food(
                [
                    instance("left", 250, "g"),
                    instance("right", 250, "g"),
                ]
            )
        ]
    }

    def respond(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})
        payload = json.loads(request.content)
        requests.append(payload)
        if payload["response_format"]["json_schema"]["name"] == "PhotoExtractionResult":
            result = answer
        else:
            result = {
                "items": [
                    {
                        "raw_text": "FOOD",
                        "display_name": "Food",
                        "count": 2,
                        "unit": "pack",
                        "storage": None,
                        "confidence": 0.8,
                    }
                ]
            }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result)}}]})

    model = SchoolModelClient(
        Settings(
            base_url="https://school.example/v1/",
            model="vision",
            api_key="test-key",
            **settings_override,
        ),
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    app = create_app()
    app.dependency_overrides[get_client] = lambda: model
    try:
        with TestClient(app) as client:
            photo = client.post("/ai/parse-image", json={**image_payload, "kind": "photo"})
            assert photo.status_code == 200
            assert photo.json()["items"][0]["count"] == 500
            assert photo.json()["items"][0]["raw_text"] is None
            assert "instances" not in photo.json()["items"][0]
            assert requests[0]["response_format"]["json_schema"]["name"] == "PhotoExtractionResult"
            assert "physical packages" in requests[0]["messages"][0]["content"]
            schema = requests[0]["response_format"]["json_schema"]["schema"]
            assert schema["$defs"]["PhotoInstance"]["additionalProperties"] is False
            assert set(schema["$defs"]["PhotoInstance"]["required"]) == {
                "position",
                "basis",
                "label_text",
                "amount",
                "unit",
            }
            receipt = client.post("/ai/parse-image", json=image_payload)
            assert receipt.status_code == 200
            assert receipt.json()["items"][0]["count"] == 2
            assert requests[-1]["response_format"]["json_schema"]["name"] == "ExtractionResult"
            text = client.post("/ai/parse-items", json={"text": "food"})
            assert text.status_code == 200
            assert requests[-1]["response_format"]["json_schema"]["name"] == "ExtractionResult"
            rejected = client.post(
                "/ai/parse-image",
                json={
                    **image_payload,
                    "kind": "photo",
                    "photo_quantity_mode": "factors",
                },
            )
            assert rejected.status_code == 422
    finally:
        app.dependency_overrides.clear()
        model.close()
