"""The demo kitchen must agree with the catalogue. No database needed."""

from datetime import UTC, date, datetime

from app.schemas.common import RemainingState, Storage
from seed.demo import ITEMS, build_items
from seed.seed import INGREDIENTS_CSV, SHELF_LIFE_BY_STORAGE, read_ingredients

TODAY = date(2026, 11, 3)
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def _catalogue():
    rows, problems = read_ingredients(INGREDIENTS_CSV)
    assert problems == []
    return {row["canonical_name"]: row for row in rows}


def _built():
    return build_items(_catalogue(), TODAY, NOW)


def test_every_demo_item_uses_a_catalogue_ingredient():
    assert {item.ingredient for item in ITEMS} <= _catalogue().keys()


def test_ids_are_unique_and_stable():
    first, second = _built(), _built()
    assert [r["id"] for r in first] == [r["id"] for r in second]
    assert len({r["id"] for r in first}) == len(first)


def test_counts_only_on_counted_ingredients_and_always_with_a_unit():
    by_id = {row["id"]: row for row in _catalogue().values()}
    for row in _built():
        ingredient = by_id[row["ingredient_id"]]
        if row["count"] is not None:
            assert ingredient["countable"] and row["unit"]
        else:
            assert row["unit"] is None


def test_values_are_allowed_ones():
    for row in _built():
        assert row["remaining_state"] in {s.value for s in RemainingState}
        assert row["storage"] in {s.value for s in Storage}
        assert row["acquired_at"] <= TODAY
        assert (row["label_date"] is None) == (row["label_date_kind"] is None)


def test_the_kitchen_reproduces_the_mock_situations():
    rows = {r["display_name"] + str(i): r for i, r in enumerate(_built())}
    catalogue = _catalogue()
    chicken = next(r for r in _built() if r["display_name"] == "Chicken thigh")
    shelf = catalogue["chicken thigh"][SHELF_LIFE_BY_STORAGE[chicken["storage"]]]
    assert (TODAY - chicken["acquired_at"]).days > shelf  # past its estimated date
    tofu = next(r for r in _built() if r["display_name"] == "Firm tofu")
    assert tofu["label_date"] > TODAY and tofu["label_date_kind"] == "use_by"
    rice = next(r for r in _built() if r["display_name"] == "Rice")
    assert rice["remaining_state"] == "unknown"
    assert len(rows) == 8
