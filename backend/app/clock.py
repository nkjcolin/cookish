"""What time and day it is for our users (docs/init.md, "Dates and times").

Always use these instead of date.today() or datetime.now(). Lambda runs in UTC, and from
midnight to 8 a.m. in Singapore the UTC date is still yesterday, which would put every
use-first date and freshness check a day out.
"""

from datetime import date, datetime, timedelta, timezone

# Singapore has no daylight saving time, so a fixed offset is exact and needs no tz data.
SINGAPORE = timezone(timedelta(hours=8), "Asia/Singapore")


def now() -> datetime:
    """The current moment, timezone-aware. Store it as is; Postgres keeps it in UTC."""
    return datetime.now(SINGAPORE)


def today() -> date:
    """Today's date in Singapore."""
    return now().date()
