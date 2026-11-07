"""Stock events. Role 2 owns this file.

Every inventory change is one stock event, written by `apply_stock_event` in one transaction:
the event, a before and after snapshot per line, the item updates and a revision bump.

`apply_stock_event` and `get_inventory_snapshot` are the internal API that Role 5's
Cook and Shop services call. Their signatures and rules are agreed in app/db/README.md;
change them only by agreement.

How the rules are met:
- Idempotency: a repeated key returns the original change. The unique constraint on
  (household_id, idempotency_key) decides a race between two requests, not a check-then-insert.
  Reusing a key for a different operation raises CONFLICT.
- Stale edits: the items are locked with SELECT ... FOR UPDATE, then each line's revision is
  compared, so two edits of one item cannot both win.
- Undo: restores each line's `before` snapshot. A line whose item changed since the event is
  reported as a conflict and left alone.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import clock
from app.auth import CurrentUser
from app.db import models as m
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.schemas.common import ItemSource, LabelDateKind, RemainingState, Storage
from app.schemas.inventory import InventoryItem, InventoryItemCreate
from app.schemas.stock_events import (
    InventoryChange,
    ItemSnapshot,
    StockEvent,
    StockEventLine,
    StockEventList,
    StockEventType,
    StockRefType,
    UndoConflict,
    UndoResult,
)
from app.services.freshness import freshness_status, use_first_date

# The only fields a ChangeBatch may set.
CHANGEABLE_FIELDS = frozenset(
    {
        "count",
        "unit",
        "remaining_state",
        "storage",
        "label_date",
        "label_date_kind",
        "display_name",
        "freshness_confirmed_at",
    }
)


@dataclass(frozen=True)
class NewBatch:
    """Add a new batch: a purchase, or an item added by hand."""

    item: InventoryItemCreate
    source: ItemSource
    # A name match identifies food, not the meaning of a quantity with no unit.
    # Explicit catalogue selections retain the existing default-unit behavior.
    use_default_unit: bool = True


@dataclass(frozen=True)
class ChangeBatch:
    """Change or remove an existing batch."""

    item_id: UUID
    # The revision the user last saw; a mismatch raises STALE_REVISION. None when the
    # change comes from the system rather than from a user's edit.
    revision: int | None
    changes: dict[str, Any]  # keys from CHANGEABLE_FIELDS only; None means "unknown"
    remove: bool = False


StockLine = NewBatch | ChangeBatch


def list_events(user: CurrentUser, limit: int) -> StockEventList:
    """The household's most recent stock events, newest first (for the Activity screen)."""
    with transaction() as s:
        events = s.scalars(
            select(m.StockEvent)
            .where(m.StockEvent.household_id == user.household_id)
            .order_by(m.StockEvent.created_at.desc(), m.StockEvent.id.desc())
            .limit(limit)
        ).all()
        lines = _lines_by_event(s, [event.id for event in events])
        return StockEventList(events=[_event_view(e, lines.get(e.id, [])) for e in events])


def undo_event(user: CurrentUser, event_id: UUID, idempotency_key: UUID) -> UndoResult:
    """Restore each line's `before` snapshot; report lines changed since as conflicts."""
    with transaction() as s:
        return _undo(s, user, event_id, idempotency_key)


def apply_stock_event(
    s: Session,
    user: CurrentUser,
    event_type: StockEventType,
    lines: list[StockLine],
    idempotency_key: UUID,
    ref_type: StockRefType = StockRefType.MANUAL,
    ref_id: UUID | None = None,
) -> InventoryChange:
    """Apply one inventory change as one stock event, inside the caller's transaction.

    Writes the event, a before and after snapshot per line, updates the items and bumps
    their revision. A repeated `idempotency_key` returns the original change and changes
    nothing. Every item must belong to `user.household_id`, or NOT_FOUND is raised.

    An empty `lines` list is allowed: it records an event that changed nothing (a cook where
    nothing was used), so the key still protects a retry. Reusing a key for a different
    operation raises CONFLICT. A line with a `revision` that is no longer current raises
    STALE_REVISION before anything is written.
    """
    if event_type == StockEventType.UNDO:
        raise ApiError(ErrorCode.VALIDATION, "Use undo_event to undo an event")
    changes = [line for line in lines if isinstance(line, ChangeBatch)]
    ids = [line.item_id for line in changes]
    if len(set(ids)) != len(ids):
        raise ApiError(ErrorCode.VALIDATION, "An item can appear only once in one event")
    for line in changes:
        _check_changes(line.changes)

    def same_operation(event: m.StockEvent) -> bool:
        return _replays(s, event, event_type, ref_type, ref_id, lines)

    # 1. A retry of something already done: return it, change nothing.
    done = _find_event(s, user.household_id, idempotency_key)
    if done is not None:
        return _replay(s, done, same_operation)

    # 2. Lock the items. A request waiting here may find, once it gets the lock, that the
    #    same key was just completed by another request, so look again.
    locked = _lock_items(s, user.household_id, ids)
    done = _find_event(s, user.household_id, idempotency_key)
    if done is not None:
        return _replay(s, done, same_operation)

    # 3. Check everything before writing anything.
    for line in changes:
        item = locked[line.item_id]
        if line.revision is not None and line.revision != item.revision:
            raise ApiError(
                ErrorCode.STALE_REVISION,
                "This item was changed elsewhere",
                {"item_id": str(item.id), "current_revision": item.revision},
            )
        if not line.remove:
            _check_label_date(item, line.changes)
    ingredients = {
        line.item.ingredient_id: _ingredient(s, line.item.ingredient_id)
        for line in lines
        if isinstance(line, NewBatch) and line.item.ingredient_id is not None
    }

    # 4. Write the event. The unique constraint, not a look-up, decides a race.
    event = m.StockEvent(
        household_id=user.household_id,
        user_id=user.user_id,
        type=event_type.value,
        idempotency_key=idempotency_key,
        ref_type=ref_type.value,
        ref_id=ref_id,
        created_at=clock.now(),
    )
    won = _insert_event(s, event)
    if not won:
        done = _find_event(s, user.household_id, idempotency_key)
        if done is None:
            raise ApiError(ErrorCode.CONFLICT, "Could not record this change; try again")
        return _replay(s, done, same_operation)

    # 5. Write the lines and change the items.
    now = clock.now()
    rows: list[m.StockEventLine] = []
    for line in lines:
        if isinstance(line, NewBatch):
            ingredient = ingredients.get(line.item.ingredient_id)
            item = _new_item(user.household_id, line, ingredient, now)
            s.add(item)
            s.flush()
            rows.append(_line(event, item, None, _snapshot(item)))
        elif line.remove:
            item = locked[line.item_id]
            before = _snapshot(item)
            item.deleted_at = now
            item.revision += 1
            rows.append(_line(event, item, before, None))
        else:
            item = locked[line.item_id]
            before = _snapshot(item)
            ingredient = None if item.ingredient_id is None else _ingredient(s, item.ingredient_id)
            _change_item(item, line.changes, ingredient, now)
            item.revision += 1
            rows.append(_line(event, item, before, _snapshot(item)))
    s.add_all(rows)
    s.flush()
    return _change(s, event, rows)


# --------------------------------------------------------------------------- snapshots


def _iso(value: date | datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _snapshot(item: m.InventoryItem) -> dict[str, Any]:
    """Everything an edit can change, as JSON, plus the revision the item has after it."""
    return {
        "count": None if item.count is None else float(item.count),
        "unit": item.unit,
        "remaining_state": item.remaining_state,
        "storage": item.storage,
        "label_date": _iso(item.label_date),
        "label_date_kind": item.label_date_kind,
        "display_name": item.display_name,
        "freshness_confirmed_at": _iso(item.freshness_confirmed_at),
        "revision": item.revision,
    }


def _line(
    event: m.StockEvent,
    item: m.InventoryItem,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> m.StockEventLine:
    return m.StockEventLine(
        event_id=event.id, inventory_item_id=item.id, before=before, after=after
    )


# --------------------------------------------------------------------------- changing items


def _check_changes(changes: dict[str, Any]) -> None:
    unknown = set(changes) - CHANGEABLE_FIELDS
    if unknown:
        raise ApiError(
            ErrorCode.VALIDATION, "These fields cannot be changed", {"fields": sorted(unknown)}
        )
    for field, value in changes.items():
        _coerce(field, value)  # raises VALIDATION for a bad value


def _coerce(field: str, value: Any) -> Any:
    """A value in the form the column stores. None means "unknown" where that is allowed."""
    try:
        match field:
            case "count":
                if value is None:
                    return None
                number = Decimal(str(value))
                if number < 0:
                    raise ValueError("count cannot be negative")
                return number
            case "remaining_state":
                return (
                    RemainingState.UNKNOWN.value if value is None else RemainingState(value).value
                )
            case "storage":
                return Storage(value).value
            case "label_date_kind":
                return None if value is None else LabelDateKind(value).value
            case "label_date":
                if value is None or isinstance(value, date):
                    return value
                return date.fromisoformat(value)
            case "freshness_confirmed_at":
                if value is None or isinstance(value, datetime):
                    return value
                return datetime.fromisoformat(value)
            case "display_name":
                if not isinstance(value, str) or not value.strip():
                    raise ValueError("display_name cannot be empty")
                return value
            case _:  # unit
                return value
    except (ValueError, InvalidOperation, TypeError) as error:
        raise ApiError(
            ErrorCode.VALIDATION, f"Invalid value for {field}", {"field": field}
        ) from error


def _check_label_date(item: m.InventoryItem, changes: dict[str, Any]) -> None:
    """Refuse an edit that would leave a label date without its kind, before changing anything."""
    label_date = (
        _coerce("label_date", changes["label_date"]) if "label_date" in changes else item.label_date
    )
    if "label_date_kind" in changes:
        kind = _coerce("label_date_kind", changes["label_date_kind"])
    else:
        kind = item.label_date_kind if label_date is not None else None
    if label_date is not None and kind is None:
        raise ApiError(ErrorCode.VALIDATION, "label_date_kind is required when label_date is set")


def _change_item(
    item: m.InventoryItem,
    changes: dict[str, Any],
    ingredient: m.Ingredient | None,
    now: datetime,
) -> None:
    for field, value in changes.items():
        setattr(item, field, _coerce(field, value))
    # A count of zero means none left, and a positive count means some left. Counted
    # ingredients only; a state the user set in the same edit always wins.
    counted = ingredient is not None and ingredient.countable
    if counted and "count" in changes and "remaining_state" not in changes:
        if item.count is not None and item.count == 0:
            item.remaining_state = RemainingState.OUT.value
        elif item.count is not None and item.remaining_state == RemainingState.OUT.value:
            item.remaining_state = RemainingState.ENOUGH.value
    if item.label_date is None and "label_date_kind" not in changes:
        item.label_date_kind = None
    if changes.keys() & {"count", "unit", "remaining_state"}:
        item.last_confirmed_at = now


def _new_item(
    household_id: UUID, line: NewBatch, ingredient: m.Ingredient | None, now: datetime
) -> m.InventoryItem:
    spec = line.item
    name = spec.display_name or (
        None if ingredient is None else ingredient.canonical_name.capitalize()
    )
    if name is None:
        raise ApiError(ErrorCode.VALIDATION, "A free-text item needs a display_name")
    storage = spec.storage or (ingredient.default_storage if ingredient else None) or Storage.PANTRY
    unit = _inventory_unit(spec.unit, ingredient)
    if line.use_default_unit and unit is None and spec.count is not None and ingredient is not None:
        unit = ingredient.default_unit
    state = RemainingState(spec.remaining_state).value
    counted = ingredient is not None and ingredient.countable
    if counted and spec.count is not None and spec.count == 0:
        state = RemainingState.OUT.value
    return m.InventoryItem(
        household_id=household_id,
        ingredient_id=spec.ingredient_id,
        display_name=name,
        count=None if spec.count is None else Decimal(str(spec.count)),
        unit=unit,
        remaining_state=state,
        storage=Storage(storage).value,
        source=ItemSource(line.source).value,
        acquired_at=spec.acquired_at or clock.today(),
        label_date=spec.label_date,
        label_date_kind=None if spec.label_date_kind is None else spec.label_date_kind.value,
        last_confirmed_at=now,
        revision=1,
    )


def _inventory_unit(unit: str | None, ingredient: m.Ingredient | None) -> str | None:
    """Canonicalise count words only; never convert weights, volumes or packs.

    For a food counted in pieces, its own name ("2 eggs", "1 cabbage") and "head" count too.
    """
    key = unit.strip().casefold() if unit is not None else None
    if key in {"pcs", "piece", "pieces"}:
        return "pcs"
    if ingredient is not None and ingredient.default_unit == "pcs":
        names = {
            n.strip().casefold() for n in (ingredient.canonical_name, *(ingredient.aliases or []))
        }
        if key in {"head", "heads"} | names | {f"{n}s" for n in names} | {f"{n}es" for n in names}:
            return "pcs"
    return unit


def _ingredient(s: Session, ingredient_id: UUID) -> m.Ingredient:
    found = s.get(m.Ingredient, ingredient_id)
    if found is None:
        raise ApiError(ErrorCode.NOT_FOUND, "Ingredient not found", {"id": str(ingredient_id)})
    return found


def _lock_items(
    s: Session, household_id: UUID, ids: list[UUID], include_removed: bool = False
) -> dict[UUID, m.InventoryItem]:
    """Lock these items (in id order, so two requests cannot deadlock) and return them.

    An id that is missing, removed or in another household raises NOT_FOUND, so a caller
    cannot tell the difference between "not yours" and "does not exist".
    """
    if not ids:
        return {}
    query = (
        select(m.InventoryItem)
        .where(m.InventoryItem.id.in_(ids), m.InventoryItem.household_id == household_id)
        .order_by(m.InventoryItem.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not include_removed:
        query = query.where(m.InventoryItem.deleted_at.is_(None))
    found = {item.id: item for item in s.scalars(query)}
    for item_id in ids:
        if item_id not in found:
            raise ApiError(ErrorCode.NOT_FOUND, "Inventory item not found", {"id": str(item_id)})
    return found


# --------------------------------------------------------------------------- idempotency


def _find_event(s: Session, household_id: UUID, key: UUID) -> m.StockEvent | None:
    return s.scalars(
        select(m.StockEvent).where(
            m.StockEvent.household_id == household_id, m.StockEvent.idempotency_key == key
        )
    ).first()


def _insert_event(s: Session, event: m.StockEvent) -> bool:
    """Insert the event. False means another request with the same key got there first."""
    try:
        with s.begin_nested():
            s.add(event)
            s.flush()
    except IntegrityError:
        return False
    return True


def _lines_of(s: Session, event_id: UUID) -> list[m.StockEventLine]:
    return list(
        s.scalars(select(m.StockEventLine).where(m.StockEventLine.event_id == event_id)).all()
    )


def _replays(
    s: Session,
    event: m.StockEvent,
    event_type: StockEventType,
    ref_type: StockRefType,
    ref_id: UUID | None,
    lines: list[StockLine],
) -> bool:
    """Is this request the same operation that the stored event recorded?"""
    if (event.type, event.ref_type, event.ref_id) != (event_type.value, ref_type.value, ref_id):
        return False
    stored = _lines_of(s, event.id)
    changed = {row.inventory_item_id for row in stored if row.before is not None}
    created = sum(1 for row in stored if row.before is None)
    asked = {line.item_id for line in lines if isinstance(line, ChangeBatch)}
    new = sum(1 for line in lines if isinstance(line, NewBatch))
    return changed == asked and created == new


def _replay(s: Session, event: m.StockEvent, same_operation) -> InventoryChange:
    if not same_operation(event):
        raise ApiError(
            ErrorCode.CONFLICT,
            "This Idempotency-Key was already used for a different request",
            {"event_id": str(event.id)},
        )
    return _change(s, event, _lines_of(s, event.id))


# --------------------------------------------------------------------------- the response


def _lines_by_event(s: Session, event_ids: list[UUID]) -> dict[UUID, list[m.StockEventLine]]:
    grouped: dict[UUID, list[m.StockEventLine]] = {}
    if event_ids:
        rows = s.scalars(
            select(m.StockEventLine).where(m.StockEventLine.event_id.in_(event_ids))
        ).all()
        for row in rows:
            grouped.setdefault(row.event_id, []).append(row)
    return grouped


def _snap(data: dict[str, Any] | None) -> ItemSnapshot | None:
    if data is None:
        return None
    return ItemSnapshot(
        count=data["count"], unit=data["unit"], remaining_state=data["remaining_state"]
    )


def _event_view(event: m.StockEvent, rows: list[m.StockEventLine]) -> StockEvent:
    lines = [
        StockEventLine(
            inventory_item_id=row.inventory_item_id,
            display_name=(row.after or row.before or {}).get("display_name", ""),
            before=_snap(row.before),
            after=_snap(row.after),
        )
        for row in rows
    ]
    lines.sort(key=lambda line: (line.display_name.lower(), str(line.inventory_item_id)))
    return StockEvent(
        id=event.id,
        type=StockEventType(event.type),
        ref_type=StockRefType(event.ref_type),
        ref_id=event.ref_id,
        user_id=event.user_id,
        created_at=event.created_at,
        lines=lines,
        reverts_event_id=event.reverts_event_id,
        can_undo=(
            event.type != StockEventType.UNDO.value
            and event.reverted_by_event_id is None
            and bool(lines)
        ),
    )


def _change(s: Session, event: m.StockEvent, rows: list[m.StockEventLine]) -> InventoryChange:
    """The event, and the touched batches as they are now (removed ones are left out)."""
    today, now = clock.today(), clock.now()
    ids = [row.inventory_item_id for row in rows]
    items: list[InventoryItem] = []
    if ids:
        found = s.execute(
            select(m.InventoryItem, m.Ingredient)
            .outerjoin(m.Ingredient, m.Ingredient.id == m.InventoryItem.ingredient_id)
            .where(m.InventoryItem.id.in_(ids), m.InventoryItem.deleted_at.is_(None))
            .execution_options(populate_existing=True)
        ).all()
        items = sorted(
            (item_view(batch, ingredient, today, now) for batch, ingredient in found),
            key=_use_first_first,
        )
    return InventoryChange(event=_event_view(event, rows), items=items)


# --------------------------------------------------------------------------- undo


def _undo(s: Session, user: CurrentUser, event_id: UUID, key: UUID) -> UndoResult:
    def replay(done: m.StockEvent) -> UndoResult:
        if done.type != StockEventType.UNDO.value or done.reverts_event_id != event_id:
            raise ApiError(
                ErrorCode.CONFLICT,
                "This Idempotency-Key was already used for a different request",
                {"event_id": str(done.id)},
            )
        return _undo_result(s, user, done)

    done = _find_event(s, user.household_id, key)
    if done is not None:
        return replay(done)

    original = s.scalars(
        select(m.StockEvent)
        .where(m.StockEvent.id == event_id, m.StockEvent.household_id == user.household_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if original is None:
        raise ApiError(ErrorCode.NOT_FOUND, "Stock event not found")

    done = _find_event(s, user.household_id, key)  # an identical retry may have just finished
    if done is not None:
        return replay(done)
    if original.type == StockEventType.UNDO.value:
        raise ApiError(ErrorCode.CONFLICT, "An undo cannot be undone")
    if original.reverted_by_event_id is not None:
        raise ApiError(ErrorCode.CONFLICT, "This event was already undone")

    rows = _lines_of(s, original.id)
    items = _lock_items(
        s, user.household_id, [row.inventory_item_id for row in rows], include_removed=True
    )

    restorable: list[m.StockEventLine] = []
    for row in rows:
        item = items[row.inventory_item_id]
        # The revision the item had straight after the event. A removal bumps it once more.
        expected = row.after["revision"] if row.after is not None else row.before["revision"] + 1
        if item.revision == expected:
            restorable.append(row)

    undo = m.StockEvent(
        household_id=user.household_id,
        user_id=user.user_id,
        type=StockEventType.UNDO.value,
        idempotency_key=key,
        ref_type=original.ref_type,
        ref_id=original.ref_id,
        reverts_event_id=original.id,
        created_at=clock.now(),
    )
    if not _insert_event(s, undo):
        done = _find_event(s, user.household_id, key)
        if done is None:
            raise ApiError(ErrorCode.CONFLICT, "Could not record this undo; try again")
        return replay(done)

    now = clock.now()
    undo_rows: list[m.StockEventLine] = []
    for row in restorable:
        item = items[row.inventory_item_id]
        current = None if item.deleted_at is not None else _snapshot(item)
        if row.before is None:  # the event created it: undo removes it
            item.deleted_at = now
        else:  # restore every field it had, and bring a removed item back
            for field in CHANGEABLE_FIELDS:
                setattr(item, field, _coerce(field, row.before[field]))
            item.deleted_at = None
            item.last_confirmed_at = now
        item.revision += 1
        after = None if item.deleted_at is not None else _snapshot(item)
        undo_rows.append(_line(undo, item, current, after))
    s.add_all(undo_rows)
    if undo_rows:
        original.reverted_by_event_id = undo.id
    s.flush()
    return _undo_result(s, user, undo)


def _undo_result(s: Session, user: CurrentUser, undo: m.StockEvent) -> UndoResult:
    rows = _lines_of(s, undo.id)
    change = _change(s, undo, rows)
    restored = {row.inventory_item_id for row in rows}
    conflicts = []
    if undo.reverts_event_id is not None:
        for row in _lines_of(s, undo.reverts_event_id):
            if row.inventory_item_id in restored:
                continue
            snapshot = row.after or row.before or {}
            conflicts.append(
                UndoConflict(
                    inventory_item_id=row.inventory_item_id,
                    display_name=snapshot.get("display_name", ""),
                    reason="Changed since this event, so it was left as it is",
                )
            )
    return UndoResult(event=change.event, items=change.items, conflicts=conflicts)


def get_inventory_snapshot(s: Session, household_id: UUID) -> list[InventoryItem]:
    """Every batch the household has, removed ones excluded.

    Each batch already carries `est_use_first_date` and `freshness_status`, computed on
    read (app/db/README.md), so the recommendation code only reads them. Batches come back
    earliest use-first date first; those with no date come last.
    """
    today, now = clock.today(), clock.now()
    rows = s.execute(
        select(m.InventoryItem, m.Ingredient)
        .outerjoin(m.Ingredient, m.Ingredient.id == m.InventoryItem.ingredient_id)
        .where(m.InventoryItem.household_id == household_id, m.InventoryItem.deleted_at.is_(None))
    ).all()
    items = [item_view(batch, ingredient, today, now) for batch, ingredient in rows]
    return sorted(items, key=_use_first_first)


def item_view(
    batch: m.InventoryItem, ingredient: m.Ingredient | None, today: date, now: datetime
) -> InventoryItem:
    """One stored batch in the shape the API returns, with its freshness worked out.

    A free-text item has no ingredient, so it is reported as category "other", tracked by
    state, and with no shelf life (so no estimated date).
    """
    shelf_life = getattr(ingredient, f"shelf_life_days_{batch.storage}", None)
    use_first = use_first_date(batch.label_date, batch.acquired_at, shelf_life)
    category = None if ingredient is None else ingredient.category
    return InventoryItem(
        id=batch.id,
        ingredient_id=batch.ingredient_id,
        display_name=batch.display_name,
        category=category or "other",
        countable=bool(ingredient and ingredient.countable),
        count=None if batch.count is None else float(batch.count),
        unit=batch.unit,
        remaining_state=batch.remaining_state,
        storage=batch.storage,
        source=batch.source,
        acquired_at=batch.acquired_at,
        label_date=batch.label_date,
        label_date_kind=batch.label_date_kind,
        est_use_first_date=use_first,
        freshness_status=freshness_status(
            today=today,
            now=now,
            remaining_state=batch.remaining_state,
            label_date=batch.label_date,
            label_date_kind=batch.label_date_kind,
            use_first=use_first,
            category=category,
            freshness_confirmed_at=batch.freshness_confirmed_at,
        ),
        freshness_confirmed_at=batch.freshness_confirmed_at,
        last_confirmed_at=batch.last_confirmed_at,
        revision=batch.revision,
    )


def _use_first_first(item: InventoryItem) -> tuple[bool, date, str, str]:
    return (
        item.est_use_first_date is None,
        item.est_use_first_date or date.max,
        item.display_name.lower(),
        str(item.id),
    )
