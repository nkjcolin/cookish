"""Reading the kitchen from a real Postgres: grouping, ordering, tenancy and freshness."""

from datetime import timedelta
from uuid import UUID, uuid4

from app import clock
from app.auth import DEV_CLAIMS, CurrentUser
from app.db import models as m
from app.db.session import transaction
from app.schemas.common import FreshnessStatus as F
from app.services import identity, inventory
from app.services.stock_events import get_inventory_snapshot

USER = UUID("11111111-1111-4111-8111-111111111111")
OTHER = UUID("22222222-2222-4222-8222-222222222222")


def _login(user_id: UUID = USER, email: str = "dev@cookish.test") -> CurrentUser:
    with transaction() as s:
        return identity.get_or_create_user(s, user_id, email)


def _add(household_id, name, **fields) -> UUID:
    """Insert one batch straight into the table (the write path is not built yet)."""
    item_id = uuid4()
    with transaction() as s:
        s.add(
            m.InventoryItem(
                id=item_id,
                household_id=household_id,
                display_name=name,
                remaining_state=fields.pop("remaining_state", "enough"),
                storage=fields.pop("storage", "fridge"),
                source=fields.pop("source", "manual"),
                acquired_at=fields.pop("acquired_at", clock.today()),
                **fields,
            )
        )
    return item_id


def _ingredient(name: str, category: str = "produce", fridge_days: int | None = 7, **extra) -> UUID:
    ingredient_id = uuid4()
    with transaction() as s:
        s.add(
            m.Ingredient(
                id=ingredient_id,
                canonical_name=name,
                category=category,
                default_storage="fridge",
                shelf_life_days_fridge=fridge_days,
                **extra,
            )
        )
    return ingredient_id


def _snapshot(household_id):
    with transaction() as s:
        return get_inventory_snapshot(s, household_id)


def test_an_empty_kitchen_is_empty():
    user = _login()
    assert _snapshot(user.household_id) == []
    assert inventory.list_inventory(user).groups == []


def test_the_estimate_comes_from_the_purchase_date_and_the_shelf_life():
    user = _login()
    spinach = _ingredient("spinach", fridge_days=5)
    _add(user.household_id, "Spinach", ingredient_id=spinach, acquired_at=clock.today())
    (item,) = _snapshot(user.household_id)
    assert item.est_use_first_date == clock.today() + timedelta(days=5)
    assert item.freshness_status == F.OK
    assert item.category == "produce"


def test_a_printed_label_date_wins_over_the_shelf_life():
    user = _login()
    tofu = _ingredient("tofu", category="other", fridge_days=30)
    label = clock.today() + timedelta(days=2)
    _add(user.household_id, "Tofu", ingredient_id=tofu, label_date=label, label_date_kind="use_by")
    (item,) = _snapshot(user.household_id)
    assert item.est_use_first_date == label and item.freshness_status == F.USE_SOON


def test_a_batch_past_its_use_by_date_is_expired():
    user = _login()
    tofu = _ingredient("tofu", category="other")
    yesterday = clock.today() - timedelta(days=1)
    _add(
        user.household_id,
        "Tofu",
        ingredient_id=tofu,
        label_date=yesterday,
        label_date_kind="use_by",
    )
    assert _snapshot(user.household_id)[0].freshness_status == F.EXPIRED


def test_saying_it_is_fine_makes_a_past_estimate_usable():
    user = _login()
    chicken = _ingredient("chicken", category="meat", fridge_days=2)
    old = clock.today() - timedelta(days=5)
    item_id = _add(user.household_id, "Chicken", ingredient_id=chicken, acquired_at=old)
    assert _snapshot(user.household_id)[0].freshness_status == F.CHECK
    with transaction() as s:
        s.get(m.InventoryItem, item_id).freshness_confirmed_at = clock.now()
    assert _snapshot(user.household_id)[0].freshness_status == F.OK


def test_a_perishable_stored_where_we_have_no_shelf_life_is_checked():
    user = _login()
    cabbage = _ingredient("cabbage", fridge_days=14)  # no freezer shelf life
    _add(user.household_id, "Cabbage", ingredient_id=cabbage, storage="freezer")
    (item,) = _snapshot(user.household_id)
    assert item.est_use_first_date is None and item.freshness_status == F.CHECK


def test_a_free_text_item_is_other_tracked_by_state_and_never_checked_for_lack_of_a_date():
    user = _login()
    _add(user.household_id, "Homemade sambal")
    (item,) = _snapshot(user.household_id)
    assert (item.ingredient_id, item.category, item.countable) == (None, "other", False)
    assert item.est_use_first_date is None and item.freshness_status == F.OK


def test_only_the_households_own_unremoved_batches_are_returned():
    mine, theirs = _login(USER), _login(OTHER, "other@cookish.test")
    _add(mine.household_id, "Mine")
    _add(theirs.household_id, "Theirs")
    _add(mine.household_id, "Removed", deleted_at=clock.now())
    assert [i.display_name for i in _snapshot(mine.household_id)] == ["Mine"]
    assert [i.display_name for i in _snapshot(theirs.household_id)] == ["Theirs"]


def test_batches_come_earliest_use_first_date_first_and_undated_last():
    user = _login()
    spinach = _ingredient("spinach", fridge_days=5)
    today = clock.today()
    _add(user.household_id, "Later", ingredient_id=spinach, acquired_at=today)
    _add(user.household_id, "Sooner", ingredient_id=spinach, acquired_at=today - timedelta(days=3))
    _add(user.household_id, "Undated")
    assert [i.display_name for i in _snapshot(user.household_id)] == ["Sooner", "Later", "Undated"]


def test_list_inventory_groups_batches_by_ingredient_and_free_text_by_name():
    user = _login()
    egg = _ingredient("egg", category="egg", fridge_days=28, countable=True, default_unit="pcs")
    today = clock.today()
    _add(user.household_id, "Egg", ingredient_id=egg, count=6, unit="pcs", acquired_at=today)
    _add(
        user.household_id,
        "Egg",
        ingredient_id=egg,
        count=2,
        unit="pcs",
        acquired_at=today - timedelta(days=20),
    )
    _add(user.household_id, "Sambal")
    _add(user.household_id, "sambal ")
    _add(user.household_id, "Kimchi")
    groups = inventory.list_inventory(user).groups
    assert [g.name for g in groups] == ["Egg", "Kimchi", "Sambal"]
    eggs = groups[0]
    assert (eggs.category, eggs.countable) == ("egg", True)
    assert [b.count for b in eggs.batches] == [2, 6]  # the older batch is first
    assert len(groups[2].batches) == 2


def test_the_demo_kitchen_gets_the_statuses_the_mock_kitchen_showed():
    from seed.demo import seed_demo
    from seed.seed import seed

    seed()
    seed_demo()
    user = _login(UUID(DEV_CLAIMS["sub"]), DEV_CLAIMS["email"])
    by_batch = {(i.display_name, i.count): i for i in _snapshot(user.household_id)}
    expected = {
        ("Egg", 2.0): F.USE_SOON,
        ("Egg", 6.0): F.OK,
        ("Tomato", 3.0): F.OK,
        ("Cabbage", None): F.USE_SOON,
        ("Garlic", None): F.OK,
        ("Chicken thigh", None): F.CHECK,
        ("Firm tofu", 1.0): F.OK,
        ("Rice", None): F.OK,
    }
    assert {key: item.freshness_status for key, item in by_batch.items()} == expected
    assert by_batch[("Rice", None)].remaining_state == "unknown"
    assert by_batch[("Chicken thigh", None)].est_use_first_date < clock.today()
    assert len(inventory.list_inventory(user).groups) == 7  # the two egg batches share a group
