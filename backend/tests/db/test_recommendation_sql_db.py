"""Cook/Shop HTTP and transactional behavior on PostgreSQL, not a fake repository."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import clock
from app.auth import get_current_user
from app.db import models as m
from app.db.session import transaction
from app.errors import ApiError, ErrorCode
from app.main import app
from app.schemas.cook import CookAdjust, CookConfirm, CookFeedback, CookSessionCreate
from app.schemas.shop import BasketConfirm, ShopSessionCreate
from app.schemas.stock_events import StockEventType
from app.services import cook, shop
from app.services.identity import get_or_create_user
from app.services.recommendation_sql import SqlRecommendationRepository
from app.services.stock_events import apply_stock_event


@pytest.fixture
def kitchen():
    with transaction() as s:
        user = get_or_create_user(s, uuid4(), "reco@example.test")
        s.add(
            m.Preferences(
                household_id=user.household_id,
                equipment=["stove"],
                max_cook_minutes=40,
                household_size=2,
            )
        )
        ingredient = m.Ingredient(
            id=uuid4(),
            canonical_name="egg",
            category="egg",
            countable=True,
            default_unit="pcs",
            default_storage="fridge",
            is_staple=False,
            allergen_tags=["egg"],
            diet_flags=["vegetarian"],
            shelf_life_days_fridge=21,
            purchase_unit="box",
            purchase_unit_size=6,
            purchase_unit_measure="pcs",
        )
        s.add(ingredient)
        recipe_ids = [uuid4(), uuid4()]
        for recipe_id in recipe_ids:
            s.add(
                m.Recipe(
                    id=recipe_id,
                    title="Egg meal",
                    cuisine="chinese",
                    total_minutes=20,
                    active_minutes=10,
                    difficulty=1,
                    servings=2,
                    equipment=["stove"],
                    taste_tags=["low_oil"],
                    diet_flags=["vegetarian"],
                    allergens=["egg"],
                    reviewed=True,
                    steps=["Cook the eggs."],
                )
            )
        s.flush()
        for recipe_id in recipe_ids:
            s.add(
                m.RecipeIngredient(
                    recipe_id=recipe_id,
                    ingredient_id=ingredient.id,
                    quantity=3,
                    unit="pcs",
                    essential=True,
                )
            )
        batch = m.InventoryItem(
            id=uuid4(),
            household_id=user.household_id,
            ingredient_id=ingredient.id,
            display_name="Egg",
            count=10,
            unit="pcs",
            remaining_state="enough",
            storage="fridge",
            source="manual",
            acquired_at=clock.today(),
            label_date=clock.today() + timedelta(days=2),
            label_date_kind="use_by",
            last_confirmed_at=clock.now(),
        )
        s.add(batch)
        s.flush()
        return user, ingredient.id, batch.id, recipe_ids


def selected(user):
    suggestion = cook.start_session(user, CookSessionCreate())
    return cook.select(user, suggestion.session_id)


def consumption(record):
    return CookConfirm(
        lines=[
            dict(
                inventory_item_id=line.item.id,
                revision=line.item.revision,
                new_count=line.proposed_count,
            )
            for line in record.proposed_consumption
        ]
    )


def basket_request(basket, bought=False):
    return BasketConfirm(
        lines=[dict(basket_item_id=line.id, bought=bought) for line in basket.items]
    )


def count(model):
    with transaction() as s:
        return s.scalar(select(func.count()).select_from(model))


def stock(batch_id):
    with transaction() as s:
        return s.get(m.InventoryItem, batch_id).count


def test_http_cook_navigation_confirmation_feedback_and_recipe_star(kitchen):
    user, _, batch_id, _ = kitchen
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app)
        response = client.post("/api/cook/sessions", json={})
        assert response.status_code == 201, response.text
        first = response.json()
        prefix = f"/api/cook/sessions/{first['session_id']}"
        assert client.post(prefix + "/next").status_code == 200
        assert client.post(prefix + "/previous").json()["recipe"]["id"] == first["recipe"]["id"]
        assert client.post(prefix + "/adjust", json={"max_minutes": 30}).status_code == 200
        response = client.post(prefix + "/select")
        assert response.status_code == 201, response.text
        record = response.json()
        assert client.post(prefix + "/select").json() == record
        lines = [
            dict(
                inventory_item_id=line["item"]["id"],
                revision=line["item"]["revision"],
                new_count=line["proposed_count"],
            )
            for line in record["proposed_consumption"]
        ]
        path = f"/api/cook/records/{record['id']}"
        key = {"Idempotency-Key": str(uuid4())}
        response = client.post(path + "/confirm", json={"lines": lines}, headers=key)
        assert response.status_code == 200, response.text
        assert (
            client.post(path + "/confirm", json={"lines": lines}, headers=key).json()
            == response.json()
        )
        assert stock(batch_id) == 7
        assert client.post(path + "/feedback", json={"rating": "like"}).json()["rating"] == "like"
        assert client.post(path + "/feedback", json={"rating": "dislike"}).status_code == 200
        recipe_path = f"/api/recipes/{record['recipe']['id']}"
        assert client.put(recipe_path + "/star", json={"starred": True}).status_code == 200
        assert client.get(recipe_path).json()["starred"]
        assert client.put(recipe_path + "/star", json={"starred": False}).status_code == 200
        assert not client.get(recipe_path).json()["starred"]
        assert client.get("/api/use-first").json()["items"]
    finally:
        app.dependency_overrides.clear()


def test_http_shop_adjust_confirm_and_exact_replay(kitchen):
    user, _, batch_id, _ = kitchen
    with transaction() as s:
        s.get(m.InventoryItem, batch_id).remaining_state = "out"
        s.get(m.InventoryItem, batch_id).count = 0
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        client = TestClient(app)
        response = client.post("/api/shop/sessions", json={"meals": 1})
        assert response.status_code == 201, response.text
        old = response.json()
        response = client.post(f"/api/shop/sessions/{old['session_id']}/adjust", json={"meals": 2})
        assert response.status_code == 200, response.text
        basket = response.json()
        assert basket["id"] != old["id"]
        key = {"Idempotency-Key": str(uuid4())}
        old_request = {
            "lines": [dict(basket_item_id=line["id"], bought=True) for line in old["items"]]
        }
        assert (
            client.post(
                f"/api/shop/baskets/{old['id']}/confirm", json=old_request, headers=key
            ).status_code
            == 409
        )
        body = {"lines": [dict(basket_item_id=line["id"], bought=True) for line in basket["items"]]}
        path = f"/api/shop/baskets/{basket['id']}/confirm"
        response = client.post(path, json=body, headers=key)
        assert response.status_code == 200, response.text
        assert client.post(path, json=body, headers=key).json() == response.json()
        assert count(m.StockEvent) == 1
        assert count(m.InventoryItem) == 2
    finally:
        app.dependency_overrides.clear()


def test_confirmed_response_survives_later_edits_and_expiry(kitchen):
    user, _, batch_id, _ = kitchen
    record = selected(user)
    body, key = consumption(record), uuid4()
    response = cook.confirm(user, record.id, body, key)
    with transaction() as s:
        s.get(m.InventoryItem, batch_id).count = 99
        s.get(m.PlanSession, record.session_id).expires_at = clock.now() - timedelta(days=1)
    assert cook.confirm(user, record.id, body, key) == response
    assert stock(batch_id) == 99
    changed = body.model_copy(deep=True)
    changed.lines[0].new_count = 2
    with pytest.raises(ApiError) as error:
        cook.confirm(user, record.id, changed, key)
    assert error.value.code == ErrorCode.CONFLICT


def test_failure_after_stock_event_rolls_back_all_effects(kitchen, monkeypatch):
    user, _, batch_id, _ = kitchen
    record = selected(user)

    def broken(*args):
        raise RuntimeError("injected response failure")

    monkeypatch.setattr(SqlRecommendationRepository, "save_confirmation", broken)
    with pytest.raises(RuntimeError, match="injected"):
        cook.confirm(user, record.id, consumption(record), uuid4())
    assert stock(batch_id) == 10
    assert count(m.StockEvent) == count(m.RecommendationLearning) == count(m.RecipeFeedback) == 0
    with transaction() as s:
        assert s.get(m.CookRecord, record.id).status == "selected"


def test_stale_revision_rejects_confirmation(kitchen):
    user, _, batch_id, _ = kitchen
    record = selected(user)
    with transaction() as s:
        s.get(m.InventoryItem, batch_id).revision += 1
    with pytest.raises(ApiError) as error:
        cook.confirm(user, record.id, consumption(record), uuid4())
    assert error.value.code == ErrorCode.STALE_REVISION
    assert count(m.StockEvent) == 0


def test_changed_ratings_replace_evidence_and_do_not_overwrite_preferences(kitchen):
    user, _, _, _ = kitchen
    record = selected(user)
    cook.confirm(user, record.id, consumption(record), uuid4())
    for rating in ["like", "like", "dislike", "maybe"]:
        cook.give_feedback(user, record.id, CookFeedback(rating=rating))
    with transaction() as s:
        repo = SqlRecommendationRepository(s)
        evidence = repo.learning(user.household_id)
        assert len(evidence.meals) == 1
        assert evidence.meals[0].rating == "maybe"
        prefs = s.get(m.Preferences, user.household_id)
        assert prefs.taste_weights == {}
        assert prefs.equipment == ["stove"]
    assert count(m.RecipeFeedback) == 4  # cooked, like, dislike, maybe; duplicate like omitted


def test_concurrent_confirmation_is_exactly_once(kitchen):
    user, _, batch_id, _ = kitchen
    record = selected(user)
    body, key = consumption(record), uuid4()
    gate = Barrier(2)

    def confirm():
        gate.wait(timeout=10)
        return cook.confirm(user, record.id, body, key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: confirm(), range(2)))
    assert first == second
    assert stock(batch_id) == 7
    assert count(m.StockEvent) == count(m.RecommendationConfirmation) == 1
    assert count(m.RecipeFeedback) == 1


def test_different_keys_cannot_confirm_same_record_twice(kitchen):
    user, _, batch_id, _ = kitchen
    record = selected(user)
    gate = Barrier(2)

    def confirm():
        gate.wait(timeout=10)
        try:
            cook.confirm(user, record.id, consumption(record), uuid4())
            return "ok"
        except ApiError as error:
            return error.code.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: confirm(), range(2)))
    assert sorted(results) == ["CONFLICT", "ok"]
    assert stock(batch_id) == 7


def test_selection_is_serialized_and_foreign_household_cannot_read_session(kitchen):
    user, _, _, _ = kitchen
    suggestion = cook.start_session(user, CookSessionCreate())
    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(lambda _: cook.select(user, suggestion.session_id), range(2)))
    assert records[0] == records[1]
    assert count(m.CookRecord) == 1
    with transaction() as s:
        other = get_or_create_user(s, uuid4(), "stranger@example.test")
    with pytest.raises(ApiError) as error:
        cook.select(other, suggestion.session_id)
    assert error.value.code == ErrorCode.NOT_FOUND


def test_selection_keeps_recipe_features_after_catalogue_changes(kitchen):
    user, _, _, _ = kitchen
    record = selected(user)
    with transaction() as s:
        recipe = s.get(m.Recipe, record.recipe.id)
        recipe.title = "Edited title"
        recipe.taste_tags = ["high_protein"]
    cook.confirm(user, record.id, consumption(record), uuid4())
    rated = cook.give_feedback(user, record.id, CookFeedback(rating="like"))
    assert rated.recipe.title == "Egg meal"
    with transaction() as s:
        assert s.get(m.Preferences, user.household_id).taste_weights == {
            "tag:low_oil": 0.25,
            "cuisine:chinese": 0.25,
        }


def test_basket_keeps_original_pack_conversion(kitchen):
    user, ingredient_id, batch_id, _ = kitchen
    with transaction() as s:
        s.get(m.InventoryItem, batch_id).count = 0
        s.get(m.InventoryItem, batch_id).remaining_state = "out"
    basket = shop.start_session(user, ShopSessionCreate(meals=1))
    with transaction() as s:
        s.get(m.Ingredient, ingredient_id).purchase_unit_size = 100
    result = shop.confirm_basket(user, basket.id, basket_request(basket, True), uuid4())
    assert result.items[0].count == 6


def test_empty_consumption_and_no_result_are_persisted_correctly(kitchen):
    user, _, _, _ = kitchen
    suggestion = cook.start_session(user, CookSessionCreate())
    with pytest.raises(ApiError) as error:
        cook.adjust(user, suggestion.session_id, CookAdjust(max_minutes=5))
    assert error.value.code == ErrorCode.NO_RESULT
    assert "max_minutes" in error.value.details["relaxable"]
    with transaction() as s:
        assert (
            SqlRecommendationRepository(s)
            .cook_session(user.household_id, suggestion.session_id)
            .state.max_minutes
            == 5
        )
    record = selected(user)
    body = CookConfirm(
        lines=[
            dict(inventory_item_id=line.item.id, revision=line.item.revision, outcome="not_used")
            for line in record.proposed_consumption
        ]
    )
    cook.confirm(user, record.id, body, uuid4())
    assert count(m.StockEvent) == 1
    assert count(m.StockEventLine) == 0


def test_manual_stock_write_can_finish_while_recommendation_holds_household_lock(kitchen):
    user, _, _, _ = kitchen
    # A manual event needs a FK KEY SHARE lock on this same household. Using
    # FOR UPDATE for the Role 5 lock would block it and can deadlock on keys.
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction() as s:
            SqlRecommendationRepository(s).lock(user.household_id)

            def manual():
                with transaction() as other:
                    return apply_stock_event(other, user, StockEventType.ADJUST, [], uuid4())

            future = pool.submit(manual)
            assert future.result(timeout=10).event.id is not None


def test_manual_event_wins_key_race_without_partial_cooking(kitchen, monkeypatch):
    user, _, batch_id, _ = kitchen
    record = selected(user)
    key, reached = uuid4(), Event()
    original = SqlRecommendationRepository.apply_stock

    def observed(self, *args):
        reached.set()
        return original(self, *args)

    monkeypatch.setattr(SqlRecommendationRepository, "apply_stock", observed)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction() as s:
            apply_stock_event(s, user, StockEventType.ADJUST, [], key)
            future = pool.submit(cook.confirm, user, record.id, consumption(record), key)
            assert reached.wait(timeout=10)
            # Commit the previously invisible manual event while Cook waits.
        with pytest.raises(ApiError) as error:
            future.result(timeout=10)
    assert error.value.code == ErrorCode.CONFLICT
    assert stock(batch_id) == 10
    assert count(m.StockEvent) == 1
    assert count(m.RecommendationConfirmation) == count(m.RecommendationLearning) == 0


def test_legacy_sessions_and_weights_are_not_silently_reconstructed(kitchen):
    user, _, _, _ = kitchen
    first = cook.start_session(user, CookSessionCreate())
    with transaction() as s:
        s.get(m.PlanSession, first.session_id).recommendation_state = None
    with pytest.raises(ApiError) as error:
        cook.next_suggestion(user, first.session_id)
    assert error.value.code == ErrorCode.CONFLICT
    with transaction() as s:
        s.get(m.Preferences, user.household_id).taste_weights = {"tag:low_oil": 1.5}
    with pytest.raises(ApiError, match="migration review"):
        cook.start_session(user, CookSessionCreate())
    with transaction() as s:
        assert s.get(m.Preferences, user.household_id).taste_weights == {"tag:low_oil": 1.5}


def test_concurrent_feedback_replacement_does_not_add_training_samples(kitchen):
    user, _, _, _ = kitchen
    record = selected(user)
    cook.confirm(user, record.id, consumption(record), uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(
            pool.map(
                lambda rating: cook.give_feedback(user, record.id, CookFeedback(rating=rating)),
                ["like", "dislike"],
            )
        )
    with transaction() as s:
        evidence = SqlRecommendationRepository(s).learning(user.household_id)
        assert len(evidence.meals) == 1
        value = 0.25 if evidence.meals[0].rating == "like" else -0.25
        assert s.get(m.Preferences, user.household_id).taste_weights == {
            "cuisine:chinese": value,
            "tag:low_oil": value,
        }


def test_new_migration_matches_declared_models(database):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.db.session import engine

    with engine().connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), m.Base.metadata)
    assert differences == []
