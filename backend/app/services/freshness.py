"""When a batch should be used by, and whether it can still be counted as stock.

Role 2 owns this file. These are plain functions: no database and no clock. The caller passes
today's date and the current time (app.clock), so every rule is easy to test.

The rules (SPEC B5 and app/db/README.md):
- The use-first date is the printed label date if there is one. Otherwise it is the purchase
  date plus the ingredient's shelf life for where the batch is stored. It is our estimate, never
  a safety claim.
- expired: past a use-by date. Not counted as stock, and "It's fine" does not rescue it.
- check: past a best-before date or past our estimate, or a perishable with no date at all, and
  not confirmed in the last 24 hours. Cook asks the user before counting it as stock.
- use_soon: the date is today or within USE_SOON_DAYS days.
- ok: everything else, and any batch that is out of stock (there is nothing left to judge).
"""

from datetime import date, datetime, timedelta

from app.schemas.common import FreshnessStatus, LabelDateKind, RemainingState

# Role 5 turns the use-first date into scoring urgency with its own window (SPEC B5, 3 to 5
# days). This one only decides when the Kitchen screen says "use soon".
USE_SOON_DAYS = 3

# "It's fine" makes a batch usable for this long (SPEC B5, freshness gate).
CONFIRMATION_LASTS = timedelta(hours=24)

# Food that goes off quickly. A batch of these with no date at all is checked, not trusted.
PERISHABLE_CATEGORIES = frozenset({"produce", "meat", "seafood", "dairy", "egg"})


def use_first_date(
    label_date: date | None, acquired_at: date, shelf_life_days: int | None
) -> date | None:
    """The date to use a batch by, or None when nothing tells us (no label, no shelf life)."""
    if label_date is not None:
        return label_date
    if shelf_life_days is None:
        return None
    return acquired_at + timedelta(days=shelf_life_days)


def freshness_status(
    *,
    today: date,
    now: datetime,
    remaining_state: str,
    label_date: date | None,
    label_date_kind: str | None,
    use_first: date | None,
    category: str | None,
    freshness_confirmed_at: datetime | None,
) -> FreshnessStatus:
    """The freshness gate for one batch. `category` is None for a free-text item."""
    if remaining_state == RemainingState.OUT:
        return FreshnessStatus.OK

    if label_date is not None and label_date_kind == LabelDateKind.USE_BY and today > label_date:
        return FreshnessStatus.EXPIRED

    confirmed = (
        freshness_confirmed_at is not None and now - freshness_confirmed_at <= CONFIRMATION_LASTS
    )

    if use_first is None:
        needs_check = category in PERISHABLE_CATEGORIES and not confirmed
        return FreshnessStatus.CHECK if needs_check else FreshnessStatus.OK

    if today > use_first:
        return FreshnessStatus.OK if confirmed else FreshnessStatus.CHECK
    if (use_first - today).days <= USE_SOON_DAYS:
        return FreshnessStatus.USE_SOON
    return FreshnessStatus.OK
