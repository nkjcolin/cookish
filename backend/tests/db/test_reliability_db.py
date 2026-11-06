"""SPEC A10, "Are stock updates reliable?": no double change, even when requests collide."""

import threading
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.auth import CurrentUser
from app.db import models as m
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.schemas.inventory import InventoryItemCreate, InventoryItemsCreate, InventoryItemUpdate
from app.services import identity, inventory
from app.services.stock_events import list_events, undo_event

USER = UUID("11111111-1111-4111-8111-111111111111")


def _login() -> CurrentUser:
    with transaction() as s:
        return identity.get_or_create_user(s, USER, "dev@cookish.test")


def _race(count: int, work) -> list:
    """Run `work(i)` in `count` threads that all start together; return what each gave back."""
    results: list = [None] * count
    barrier = threading.Barrier(count)

    def run(i: int) -> None:
        barrier.wait()
        try:
            results[i] = work(i)
        except ApiError as error:
            results[i] = error.code

    threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def test_two_undos_of_one_event_at_the_same_moment_undo_it_once():
    user = _login()
    added = inventory.add_items(
        user, InventoryItemsCreate(items=[InventoryItemCreate(display_name="Rice")]), uuid4()
    )
    results = _race(4, lambda i: undo_event(user, added.event.id, uuid4()))
    done = [r for r in results if not isinstance(r, ErrorCode)]
    assert len(done) == 1 and all(r == ErrorCode.CONFLICT for r in results if r not in done)
    with transaction() as s:
        undo_events = s.scalar(
            select(func.count()).select_from(m.StockEvent).where(m.StockEvent.type == "undo")
        )
        item = s.get(m.InventoryItem, added.items[0].id)
        revision, removed = item.revision, item.deleted_at is not None
    assert undo_events == 1 and revision == 2 and removed


def test_many_edits_of_one_item_at_the_same_moment_apply_exactly_one():
    user = _login()
    (item,) = inventory.add_items(
        user, InventoryItemsCreate(items=[InventoryItemCreate(display_name="Rice")]), uuid4()
    ).items
    results = _race(
        8,
        lambda i: inventory.update_item(
            user, item.id, InventoryItemUpdate(revision=1, unit=f"u{i}"), uuid4()
        ),
    )
    assert sum(r == ErrorCode.STALE_REVISION for r in results) == 7
    with transaction() as s:
        revision = s.get(m.InventoryItem, item.id).revision
        edits = s.scalar(
            select(func.count()).select_from(m.StockEvent).where(m.StockEvent.type == "adjust")
        )
    assert revision == 2 and edits == 1


def test_an_edit_and_an_undo_at_the_same_moment_never_lose_either_change():
    user = _login()
    (item,) = inventory.add_items(
        user, InventoryItemsCreate(items=[InventoryItemCreate(display_name="Rice")]), uuid4()
    ).items
    first = inventory.update_item(
        user, item.id, InventoryItemUpdate(revision=1, unit="kg"), uuid4()
    )

    def work(i: int):
        if i == 0:
            return undo_event(user, first.event.id, uuid4())
        return inventory.update_item(
            user, item.id, InventoryItemUpdate(revision=2, unit="g"), uuid4()
        )

    results = _race(2, work)
    with transaction() as s:
        unit = s.get(m.InventoryItem, item.id).unit
    # Either the undo ran first (unit back to None) and the edit was then refused as stale,
    # or the edit ran first and the undo reported a conflict. The item is never half of each.
    assert unit in (None, "g")
    undone = not isinstance(results[0], ErrorCode) and results[0].conflicts == []
    if undone:
        assert results[1] == ErrorCode.STALE_REVISION and unit is None
    else:
        assert unit == "g" and results[0].conflicts


def test_a_retry_storm_leaves_one_event_per_action():
    user = _login()
    keys = [uuid4() for _ in range(3)]
    body = InventoryItemsCreate(items=[InventoryItemCreate(display_name="Rice")])
    _race(12, lambda i: inventory.add_items(user, body, keys[i % 3]))
    assert len(list_events(user, 50).events) == 3
    with transaction() as s:
        assert s.scalar(select(func.count()).select_from(m.InventoryItem)) == 3
