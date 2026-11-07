"""Real Cook/Shop routes, snapshots and atomic confirmation on disposable Postgres."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from app import clock
from app.auth import DEV_CLAIMS
from app.db import models as m
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.main import app
from app.schemas.common import Equipment, LabelDateKind, RemainingState
from app.schemas.cook import (
    ConsumptionLine,
    CookAdjust,
    CookConfirm,
    CookFeedback,
    CookSessionCreate,
    Rating,
)
from app.schemas.identity import PreferencesUpdate
from app.schemas.inventory import InventoryItemCreate, InventoryItemsCreate, InventoryItemUpdate
from app.schemas.shop import BasketConfirm, BoughtLine, ShopAdjust, ShopSessionCreate
from app.services import cook, identity, inventory, shop
from app.services.recommendation_inputs import SqlRecommendationInputs
from seed.seed import seed

RECIPE_ID = UUID("645a8d38-bfae-47f2-b00e-3ca6828a964e")
FEATURES = {"cuisine:chinese", "tag:light", "tag:vegetable_rich"}


@pytest.fixture
def kitchen():
    """Use real seed data, limiting review eligibility to one known complete meal."""
    seed()
    with transaction() as session:
        user = identity.get_or_create_user(session, UUID(DEV_CLAIMS["sub"]), DEV_CLAIMS["email"])
        session.execute(update(m.Recipe).values(reviewed=m.Recipe.id == RECIPE_ID))
    identity.save_preferences(
        user,
        PreferencesUpdate(equipment=list(Equipment), max_cook_minutes=240, max_difficulty=3),
    )
    with transaction() as session:
        catalogue = SqlRecommendationInputs(session).catalogue(user.household_id)
    return user, catalogue


def stock(kitchen):
    user, catalogue = kitchen
    recipe = catalogue.recipes[0]
    items = []
    for line in recipe.ingredients:
        meta = catalogue.ingredients[line.ingredient_id]
        if meta.is_staple:
            continue
        items.append(
            InventoryItemCreate(
                ingredient_id=line.ingredient_id,
                count=line.quantity * 10 if meta.countable else None,
                unit=line.unit if meta.countable else None,
                remaining_state=RemainingState.ENOUGH,
                label_date=clock.today() + timedelta(days=7),
                label_date_kind=LabelDateKind.BEST_BEFORE,
            )
        )
    return inventory.add_items(user, InventoryItemsCreate(items=items), uuid4())


def selected(kitchen):
    user, _ = kitchen
    stock(kitchen)
    suggestion = cook.start_session(user, CookSessionCreate())
    return cook.select(user, suggestion.session_id)


def consumption(record):
    return CookConfirm(
        lines=[
            ConsumptionLine(
                inventory_item_id=line.item.id,
                revision=line.item.revision,
                new_count=line.proposed_count,
                outcome=line.proposed_outcome,
            )
            for line in record.proposed_consumption
        ]
    )


def event_count(kind):
    with transaction() as session:
        return session.scalar(
            select(func.count()).select_from(m.StockEvent).where(m.StockEvent.type == kind)
        )


def weights(user):
    with transaction() as session:
        return dict(session.get(m.Preferences, user.household_id).taste_weights)


def expect_error(code, action):
    with pytest.raises(ApiError) as caught:
        action()
    assert caught.value.code == code


def race(actions):
    barrier = Barrier(len(actions))

    def run(action):
        barrier.wait(timeout=10)
        try:
            return action()
        except ApiError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        futures = [pool.submit(run, action) for action in actions]
        return [future.result(timeout=30) for future in futures]


def purchase(basket, item_id, packs=2):
    return BasketConfirm(
        lines=[
            BoughtLine(
                basket_item_id=item.id,
                bought=item.id == item_id,
                packs=packs if item.id == item_id else None,
            )
            for item in basket.items
        ]
    )


def test_http_suggestion_selection_details_confirmation_and_feedback_use_real_ids(kitchen):
    user, _ = kitchen
    stock(kitchen)
    with TestClient(app) as client:
        started = client.post("/api/cook/sessions", json={"people": 3})
        assert started.status_code == 201, started.text
        suggestion = started.json()
        assert suggestion["recipe"]["id"] == str(RECIPE_ID)
        chosen = client.post(f"/api/cook/sessions/{suggestion['session_id']}/select")
        assert chosen.status_code == 201, chosen.text
        record = chosen.json()
        assert record["recipe"]["id"] == str(RECIPE_ID)
        details = client.get(f"/api/recipes/{record['recipe']['id']}")
        assert details.status_code == 200, details.text
        assert details.json()["ingredients"]
        assert event_count("consume") == 0  # choosing a recipe is not cooking it

        body = {
            "lines": [
                {
                    "inventory_item_id": line["item"]["id"],
                    "revision": line["item"]["revision"],
                    "new_count": line["proposed_count"],
                    "outcome": line["proposed_outcome"],
                }
                for line in record["proposed_consumption"]
            ]
        }
        confirmed = client.post(
            f"/api/cook/records/{record['id']}/confirm",
            json=body,
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert event_count("consume") == 1
        assert weights(user) == dict.fromkeys(FEATURES, 0.0625)
        for rating, value in [("like", 0.25), ("like", 0.25), ("dislike", -0.25), ("maybe", 0)]:
            rated = client.post(
                f"/api/cook/records/{record['id']}/feedback", json={"rating": rating}
            )
            assert rated.status_code == 200, rated.text
            assert weights(user) == (dict.fromkeys(FEATURES, value) if value else {})
    with transaction() as session:
        stored = session.get(m.CookRecord, UUID(record["id"]))
        assert stored.status == "confirmed" and stored.stock_event_id is not None
        assert stored.selection_snapshot and stored.confirmation_snapshot
        assert session.get(m.Preferences, user.household_id).last_cook_people == 3


def test_selection_is_repeatable_and_keeps_original_proposal_after_catalogue_edit(kitchen):
    user, _ = kitchen
    record = selected(kitchen)
    with transaction() as session:
        original = deepcopy(session.get(m.CookRecord, record.id).selection_snapshot)
        recipe = session.get(m.Recipe, RECIPE_ID)
        recipe.title = "Changed after selection"
        recipe.taste_tags = ["rich"]
    assert cook.select(user, record.session_id) == record
    cook.confirm(user, record.id, consumption(record), uuid4())
    cook.give_feedback(user, record.id, CookFeedback(rating=Rating.LIKE))
    assert weights(user) == dict.fromkeys(FEATURES, 0.25)
    with transaction() as session:
        assert session.get(m.CookRecord, record.id).selection_snapshot == original
        assert session.scalar(select(func.count()).select_from(m.CookRecord)) == 1


def test_no_result_keeps_adjustment_and_skip_without_fabricating_history(kitchen):
    user, _ = kitchen
    first = cook.start_session(user, CookSessionCreate())
    expect_error(
        ErrorCode.NO_RESULT,
        lambda: cook.adjust(user, first.session_id, CookAdjust(max_minutes=5)),
    )
    expect_error(
        ErrorCode.NO_RESULT,
        lambda: cook.adjust(user, first.session_id, CookAdjust(people=3)),
    )
    expect_error(ErrorCode.NO_RESULT, lambda: cook.next_suggestion(user, first.session_id))
    with transaction() as session:
        row = session.get(m.PlanSession, first.session_id)
        assert row.shown_recipe_ids == [RECIPE_ID]
        assert row.position == 0
    # A successful read after the failed requests must still enforce the saved limit.
    expect_error(ErrorCode.CONFLICT, lambda: cook.select(user, first.session_id))
    assert not weights(user)


def test_previous_replays_saved_recipe_and_portions_after_catalogue_changes(kitchen):
    user, _ = kitchen
    first = cook.start_session(user, CookSessionCreate(people=2))
    second = cook.adjust(user, first.session_id, CookAdjust(people=3))
    assert second.people == 3 and second.has_previous
    with transaction() as session:
        session.get(m.Recipe, RECIPE_ID).title = "A later catalogue title"
    previous = cook.previous_suggestion(user, first.session_id)
    assert previous.people == 2
    assert previous.recipe.title == first.recipe.title
    assert previous.ingredients == first.ingredients
    assert not previous.has_previous
    with transaction() as session:
        assert session.get(m.Preferences, user.household_id).last_cook_people == 2


def test_same_key_concurrent_confirmation_replays_once_even_after_expiry(kitchen):
    user, _ = kitchen
    record = selected(kitchen)
    body, key = consumption(record), uuid4()
    results = race([lambda: cook.confirm(user, record.id, body, key)] * 4)
    assert all(result == results[0] for result in results)
    assert event_count("consume") == 1
    with transaction() as session:
        session.get(m.PlanSession, record.session_id).expires_at = clock.now() - timedelta(days=1)
        assert session.scalar(select(func.count()).select_from(m.RecommendationConfirmation)) == 1
    assert cook.confirm(user, record.id, body, key) == results[0]
    assert weights(user) == dict.fromkeys(FEATURES, 0.0625)
    cook.give_feedback(user, record.id, CookFeedback(rating=Rating.LIKE))
    assert weights(user) == dict.fromkeys(FEATURES, 0.25)


def test_first_confirmation_of_expired_session_does_not_write_stock(kitchen):
    user, _ = kitchen
    record = selected(kitchen)
    with transaction() as session:
        session.get(m.PlanSession, record.session_id).expires_at = clock.now() - timedelta(
            seconds=1
        )
    expect_error(
        ErrorCode.NOT_FOUND,
        lambda: cook.confirm(user, record.id, consumption(record), uuid4()),
    )
    assert event_count("consume") == 0 and not weights(user)


def test_edited_rating_replays_persisted_evidence_after_weights_saturate(kitchen):
    user, _ = kitchen
    stock(kitchen)
    records = []
    for _ in range(9):
        suggestion = cook.start_session(user, CookSessionCreate())
        record = cook.select(user, suggestion.session_id)
        cook.confirm(user, record.id, consumption(record), uuid4())
        cook.give_feedback(user, record.id, CookFeedback(rating=Rating.LIKE))
        records.append(record)
    assert weights(user) == dict.fromkeys(FEATURES, 2.0)
    cook.give_feedback(user, records[0].id, CookFeedback(rating=Rating.DISLIKE))
    # Replay is -0.25 + eight 0.25 ratings, not 2.0 minus a 0.5 adjustment.
    assert weights(user) == dict.fromkeys(FEATURES, 1.75)


def test_different_keys_cannot_confirm_same_meal_twice(kitchen):
    user, _ = kitchen
    record = selected(kitchen)
    body = consumption(record)
    results = race([lambda: cook.confirm(user, record.id, body, uuid4())] * 3)
    assert results.count(ErrorCode.CONFLICT) == 2
    assert event_count("consume") == 1
    assert weights(user) == dict.fromkeys(FEATURES, 0.0625)


def test_confirmation_rejects_key_reused_with_another_body_or_manual_event(kitchen):
    user, _ = kitchen
    record = selected(kitchen)
    body, key = consumption(record), uuid4()
    inventory.add_items(
        user, InventoryItemsCreate(items=[InventoryItemCreate(display_name="Manual item")]), key
    )
    expect_error(ErrorCode.CONFLICT, lambda: cook.confirm(user, record.id, body, key))
    assert event_count("consume") == 0
    key = uuid4()
    cook.confirm(user, record.id, body, key)
    changed = body.model_copy(deep=True)
    counted = next(line for line in changed.lines if line.new_count is not None)
    counted.new_count -= 1
    expect_error(ErrorCode.CONFLICT, lambda: cook.confirm(user, record.id, changed, key))
    assert event_count("consume") == 1


def test_manual_add_and_cook_confirmation_race_for_one_shared_key(kitchen):
    user, _ = kitchen
    record = selected(kitchen)
    body, key = consumption(record), uuid4()
    results = race(
        [
            lambda: inventory.add_items(
                user,
                InventoryItemsCreate(items=[InventoryItemCreate(display_name="Concurrent item")]),
                key,
            ),
            lambda: cook.confirm(user, record.id, body, key),
        ]
    )
    assert results.count(ErrorCode.CONFLICT) == 1
    with transaction() as session:
        events = list(
            session.scalars(
                select(m.StockEvent).where(
                    m.StockEvent.household_id == user.household_id,
                    m.StockEvent.idempotency_key == key,
                )
            )
        )
        assert len(events) == 1
        stored = session.get(m.CookRecord, record.id)
        replay = session.get(m.RecommendationConfirmation, (user.household_id, key))
        if results[1] == ErrorCode.CONFLICT:
            assert events[0].id == results[0].event.id
            assert events[0].ref_type == "manual"
            assert stored.status == "selected" and stored.stock_event_id is None
            assert replay is None
            assert session.get(m.RecommendationLearning, user.household_id) is None
            assert not session.get(m.Preferences, user.household_id).taste_weights
            for proposal in record.proposed_consumption:
                batch = session.get(m.InventoryItem, proposal.item.id)
                assert batch.revision == proposal.item.revision
                assert batch.count == proposal.item.count
        else:
            assert events[0].id == results[1].event.id
            assert events[0].type == "consume"
            assert stored.status == "confirmed" and stored.stock_event_id == events[0].id
            assert replay.stock_event_id == events[0].id
            assert session.get(m.Preferences, user.household_id).taste_weights == dict.fromkeys(
                FEATURES, 0.0625
            )
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(m.InventoryItem)
                    .where(m.InventoryItem.display_name == "Concurrent item")
                )
                == 0
            )


def test_retry_after_later_stock_edit_and_feedback_replays_original_response(kitchen):
    user, _ = kitchen
    record = selected(kitchen)
    body, key = consumption(record), uuid4()
    original = cook.confirm(user, record.id, body, key)
    original_json = original.model_dump(mode="json")
    batch = next(item for item in original.items if item.countable)
    edited = inventory.update_item(
        user, batch.id, InventoryItemUpdate(revision=batch.revision, count=batch.count + 2), uuid4()
    ).items[0]
    cook.give_feedback(user, record.id, CookFeedback(rating=Rating.LIKE))
    with transaction() as session:
        evidence = deepcopy(session.get(m.RecommendationLearning, user.household_id).state)
        feedback_count = session.scalar(select(func.count()).select_from(m.RecipeFeedback))

    replay = cook.confirm(user, record.id, body, key)
    assert replay.model_dump(mode="json") == original_json
    replayed_batch = next(item for item in replay.items if item.id == batch.id)
    assert replayed_batch.count != edited.count and replayed_batch.revision != edited.revision
    assert event_count("consume") == 1 and event_count("adjust") == 1
    with transaction() as session:
        current = session.get(m.InventoryItem, batch.id)
        assert current.count == edited.count and current.revision == edited.revision
        assert session.get(m.RecommendationLearning, user.household_id).state == evidence
        assert session.scalar(select(func.count()).select_from(m.RecipeFeedback)) == feedback_count
        assert session.scalar(select(func.count()).select_from(m.RecommendationConfirmation)) == 1
    assert weights(user) == dict.fromkeys(FEATURES, 0.25)


def test_failure_after_stock_write_rolls_back_record_inventory_learning_and_replay(
    kitchen, monkeypatch
):
    from app.services.recommendation_sql import SqlRecommendationRepository

    user, _ = kitchen
    record = selected(kitchen)
    body, key = consumption(record), uuid4()
    before = inventory.list_inventory(user).model_dump(mode="json")

    def fail(*args, **kwargs):
        raise RuntimeError("injected after stock application")

    with monkeypatch.context() as patch:
        patch.setattr(SqlRecommendationRepository, "save_confirmation", fail)
        with pytest.raises(RuntimeError, match="injected"):
            cook.confirm(user, record.id, body, key)
    assert inventory.list_inventory(user).model_dump(mode="json") == before
    assert event_count("consume") == 0 and not weights(user)
    with transaction() as session:
        assert session.get(m.CookRecord, record.id).status == "selected"
        assert session.scalar(select(func.count()).select_from(m.RecommendationConfirmation)) == 0
    cook.confirm(user, record.id, body, key)
    assert event_count("consume") == 1


def test_stale_inventory_revision_does_not_confirm_or_train(kitchen):
    user, _ = kitchen
    record = selected(kitchen)
    batch = next(line.item for line in record.proposed_consumption if line.item.countable)
    inventory.update_item(
        user, batch.id, InventoryItemUpdate(revision=batch.revision, count=batch.count + 1), uuid4()
    )
    expect_error(
        ErrorCode.STALE_REVISION,
        lambda: cook.confirm(user, record.id, consumption(record), uuid4()),
    )
    assert event_count("consume") == 0 and not weights(user)


@pytest.mark.parametrize("operation", ["next", "select", "confirm", "feedback"])
def test_other_household_cannot_access_cook_state(kitchen, operation):
    user, _ = kitchen
    record = selected(kitchen)
    with transaction() as session:
        stranger = identity.get_or_create_user(session, uuid4(), "stranger@example.test")
    actions = {
        "next": lambda: cook.next_suggestion(stranger, record.session_id),
        "select": lambda: cook.select(stranger, record.session_id),
        "confirm": lambda: cook.confirm(stranger, record.id, consumption(record), uuid4()),
        "feedback": lambda: cook.give_feedback(
            stranger, record.id, CookFeedback(rating=Rating.LIKE)
        ),
    }
    expect_error(ErrorCode.NOT_FOUND, actions[operation])
    assert event_count("consume") == 0 and not weights(user)


def test_shop_confirmation_uses_saved_pack_conversion_and_replays(kitchen):
    user, catalogue = kitchen
    basket = shop.start_session(user, ShopSessionCreate(meals=1))
    assert basket.planned_meals[0].id == RECIPE_ID
    item = next(
        item
        for item in basket.items
        if catalogue.ingredients[item.ingredient_id].canonical_name == "egg"
    )
    original = catalogue.purchases[item.ingredient_id]
    with transaction() as session:
        ingredient = session.get(m.Ingredient, item.ingredient_id)
        ingredient.purchase_unit_size = 99
        before = deepcopy(session.get(m.Basket, basket.id).planning_snapshot)
    body, key = purchase(basket, item.id), uuid4()
    result = shop.confirm_basket(user, basket.id, body, key)
    assert len(result.items) == 1
    assert result.items[0].count == 2 * original.purchase_unit_size
    assert result.items[0].unit == original.purchase_unit_measure
    assert shop.confirm_basket(user, basket.id, body, key) == result
    assert event_count("purchase") == 1
    assert not weights(user)
    with transaction() as session:
        row = session.get(m.Basket, basket.id)
        assert row.status == "confirmed" and row.stock_event_id == result.event.id
        assert row.planning_snapshot == before
        line = session.get(m.BasketItem, item.id)
        assert line.actual_bought and line.actual_packs == 2


def test_shop_adjust_abandons_old_basket_and_rejects_other_household(kitchen):
    user, _ = kitchen
    first = shop.start_session(user, ShopSessionCreate(meals=1))
    second = shop.adjust(user, first.session_id, ShopAdjust(people=3))
    assert second.id != first.id and second.people == 3
    with transaction() as session:
        stranger = identity.get_or_create_user(session, uuid4(), "shop-stranger@example.test")
        assert session.get(m.Basket, first.id).status == "abandoned"
        assert session.get(m.Preferences, user.household_id).last_shop_people == 3
    body = BasketConfirm(
        lines=[BoughtLine(basket_item_id=item.id, bought=False) for item in first.items]
    )
    expect_error(ErrorCode.CONFLICT, lambda: shop.confirm_basket(user, first.id, body, uuid4()))
    expect_error(
        ErrorCode.NOT_FOUND, lambda: shop.adjust(stranger, first.session_id, ShopAdjust(people=2))
    )
    expect_error(
        ErrorCode.NOT_FOUND, lambda: shop.confirm_basket(stranger, first.id, body, uuid4())
    )
    assert event_count("purchase") == 0


def test_legacy_weights_without_evidence_are_not_silently_reset(kitchen):
    user, _ = kitchen
    with transaction() as session:
        session.get(m.Preferences, user.household_id).taste_weights = {"cuisine:chinese": 0.75}
    expect_error(ErrorCode.CONFLICT, lambda: cook.start_session(user, CookSessionCreate()))
    assert weights(user) == {"cuisine:chinese": 0.75}
    with transaction() as session:
        assert session.scalar(select(func.count()).select_from(m.PlanSession)) == 0
