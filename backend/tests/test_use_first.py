"""Role 5 use-first decisions over an explicit freshness snapshot."""

from datetime import UTC, datetime, timedelta

import pytest

from app.reco.use_first import use_first_items
from app.schemas.common import FreshnessStatus, IngredientCategory, RemainingState
from tests.reco_fixtures import NOW, batch


def soon(key="one", **changes):
    return batch(
        key=key,
        **{
            "category": IngredientCategory.EGG,
            "freshness_status": FreshnessStatus.USE_SOON,
            **changes,
        },
    )


def choose(items, as_of=NOW):
    return use_first_items(items, as_of=as_of, perishable_categories={"egg"})


def test_empty_kitchen_returns_empty_list():
    assert choose([]).items == []


@pytest.mark.parametrize(
    "changes",
    [
        {"freshness_status": FreshnessStatus.EXPIRED},
        {"freshness_status": FreshnessStatus.CHECK},
        {"freshness_status": FreshnessStatus.OK},
        {"est_use_first_date": None},
        {"est_use_first_date": NOW.date() - timedelta(days=1)},
        {"remaining_state": RemainingState.OUT},
        {"remaining_state": RemainingState.UNKNOWN},
        {"count": 0},
        {"count": None},
        {"count": float("nan")},
        {"count": -1},
        {"unit": None},
        {"last_confirmed_at": NOW - timedelta(days=14, microseconds=1)},
        {"last_confirmed_at": NOW + timedelta(seconds=1)},
        {"last_confirmed_at": NOW.replace(tzinfo=None)},
    ],
)
def test_unusable_or_uncertain_stock_is_not_promoted(changes):
    assert not choose([soon(**changes)]).items


def test_batches_sort_by_date_then_acquisition_then_id_without_merging_or_mutation():
    items = [
        soon("later"),
        soon("today", est_use_first_date=NOW.date()),
        soon("same", acquired_at=NOW.date() - timedelta(days=2)),
    ]
    original = [item.model_dump() for item in items]
    result = choose(items)
    assert [row.item.id for row in result.items] == [items[1].id, items[2].id, items[0].id]
    assert [row.days_left for row in result.items] == [0, 2, 2]
    assert choose(list(reversed(items))) == result
    assert [item.model_dump() for item in items] == original
    tied = [soon("a"), soon("b")]
    assert [row.item.id for row in choose(tied).items] == sorted(
        [item.id for item in tied], key=str
    )


def test_positive_low_count_and_state_tracked_low_can_be_used_without_claiming_full_portions():
    counted = soon(count=1, remaining_state=RemainingState.LOW)
    state = soon(
        "state", countable=False, count=None, unit=None, remaining_state=RemainingState.LOW
    )
    result = choose([counted, state])
    assert len(result.items) == 2
    assert next(row.item for row in result.items if row.item.id == state.id).count is None


def test_confirmation_boundary_and_nonperishable_policy_match_cook_availability():
    assert choose([soon(last_confirmed_at=NOW - timedelta(days=14))]).items
    assert choose(
        [soon(category=IngredientCategory.PANTRY, last_confirmed_at=NOW - timedelta(days=30))]
    ).items


def test_days_left_uses_singapore_date_across_utc_midnight():
    instant = datetime(2026, 10, 19, 16, 1, tzinfo=UTC)  # 20 Oct in Singapore
    item = soon(est_use_first_date=NOW.date(), last_confirmed_at=instant)
    assert choose([item], as_of=instant).items[0].days_left == 0


def test_invalid_time_and_duplicate_batch_snapshot_are_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        choose([], as_of=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="duplicate batch"):
        choose([soon(), soon()])
