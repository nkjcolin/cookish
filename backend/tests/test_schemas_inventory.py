from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.identity import PreferencesUpdate
from app.schemas.inventory import InventoryItemCreate, InventoryItemsCreate, InventoryItemUpdate


def test_create_needs_an_ingredient_or_a_name() -> None:
    with pytest.raises(ValidationError, match="ingredient_id or display_name"):
        InventoryItemCreate(count=3)

    assert InventoryItemCreate(display_name="Grandma's chilli paste").ingredient_id is None
    assert InventoryItemCreate(ingredient_id=uuid4(), count=3).count == 3


def test_label_date_needs_a_kind() -> None:
    with pytest.raises(ValidationError, match="label_date_kind"):
        InventoryItemCreate(display_name="Milk", label_date=date(2026, 10, 20))


def test_count_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        InventoryItemCreate(display_name="Eggs", count=-1)


def test_create_request_rejects_unknown_fields_and_empty_lists() -> None:
    with pytest.raises(ValidationError):
        InventoryItemsCreate(items=[])
    with pytest.raises(ValidationError):
        InventoryItemsCreate.model_validate({"items": [{"display_name": "Eggs", "qty": 3}]})


def test_update_distinguishes_absent_from_null() -> None:
    unchanged = InventoryItemUpdate.model_validate({"revision": 2, "remaining_state": "low"})
    cleared = InventoryItemUpdate.model_validate({"revision": 2, "count": None})

    assert "count" not in unchanged.model_fields_set
    assert "count" in cleared.model_fields_set and cleared.count is None


def test_preferences_reject_values_outside_the_vocabulary() -> None:
    assert PreferencesUpdate(allergens=["peanut"], diets=["halal"]).household_size == 2
    with pytest.raises(ValidationError):
        PreferencesUpdate(allergens=["gluten-free"])
