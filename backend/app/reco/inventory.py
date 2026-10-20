"""Portion scaling and stock classification using Role 2's freshness snapshot."""

import math
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from uuid import UUID

from app.reco.config import DEFAULT_CONFIG, ScoringConfig
from app.reco.models import Candidate, CatalogIngredient, IngredientAssessment
from app.schemas.common import FreshnessStatus, LabelDateKind, RemainingState
from app.schemas.cook import FreshnessCheck, FreshnessReason, IngredientStatus
from app.schemas.inventory import InventoryItem
from app.schemas.recipes import RecipeIngredient


def batch_order(item: InventoryItem):
    return (item.est_use_first_date or date.max, item.acquired_at, str(item.id))


def freshness_reason(item: InventoryItem) -> FreshnessReason:
    if item.freshness_status == FreshnessStatus.EXPIRED:
        return FreshnessReason.PAST_USE_BY
    if item.label_date is not None and item.label_date_kind == LabelDateKind.BEST_BEFORE:
        return FreshnessReason.PAST_BEST_BEFORE
    if item.est_use_first_date is not None:
        return FreshnessReason.PAST_ESTIMATE
    return FreshnessReason.NO_DATE


def display_amount(item: RecipeIngredient, factor: float, people: int, servings: int) -> str:
    if item.quantity is not None:
        return f"{item.quantity * factor:g} {item.unit}"
    if factor == 1:
        return item.coarse_amount or ""
    # Never pretend natural-language amounts were numerically converted.
    return f"{item.coarse_amount} (adjust for {people} people; original serves {servings})"


def assess_ingredients(
    recipe: Candidate,
    inventory: Sequence[InventoryItem],
    catalogue: Mapping[UUID, CatalogIngredient],
    people: int,
    *,
    as_of: datetime,
    config: ScoringConfig = DEFAULT_CONFIG,
) -> tuple[IngredientAssessment, ...]:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware; pass app.clock.now() from the service")
    if isinstance(people, bool) or not isinstance(people, int) or not 1 <= people <= 12:
        raise ValueError("people must be between 1 and 12")
    if len({item.id for item in inventory}) != len(inventory):
        raise ValueError("inventory snapshot contains duplicate batch IDs")
    factor = people / recipe.servings
    result = []
    for line in recipe.ingredients:
        meta = catalogue.get(line.ingredient_id)
        if meta is None or meta.id != line.ingredient_id:
            raise ValueError("ingredient metadata is missing or has a mismatched ID")
        batches = sorted(
            (item for item in inventory if item.ingredient_id == line.ingredient_id),
            key=batch_order,
        )
        need = line.quantity * factor if line.quantity is not None else None
        usable, uncertain, freshness = [], [], []
        known = 0.0
        enough = False
        low = False
        for item in batches:
            if item.remaining_state == RemainingState.OUT or (item.countable and item.count == 0):
                continue
            if item.freshness_status in {FreshnessStatus.EXPIRED, FreshnessStatus.CHECK}:
                freshness.append(FreshnessCheck(item=item, reason=freshness_reason(item)))
                continue
            confirmed = item.last_confirmed_at
            stale = meta.perishable and (
                confirmed.tzinfo is None
                or confirmed.utcoffset() is None
                or confirmed > as_of
                or as_of - confirmed > timedelta(days=config.stale_confirmation_days)
            )
            if stale or item.countable != meta.countable:
                uncertain.append(item)
                continue
            if meta.countable:
                if (
                    item.count is None
                    or not math.isfinite(item.count)
                    or item.count < 0
                    or need is None
                    or item.unit != line.unit
                ):
                    uncertain.append(item)
                    continue
                known += item.count
                usable.append(item)
            elif item.remaining_state == RemainingState.UNKNOWN:
                uncertain.append(item)
            else:
                enough |= item.remaining_state == RemainingState.ENOUGH
                low |= item.remaining_state == RemainingState.LOW
                usable.append(item)
        if meta.countable:
            enough = need is not None and known >= need
            low = known > 0 and not enough
        # An explicit tracked absence/uncertainty overrides the staple assumption.
        if meta.is_staple and not batches:
            status = IngredientStatus.STAPLE
        elif enough:
            status = IngredientStatus.STAPLE if meta.is_staple else IngredientStatus.HAVE
        elif any(check.item.freshness_status == FreshnessStatus.CHECK for check in freshness):
            status = IngredientStatus.CHECK
        elif uncertain:
            status = IngredientStatus.UNKNOWN
        elif low:
            status = IngredientStatus.LOW
        else:
            status = IngredientStatus.MISSING
        result.append(
            IngredientAssessment(
                ingredient_id=line.ingredient_id,
                name=meta.canonical_name,
                essential=line.essential,
                quantity=need,
                unit=line.unit,
                amount=display_amount(line, factor, people, recipe.servings),
                status=status,
                is_staple=meta.is_staple,
                known_quantity=known if meta.countable else None,
                usable_batches=tuple(usable),
                needs_check=(
                    tuple(uncertain[:1])
                    if line.essential and status == IngredientStatus.UNKNOWN
                    else ()
                ),
                freshness_check=tuple(freshness),
            )
        )
    return tuple(result)
