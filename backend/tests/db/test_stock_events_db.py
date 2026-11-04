"""The write path against a real Postgres: add, edit, remove, idempotency, undo and tenancy."""

import threading
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app import clock
from app.auth import CurrentUser
from app.db import models as m
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.schemas.common import ItemSource
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemsCreate,
    InventoryItemUpdate,
)
from app.schemas.stock_events import StockEventType, StockRefType
from app.services import identity, inventory
from app.services.stock_events import (
    CHANGEABLE_FIELDS,
    ChangeBatch,
    _snapshot,
    apply_stock_event,
    get_inventory_snapshot,
    list_events,
    undo_event,
)

USER = UUID("11111111-1111-4111-8111-111111111111")
OTHER = UUID("22222222-2222-4222-8222-222222222222")


def _login(user_id: UUID = USER, email: str = "dev@cookish.test") -> CurrentUser:
    with transaction() as s:
        return identity.get_or_create_user(s, user_id, email)


def _ingredient(name: str, countable: bool = False, **extra) -> UUID:
    ingredient_id = uuid4()
    with transaction() as s:
        s.add(
            m.Ingredient(
                id=ingredient_id,
                canonical_name=name,
                category=extra.pop("category", "produce"),
                countable=countable,
                default_unit="pcs" if countable else None,
                default_storage=extra.pop("default_storage", "fridge"),
                shelf_life_days_fridge=7,
                **extra,
            )
        )
    return ingredient_id


def _add(user: CurrentUser, ingredient_id: UUID | None = None, key: UUID | None = None, **fields):
    body = InventoryItemsCreate(
        source=fields.pop("source", ItemSource.MANUAL),
        items=[InventoryItemCreate(ingredient_id=ingredient_id, **fields)],
    )
    return inventory.add_items(user, body, key or uuid4())


def _row(item_id: UUID) -> m.InventoryItem:
    with transaction() as s:
        row = s.get(m.InventoryItem, item_id)
        s.expunge(row)
        return row


def _count(model) -> int:
    with transaction() as s:
        return s.scalar(select(func.count()).select_from(model))


def _fails(code: ErrorCode):
    return pytest.raises(ApiError, check=lambda error: error.code == code)


# --------------------------------------------------------------------------- adding


def test_adding_an_ingredient_takes_its_name_unit_and_storage_from_the_catalogue():
    user = _login()
    egg = _ingredient("egg", countable=True)
    change = _add(user, egg, count=6)
    (item,) = change.items
    assert (item.display_name, item.count, item.unit, item.storage) == ("Egg", 6, "pcs", "fridge")
    assert item.revision == 1 and item.source == "manual"
    assert change.event.type == StockEventType.PURCHASE
    (line,) = change.event.lines
    assert line.before is None and line.after.count == 6
    assert [g.name for g in inventory.list_inventory(user).groups] == ["Egg"]


def test_a_free_text_item_needs_a_name_and_is_tracked_by_state():
    user = _login()
    change = _add(user, display_name="Grandma's chilli oil")
    (item,) = change.items
    assert item.ingredient_id is None and item.category == "other" and not item.countable
    assert item.remaining_state == "enough" and item.storage == "pantry"


def test_several_items_in_one_request_make_one_event():
    user = _login()
    body = InventoryItemsCreate(
        items=[InventoryItemCreate(display_name="Rice"), InventoryItemCreate(display_name="Salt")]
    )
    change = inventory.add_items(user, body, uuid4())
    assert len(change.items) == 2 and len(change.event.lines) == 2
    assert _count(m.StockEvent) == 1 and _count(m.StockEventLine) == 2


def test_an_unknown_ingredient_is_not_found():
    user = _login()
    with _fails(ErrorCode.NOT_FOUND):
        _add(user, uuid4())
    assert _count(m.InventoryItem) == 0 and _count(m.StockEvent) == 0


def test_a_count_of_zero_on_a_counted_ingredient_means_out():
    user = _login()
    egg = _ingredient("egg", countable=True)
    (item,) = _add(user, egg, count=0).items
    assert item.remaining_state == "out"


# --------------------------------------------------------------------------- idempotency


def test_repeating_a_key_returns_the_first_change_and_adds_nothing():
    user = _login()
    key = uuid4()
    first = _add(user, display_name="Rice", key=key)
    again = _add(user, display_name="Rice", key=key)
    assert again.event.id == first.event.id
    assert [i.id for i in again.items] == [i.id for i in first.items]
    assert _count(m.InventoryItem) == 1 and _count(m.StockEvent) == 1


def test_reusing_a_key_for_a_different_operation_is_a_conflict():
    user = _login()
    key = uuid4()
    (item,) = _add(user, display_name="Rice", key=key).items
    with _fails(ErrorCode.CONFLICT):
        inventory.delete_item(user, item.id, item.revision, key)
    assert _row(item.id).deleted_at is None


def test_the_same_key_in_two_households_is_two_different_events():
    key = uuid4()
    mine, theirs = _login(), _login(OTHER, "other@cookish.test")
    _add(mine, display_name="Rice", key=key)
    _add(theirs, display_name="Rice", key=key)
    assert _count(m.StockEvent) == 2 and _count(m.InventoryItem) == 2


def test_an_empty_event_is_recorded_and_its_retry_is_a_no_op():
    user = _login()
    key, ref = uuid4(), uuid4()
    with transaction() as s:
        first = apply_stock_event(
            s, user, StockEventType.CONSUME, [], key, StockRefType.COOK_SESSION, ref
        )
    with transaction() as s:
        again = apply_stock_event(
            s, user, StockEventType.CONSUME, [], key, StockRefType.COOK_SESSION, ref
        )
    assert first.items == [] and first.event.lines == [] and not first.event.can_undo
    assert again.event.id == first.event.id and _count(m.StockEvent) == 1
    with _fails(ErrorCode.CONFLICT), transaction() as s:
        apply_stock_event(s, user, StockEventType.CONSUME, [], key, StockRefType.BASKET, ref)


def test_two_requests_with_one_key_at_the_same_time_change_things_once():
    user = _login()
    key = uuid4()
    results, errors = [], []
    barrier = threading.Barrier(4)

    def attempt():
        barrier.wait()
        try:
            results.append(_add(user, display_name="Rice", key=key))
        except Exception as error:  # noqa: BLE001 - reported by the assertion below
            errors.append(error)

    threads = [threading.Thread(target=attempt) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len({r.event.id for r in results}) == 1
    assert _count(m.InventoryItem) == 1 and _count(m.StockEvent) == 1


# --------------------------------------------------------------------------- editing


def test_an_edit_bumps_the_revision_and_keeps_before_and_after():
    user = _login()
    egg = _ingredient("egg", countable=True)
    (item,) = _add(user, egg, count=6).items
    change = inventory.update_item(user, item.id, InventoryItemUpdate(revision=1, count=4), uuid4())
    (edited,) = change.items
    assert (edited.count, edited.revision) == (4, 2)
    (line,) = change.event.lines
    assert (line.before.count, line.after.count) == (6, 4)
    assert change.event.type == StockEventType.ADJUST and change.event.can_undo


def test_a_field_that_is_absent_is_kept_and_one_sent_as_null_becomes_unknown():
    user = _login()
    egg = _ingredient("egg", countable=True)
    (item,) = _add(user, egg, count=6, label_date="2030-01-01", label_date_kind="best_before").items
    body = InventoryItemUpdate.model_validate({"revision": 1, "count": None})
    (edited,) = inventory.update_item(user, item.id, body, uuid4()).items
    assert edited.count is None and edited.unit == "pcs"
    assert edited.label_date is not None  # not sent, so not touched


def test_a_stale_edit_is_refused_and_changes_nothing():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    inventory.update_item(user, item.id, InventoryItemUpdate(revision=1, unit="kg"), uuid4())
    events_before = _count(m.StockEvent)
    with pytest.raises(ApiError) as caught:
        inventory.update_item(user, item.id, InventoryItemUpdate(revision=1, unit="g"), uuid4())
    assert caught.value.code == ErrorCode.STALE_REVISION
    assert caught.value.details["current_revision"] == 2
    assert _row(item.id).unit == "kg" and _count(m.StockEvent) == events_before


def test_confirming_freshness_records_the_time():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    body = InventoryItemUpdate(revision=1, freshness_confirmed=True)
    (edited,) = inventory.update_item(user, item.id, body, uuid4()).items
    assert edited.freshness_confirmed_at is not None


def test_a_label_date_needs_its_kind():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    line = ChangeBatch(item.id, 1, {"label_date": clock.today()})
    with _fails(ErrorCode.VALIDATION), transaction() as s:
        apply_stock_event(s, user, StockEventType.ADJUST, [line], uuid4())
    assert _row(item.id).revision == 1


def test_a_field_that_may_not_change_is_refused():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    for changes in ({"source": "photo"}, {"remaining_state": "plenty"}, {"count": -1}):
        line = ChangeBatch(item.id, 1, changes)
        with _fails(ErrorCode.VALIDATION), transaction() as s:
            apply_stock_event(s, user, StockEventType.ADJUST, [line], uuid4())
    assert _row(item.id).revision == 1


def test_the_same_item_twice_in_one_event_is_refused():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    lines = [ChangeBatch(item.id, 1, {"unit": "kg"}), ChangeBatch(item.id, 1, {"unit": "g"})]
    with _fails(ErrorCode.VALIDATION), transaction() as s:
        apply_stock_event(s, user, StockEventType.ADJUST, lines, uuid4())


def test_a_system_change_without_a_revision_is_not_checked():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    inventory.update_item(user, item.id, InventoryItemUpdate(revision=1, unit="kg"), uuid4())
    line = ChangeBatch(item.id, None, {"remaining_state": "low"})
    with transaction() as s:
        change = apply_stock_event(s, user, StockEventType.CONSUME, [line], uuid4())
    assert change.items[0].remaining_state == "low" and change.items[0].revision == 3


def test_two_edits_of_one_item_at_the_same_time_cannot_both_win():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    outcomes = []
    barrier = threading.Barrier(2)

    def edit(unit: str):
        barrier.wait()
        try:
            inventory.update_item(
                user, item.id, InventoryItemUpdate(revision=1, unit=unit), uuid4()
            )
            outcomes.append("ok")
        except ApiError as error:
            outcomes.append(error.code)

    threads = [threading.Thread(target=edit, args=(u,)) for u in ("kg", "g")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(map(str, outcomes)) == ["STALE_REVISION", "ok"]
    assert _row(item.id).revision == 2


def test_an_edit_waits_for_another_in_progress_edit_and_is_then_refused():
    """Deterministic version of the race: the first edit holds its lock until we release it."""
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    outcome = []

    def second_edit():
        try:
            inventory.update_item(user, item.id, InventoryItemUpdate(revision=1, unit="g"), uuid4())
            outcome.append("ok")
        except ApiError as error:
            outcome.append(error.code)

    with transaction() as s:
        line = ChangeBatch(item.id, 1, {"unit": "kg"})
        apply_stock_event(s, user, StockEventType.ADJUST, [line], uuid4())  # not committed yet
        thread = threading.Thread(target=second_edit)
        thread.start()
        thread.join(timeout=1)
        assert thread.is_alive()  # it is waiting for the lock, not racing past it
    thread.join(timeout=10)
    assert outcome == [ErrorCode.STALE_REVISION]
    assert _row(item.id).unit == "kg" and _row(item.id).revision == 2


# --------------------------------------------------------------------------- removing


def test_removing_an_item_hides_it_but_keeps_the_row():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    change = inventory.delete_item(user, item.id, 1, uuid4())
    assert change.items == [] and change.event.lines[0].after is None
    assert _row(item.id).deleted_at is not None
    assert get_inventory_snapshot_ids(user) == []


def get_inventory_snapshot_ids(user: CurrentUser) -> list[UUID]:
    with transaction() as s:
        return [i.id for i in get_inventory_snapshot(s, user.household_id)]


def test_retrying_a_removal_returns_the_same_result_not_not_found():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    key = uuid4()
    first = inventory.delete_item(user, item.id, 1, key)
    again = inventory.delete_item(user, item.id, 1, key)
    assert again.event.id == first.event.id and again.items == []


def test_removing_with_a_stale_revision_is_refused():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    inventory.update_item(user, item.id, InventoryItemUpdate(revision=1, unit="kg"), uuid4())
    with _fails(ErrorCode.STALE_REVISION):
        inventory.delete_item(user, item.id, 1, uuid4())
    assert _row(item.id).deleted_at is None


# --------------------------------------------------------------------------- other households


def test_another_households_item_cannot_be_read_changed_or_removed():
    mine, theirs = _login(), _login(OTHER, "other@cookish.test")
    (item,) = _add(theirs, display_name="Their rice").items
    with _fails(ErrorCode.NOT_FOUND):
        inventory.update_item(mine, item.id, InventoryItemUpdate(revision=1, unit="kg"), uuid4())
    with _fails(ErrorCode.NOT_FOUND):
        inventory.delete_item(mine, item.id, 1, uuid4())
    line = ChangeBatch(item.id, None, {"remaining_state": "out"})
    with _fails(ErrorCode.NOT_FOUND), transaction() as s:
        apply_stock_event(s, mine, StockEventType.CONSUME, [line], uuid4())
    assert inventory.list_inventory(mine).groups == []
    assert _row(item.id).revision == 1 and _row(item.id).deleted_at is None


def test_another_households_events_cannot_be_listed_or_undone():
    mine, theirs = _login(), _login(OTHER, "other@cookish.test")
    event = _add(theirs, display_name="Their rice").event
    assert list_events(mine, 10).events == []
    with _fails(ErrorCode.NOT_FOUND):
        undo_event(mine, event.id, uuid4())
    assert [e.id for e in list_events(theirs, 10).events] == [event.id]


# --------------------------------------------------------------------------- the activity list


def test_events_are_listed_newest_first_up_to_the_limit():
    user = _login()
    first = _add(user, display_name="Rice").event
    second = _add(user, display_name="Salt").event
    third = _add(user, display_name="Oil").event
    assert [e.id for e in list_events(user, 10).events] == [third.id, second.id, first.id]
    assert [e.id for e in list_events(user, 2).events] == [third.id, second.id]


# --------------------------------------------------------------------------- undo


def test_undoing_an_add_removes_the_item():
    user = _login()
    change = _add(user, display_name="Rice")
    (item,) = change.items
    result = undo_event(user, change.event.id, uuid4())
    assert result.conflicts == [] and result.items == []
    assert result.event.type == StockEventType.UNDO and result.event.reverts_event_id
    assert get_inventory_snapshot_ids(user) == []
    events = {e.id: e for e in list_events(user, 10).events}
    assert not events[change.event.id].can_undo  # already undone
    assert _row(item.id).deleted_at is not None


def test_undoing_an_edit_restores_every_field():
    user = _login()
    egg = _ingredient("egg", countable=True)
    (item,) = _add(user, egg, count=6, label_date="2030-01-01", label_date_kind="use_by").items
    body = InventoryItemUpdate(
        revision=1, count=1, unit="box", storage="freezer", display_name="Eggs"
    )
    edit = inventory.update_item(user, item.id, body, uuid4())
    result = undo_event(user, edit.event.id, uuid4())
    (restored,) = result.items
    assert (restored.count, restored.unit, restored.storage) == (6, "pcs", "fridge")
    assert (restored.display_name, str(restored.label_date)) == ("Egg", "2030-01-01")
    assert restored.revision == 3  # an undo is a change too


def test_undoing_a_removal_brings_the_item_back():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    removal = inventory.delete_item(user, item.id, 1, uuid4())
    result = undo_event(user, removal.event.id, uuid4())
    assert [i.id for i in result.items] == [item.id]
    assert get_inventory_snapshot_ids(user) == [item.id]
    assert _row(item.id).deleted_at is None


def test_undo_after_a_later_edit_reports_a_conflict_and_leaves_the_item_alone():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    first = inventory.update_item(
        user, item.id, InventoryItemUpdate(revision=1, unit="kg"), uuid4()
    )
    inventory.update_item(user, item.id, InventoryItemUpdate(revision=2, unit="g"), uuid4())
    result = undo_event(user, first.event.id, uuid4())
    assert [c.inventory_item_id for c in result.conflicts] == [item.id]
    assert result.conflicts[0].display_name == "Rice"
    assert result.items == [] and _row(item.id).unit == "g"


def test_undoing_part_of_an_event_restores_the_lines_that_can_be():
    user = _login()
    body = InventoryItemsCreate(
        items=[InventoryItemCreate(display_name="Rice"), InventoryItemCreate(display_name="Salt")]
    )
    added = inventory.add_items(user, body, uuid4())
    rice = next(i for i in added.items if i.display_name == "Rice")
    inventory.update_item(user, rice.id, InventoryItemUpdate(revision=1, unit="kg"), uuid4())
    result = undo_event(user, added.event.id, uuid4())
    assert [c.display_name for c in result.conflicts] == ["Rice"]
    assert result.items == []  # Salt was removed, so nothing is left to show
    assert get_inventory_snapshot_ids(user) == [rice.id]


def test_an_undo_can_be_retried_and_cannot_be_repeated_or_undone():
    user = _login()
    change = _add(user, display_name="Rice")
    key = uuid4()
    first = undo_event(user, change.event.id, key)
    again = undo_event(user, change.event.id, key)
    assert again.event.id == first.event.id and _count(m.StockEvent) == 2
    with _fails(ErrorCode.CONFLICT):
        undo_event(user, change.event.id, uuid4())  # already undone
    with _fails(ErrorCode.CONFLICT):
        undo_event(user, first.event.id, uuid4())  # an undo cannot be undone
    with _fails(ErrorCode.CONFLICT):
        undo_event(user, uuid4(), key)  # key already used for something else
    with _fails(ErrorCode.NOT_FOUND):
        undo_event(user, uuid4(), uuid4())


def test_undoing_a_cook_restores_the_amounts_that_were_used():
    user = _login()
    egg = _ingredient("egg", countable=True)
    (item,) = _add(user, egg, count=6).items
    ref = uuid4()
    line = ChangeBatch(item.id, item.revision, {"count": 4})
    with transaction() as s:
        cook = apply_stock_event(
            s, user, StockEventType.CONSUME, [line], uuid4(), StockRefType.COOK_SESSION, ref
        )
    assert cook.event.ref_type == StockRefType.COOK_SESSION and cook.event.ref_id == ref
    result = undo_event(user, cook.event.id, uuid4())
    assert result.items[0].count == 6 and result.event.ref_id == ref


# --------------------------------------------------------------------------- housekeeping


def test_the_snapshot_holds_every_changeable_field():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    assert CHANGEABLE_FIELDS <= set(_snapshot(_row(item.id)))


def test_everything_in_a_failed_transaction_is_rolled_back():
    user = _login()
    (item,) = _add(user, display_name="Rice").items
    good = ChangeBatch(item.id, 1, {"unit": "kg"})
    bad = ChangeBatch(uuid4(), None, {"unit": "kg"})
    with pytest.raises(ApiError), transaction() as s:
        apply_stock_event(s, user, StockEventType.ADJUST, [good, bad], uuid4())
    assert _row(item.id).unit is None and _count(m.StockEvent) == 1
