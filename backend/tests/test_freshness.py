"""The freshness rules, one case per row. No database needed."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.schemas.common import FreshnessStatus as F
from app.services.freshness import freshness_status, use_first_date

TODAY = date(2026, 11, 3)
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


def days(n: int) -> date:
    return TODAY + timedelta(days=n)


def status(**overrides):
    base = {
        "today": TODAY,
        "now": NOW,
        "remaining_state": "enough",
        "label_date": None,
        "label_date_kind": None,
        "use_first": None,
        "category": "produce",
        "freshness_confirmed_at": None,
    }
    return freshness_status(**{**base, **overrides})


def test_use_first_date_prefers_the_printed_label():
    assert use_first_date(days(4), days(-10), 28) == days(4)


def test_use_first_date_adds_the_shelf_life_to_the_purchase_date():
    assert use_first_date(None, days(-3), 7) == days(4)


def test_use_first_date_is_unknown_without_a_label_or_shelf_life():
    assert use_first_date(None, days(-3), None) is None


@pytest.mark.parametrize(
    ("use_first", "expected"),
    [
        (days(14), F.OK),
        (days(4), F.OK),
        (days(3), F.USE_SOON),  # the window's last day
        (days(1), F.USE_SOON),
        (days(0), F.USE_SOON),  # the date itself is not yet past
        (days(-1), F.CHECK),
        (days(-30), F.CHECK),
    ],
)
def test_an_estimated_date(use_first, expected):
    assert status(use_first=use_first) == expected


def test_saying_it_is_fine_makes_a_past_estimate_usable_for_24_hours():
    assert status(use_first=days(-1), freshness_confirmed_at=NOW - timedelta(hours=1)) == F.OK
    assert status(use_first=days(-1), freshness_confirmed_at=NOW - timedelta(hours=25)) == F.CHECK


def test_a_batch_past_its_use_by_date_is_expired_even_if_confirmed():
    args = {"label_date": days(-1), "label_date_kind": "use_by", "use_first": days(-1)}
    assert status(**args) == F.EXPIRED
    assert status(**args, freshness_confirmed_at=NOW) == F.EXPIRED


def test_the_use_by_date_itself_is_not_yet_expired():
    args = {"label_date": days(0), "label_date_kind": "use_by", "use_first": days(0)}
    assert status(**args) == F.USE_SOON


def test_past_a_best_before_date_is_checked_not_expired():
    args = {"label_date": days(-1), "label_date_kind": "best_before", "use_first": days(-1)}
    assert status(**args) == F.CHECK
    assert status(**args, freshness_confirmed_at=NOW) == F.OK


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("meat", F.CHECK),
        ("produce", F.CHECK),
        ("egg", F.CHECK),
        ("grain", F.OK),
        ("pantry", F.OK),
        (None, F.OK),  # a free-text item: nothing tells us it is perishable
    ],
)
def test_no_date_at_all(category, expected):
    assert status(category=category) == expected


def test_a_perishable_with_no_date_is_usable_once_confirmed():
    assert status(category="meat", freshness_confirmed_at=NOW - timedelta(hours=2)) == F.OK


def test_a_batch_that_is_out_has_nothing_to_judge():
    args = {"remaining_state": "out", "label_date": days(-5), "label_date_kind": "use_by"}
    assert status(**args, use_first=days(-5)) == F.OK
