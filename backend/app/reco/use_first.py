"""Order confirmed stock from an existing freshness snapshot; never compute shelf life."""

import math
from collections.abc import Collection, Sequence
from datetime import datetime, timedelta

from app.clock import SINGAPORE
from app.reco.config import DEFAULT_CONFIG, ScoringConfig
from app.reco.inventory import batch_order
from app.schemas.common import FreshnessStatus, RemainingState
from app.schemas.cook import UseFirstItem, UseFirstList
from app.schemas.inventory import InventoryItem


def use_first_items(
    inventory: Sequence[InventoryItem],
    *,
    as_of: datetime,
    perishable_categories: Collection[str],
    config: ScoringConfig = DEFAULT_CONFIG,
) -> UseFirstList:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if len({item.id for item in inventory}) != len(inventory):
        raise ValueError("inventory snapshot contains duplicate batch IDs")
    today = as_of.astimezone(SINGAPORE).date()
    selected = []
    for item in inventory:
        if (
            item.freshness_status != FreshnessStatus.USE_SOON
            or item.est_use_first_date is None
            or item.est_use_first_date < today
            or item.remaining_state not in {RemainingState.ENOUGH, RemainingState.LOW}
        ):
            continue
        confirmed = item.last_confirmed_at
        if (
            confirmed.tzinfo is None
            or confirmed.utcoffset() is None
            or confirmed > as_of
            or (
                item.category in perishable_categories
                and as_of - confirmed > timedelta(days=config.stale_confirmation_days)
            )
        ):
            continue
        if item.countable and (
            item.count is None or not math.isfinite(item.count) or item.count <= 0 or not item.unit
        ):
            continue
        selected.append(item)
    return UseFirstList(
        items=[
            UseFirstItem(item=item, days_left=(item.est_use_first_date - today).days)
            for item in sorted(selected, key=batch_order)
        ]
    )
