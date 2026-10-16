from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.cook import ConsumptionLine, CookAdjust
from app.schemas.shop import BasketConfirm, ShopAdjust


def test_adjust_must_change_something() -> None:
    with pytest.raises(ValidationError, match="at least one field"):
        CookAdjust()
    with pytest.raises(ValidationError, match="at least one field"):
        ShopAdjust()

    assert CookAdjust(tags=["quicker"]).people is None
    assert CookAdjust(people=4).tags == []


def test_adjust_rejects_tags_from_the_other_mode() -> None:
    with pytest.raises(ValidationError):
        CookAdjust(tags=["longer_lasting"])
    with pytest.raises(ValidationError):
        ShopAdjust(tags=["quicker"])


def test_consumption_line_takes_a_count_or_an_outcome_not_both() -> None:
    item = uuid4()

    assert ConsumptionLine(inventory_item_id=item, revision=1, new_count=0).new_count == 0
    assert ConsumptionLine(inventory_item_id=item, revision=1, outcome="used_up").outcome
    with pytest.raises(ValidationError, match="exactly one"):
        ConsumptionLine(inventory_item_id=item, revision=1)
    with pytest.raises(ValidationError, match="exactly one"):
        ConsumptionLine(inventory_item_id=item, revision=1, new_count=2, outcome="used_up")


def test_basket_confirm_needs_at_least_one_line() -> None:
    with pytest.raises(ValidationError):
        BasketConfirm(lines=[])
