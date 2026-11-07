"""Service orchestration tests using a transactional double, not Postgres."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from itertools import count

import pytest

from app.auth import CurrentUser
from app.errors import ApiError, ErrorCode
from app.reco import taste_weights
from app.schemas.common import Allergen, FreshnessStatus, ItemSource, RemainingState
from app.schemas.cook import (
    ConsumptionLine,
    ConsumptionOutcome,
    CookAdjust,
    CookConfirm,
    CookFeedback,
    CookRecordStatus,
    CookSessionCreate,
    CookTag,
    Rating,
)
from app.schemas.shop import (
    BasketConfirm,
    BasketStatus,
    BoughtLine,
    ShopAdjust,
    ShopSessionCreate,
    ShopTag,
)
from app.services.recommendation_workflow import RecommendationWorkflow
from tests.reco_fixtures import NOW, batch, prefs, recipe, uid
from tests.recommendation_repository_fake import HOUSEHOLD, OTHER, FakeDatabase, set_recipes

USER = CurrentUser(uid("workflow-user"), HOUSEHOLD, "fixture@example.test")
STRANGER = CurrentUser(uid("workflow-stranger"), OTHER, "other@example.test")


@pytest.fixture
def setup():
    database = FakeDatabase()
    time = [NOW]
    ids = count()
    service = RecommendationWorkflow(
        database.transaction, now=lambda: time[0], new_id=lambda: uid(f"workflow/{next(ids)}")
    )
    return database, service, time


def selected(service):
    suggestion = service.start_cook(USER, CookSessionCreate())
    return service.select_cook(USER, suggestion.session_id)


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


def shopping(service):
    return service.start_shop(USER, ShopSessionCreate(meals=1))


def bought(basket, *, packs=None, purchase=True):
    return BasketConfirm(
        lines=[
            BoughtLine(basket_item_id=item.id, bought=purchase, packs=packs)
            for item in basket.items
        ]
    )


def assert_error(code, fn):
    with pytest.raises(ApiError) as error:
        fn()
    assert error.value.code == code
    return error.value


def test_cook_history_previous_and_next_preserve_constraints_and_do_not_train(setup):
    db, service, _ = setup
    first = service.start_cook(USER, CookSessionCreate(people=3))
    second = service.next_cook(USER, first.session_id)
    assert second.recipe.id != first.recipe.id
    previous = service.previous_cook(USER, first.session_id)
    assert previous.recipe.id == first.recipe.id
    assert not previous.has_previous
    assert_error(ErrorCode.CONFLICT, lambda: service.previous_cook(USER, first.session_id))
    third = service.next_cook(USER, first.session_id)
    assert third.has_previous
    assert len(db.state["cook_sessions"][HOUSEHOLD, first.session_id].history) == 3
    assert db.state["prefs"][HOUSEHOLD].last_cook_people == 3
    assert not taste_weights(db.state["learning"][HOUSEHOLD])


def test_previous_restores_displayed_people_without_loosening_adjustments(setup):
    db, service, _ = setup
    set_recipes(db, recipe("slow", starred=True), recipe("fast", total_minutes=20))
    first = service.start_cook(USER, CookSessionCreate(people=2))
    service.adjust_cook(USER, first.session_id, CookAdjust(people=4, tags=[CookTag.QUICKER]))
    previous = service.previous_cook(USER, first.session_id)
    assert previous.people == 2
    assert previous.applied_constraints.max_minutes == 20
    assert db.state["prefs"][HOUSEHOLD].last_cook_people == 2
    assert_error(ErrorCode.CONFLICT, lambda: service.select_cook(USER, first.session_id))


def test_no_result_does_not_save_half_a_session_or_preferences(setup):
    db, service, _ = setup
    db.state["prefs"][HOUSEHOLD] = prefs(allergens=[Allergen.EGG])
    before = deepcopy(db.state)
    error = assert_error(
        ErrorCode.NO_RESULT, lambda: service.start_cook(USER, CookSessionCreate(people=4))
    )
    assert error.details == {"relaxable": []}
    assert db.state == before


def test_no_result_retains_requested_adjustments_without_adding_history(setup):
    db, service, _ = setup
    suggestion = service.start_cook(USER, CookSessionCreate())
    before = deepcopy(db.state["cook_sessions"][HOUSEHOLD, suggestion.session_id])
    assert_error(
        ErrorCode.NO_RESULT,
        lambda: service.adjust_cook(USER, suggestion.session_id, CookAdjust(max_minutes=5)),
    )
    saved = db.state["cook_sessions"][HOUSEHOLD, suggestion.session_id]
    assert saved.state.max_minutes == 5
    assert saved.history == before.history
    assert saved.position == before.position
    assert_error(ErrorCode.NO_RESULT, lambda: service.next_cook(USER, suggestion.session_id))
    assert db.state["cook_sessions"][HOUSEHOLD, suggestion.session_id].state.max_minutes == 5
    assert (
        suggestion.recipe.id
        in db.state["cook_sessions"][HOUSEHOLD, suggestion.session_id].state.skipped_recipe_ids
    )


def test_selection_splits_counted_consumption_in_expiry_order_and_is_repeatable(setup):
    db, service, _ = setup
    db.state["inventory"][HOUSEHOLD] = [
        batch(key="later", count=5, est_use_first_date=NOW.date() + timedelta(days=4)),
        batch(key="first", count=2, est_use_first_date=NOW.date() + timedelta(days=1)),
    ]
    record = selected(service)
    assert [line.item.id for line in record.proposed_consumption] == [
        uid("batch/egg/first"),
        uid("batch/egg/later"),
    ]
    assert [line.proposed_count for line in record.proposed_consumption] == [0, 4]
    assert service.select_cook(USER, record.session_id) == record
    assert len(db.state["cook_records"]) == 1
    assert_error(ErrorCode.CONFLICT, lambda: service.next_cook(USER, record.session_id))
    assert not db.state["events"]


@pytest.mark.parametrize(
    "stock",
    [
        [],
        [batch(count=None)],
        [batch(count=10, remaining_state=RemainingState.UNKNOWN)],
        [batch(count=1)],
        [batch(freshness_status=FreshnessStatus.CHECK)],
        [batch(freshness_status=FreshnessStatus.EXPIRED)],
    ],
)
def test_selection_requires_essential_stock_to_be_resolved(setup, stock):
    db, service, _ = setup
    db.state["inventory"][HOUSEHOLD] = stock
    suggestion = service.start_cook(USER, CookSessionCreate())
    assert_error(ErrorCode.CONFLICT, lambda: service.select_cook(USER, suggestion.session_id))
    assert not db.state["cook_records"]


def test_selection_rechecks_new_household_allergens(setup):
    db, service, _ = setup
    suggestion = service.start_cook(USER, CookSessionCreate())
    db.state["prefs"][HOUSEHOLD] = prefs(allergens=[Allergen.EGG])
    assert_error(ErrorCode.CONFLICT, lambda: service.select_cook(USER, suggestion.session_id))


def test_confirm_cook_updates_stock_record_and_provisional_learning_then_replays(setup):
    db, service, time = setup
    record = selected(service)
    body, key = consumption(record), uid("cook-key")
    result = service.confirm_cook(USER, record.id, body, key)
    assert result.items[0].count == 7
    assert result.items[0].revision == 2
    assert result.event.ref_id == record.id
    assert (
        db.state["cook_records"][HOUSEHOLD, record.id].response.status == CookRecordStatus.CONFIRMED
    )
    assert taste_weights(db.state["learning"][HOUSEHOLD]) == {"cuisine:chinese": 0.0625}
    time[0] += timedelta(days=2)
    assert service.confirm_cook(USER, record.id, body, key) == result
    assert db.stock_attempts == 1
    assert len(db.state["events"]) == 1


def test_cook_same_key_different_body_and_different_key_same_record_are_rejected(setup):
    db, service, _ = setup
    record = selected(service)
    body, key = consumption(record), uid("key")
    service.confirm_cook(USER, record.id, body, key)
    changed = body.model_copy(deep=True)
    changed.lines[0].new_count = 5
    assert_error(ErrorCode.CONFLICT, lambda: service.confirm_cook(USER, record.id, changed, key))
    assert_error(
        ErrorCode.CONFLICT, lambda: service.confirm_cook(USER, record.id, body, uid("new"))
    )
    assert db.stock_attempts == 1


@pytest.mark.parametrize("failure", ["save_learning", "save_confirmation"])
def test_failure_after_stock_application_rolls_back_everything(setup, failure):
    db, service, _ = setup
    record = selected(service)
    before = deepcopy(db.state)
    db.fail_on = failure
    with pytest.raises(RuntimeError, match="simulated"):
        service.confirm_cook(USER, record.id, consumption(record), uid("rollback-key"))
    assert db.stock_attempts == 1
    assert db.state == before
    db.fail_on = None
    result = service.confirm_cook(USER, record.id, consumption(record), uid("rollback-key"))
    assert result.items[0].count == 7


def test_stale_revision_rejects_without_training_or_stock_event(setup):
    db, service, _ = setup
    record = selected(service)
    db.state["inventory"][HOUSEHOLD][0].revision += 1
    assert_error(
        ErrorCode.STALE_REVISION,
        lambda: service.confirm_cook(USER, record.id, consumption(record), uid("stale")),
    )
    assert db.stock_attempts == 0
    assert not taste_weights(db.state["learning"][HOUSEHOLD])


@pytest.mark.parametrize(
    "change, code",
    [
        ("duplicate", ErrorCode.VALIDATION),
        ("extra", ErrorCode.VALIDATION),
        ("missing", ErrorCode.VALIDATION),
        ("increase", ErrorCode.VALIDATION),
        ("infinite", ErrorCode.VALIDATION),
        ("wrong_mode", ErrorCode.VALIDATION),
    ],
)
def test_invalid_cook_confirmation_never_reaches_stock_writer(setup, change, code):
    db, service, _ = setup
    record = selected(service)
    body = consumption(record)
    if change == "duplicate":
        body.lines.append(body.lines[0].model_copy())
    elif change == "extra":
        body.lines.append(body.lines[0].model_copy(update={"inventory_item_id": uid("foreign")}))
    elif change == "missing":
        body.lines.clear()
    elif change == "wrong_mode":
        body.lines[0] = ConsumptionLine(
            inventory_item_id=body.lines[0].inventory_item_id,
            revision=1,
            outcome=ConsumptionOutcome.USED_UP,
        )
    else:
        body.lines[0].new_count = float("inf") if change == "infinite" else 11
    assert_error(code, lambda: service.confirm_cook(USER, record.id, body, uid("invalid")))
    assert db.stock_attempts == 0


@pytest.mark.parametrize("changed", ["freshness", "units", "allergens"])
def test_confirm_rechecks_changed_freshness_units_and_allergens(setup, changed):
    db, service, _ = setup
    record = selected(service)
    if changed == "freshness":
        db.state["inventory"][HOUSEHOLD][0].freshness_status = FreshnessStatus.EXPIRED
    elif changed == "units":
        db.state["inventory"][HOUSEHOLD][0].unit = "g"
    else:
        db.state["prefs"][HOUSEHOLD] = prefs(allergens=[Allergen.EGG])
    assert_error(
        ErrorCode.CONFLICT,
        lambda: service.confirm_cook(USER, record.id, consumption(record), uid("changed")),
    )
    assert not db.state["events"]


def test_not_used_leaves_batch_untouched_and_state_outcomes_do_not_invent_counts(setup):
    db, service, _ = setup
    set_recipes(db, recipe(ingredients=("egg", "tomato")))
    db.state["inventory"][HOUSEHOLD] = [batch(count=10), batch("tomato")]
    record = selected(service)
    body = consumption(record)
    for line in body.lines:
        if line.inventory_item_id == uid("batch/egg/one"):
            line.new_count, line.outcome = None, ConsumptionOutcome.NOT_USED
        else:
            line.outcome = ConsumptionOutcome.USED_UP
    result = service.confirm_cook(USER, record.id, body, uid("state"))
    assert len(result.items) == 1
    assert result.items[0].count is None
    assert result.items[0].remaining_state == RemainingState.OUT
    assert next(item for item in db.state["inventory"][HOUSEHOLD] if item.countable).count == 10


def test_feedback_requires_confirmation_and_replaces_reward_even_after_session_expiry(setup):
    db, service, time = setup
    record = selected(service)
    assert_error(
        ErrorCode.CONFLICT,
        lambda: service.feedback(USER, record.id, CookFeedback(rating=Rating.LIKE)),
    )
    service.confirm_cook(USER, record.id, consumption(record), uid("confirm"))
    time[0] += timedelta(days=10)
    result = service.feedback(USER, record.id, CookFeedback(rating=Rating.LIKE))
    assert result.rating == Rating.LIKE
    assert taste_weights(db.state["learning"][HOUSEHOLD]) == {"cuisine:chinese": 0.25}
    service.feedback(USER, record.id, CookFeedback(rating=Rating.LIKE))
    assert len(db.state["learning"][HOUSEHOLD].meals) == 1
    service.feedback(USER, record.id, CookFeedback(rating=Rating.MAYBE))
    assert taste_weights(db.state["learning"][HOUSEHOLD]) == {}


def test_shop_adjust_supersedes_old_basket_and_remembers_choices(setup):
    db, service, _ = setup
    db.state["inventory"][HOUSEHOLD] = []
    first = shopping(service)
    second = service.adjust_shop(
        USER, first.session_id, ShopAdjust(people=4, tags=[ShopTag.COVER_MORE_MEALS])
    )
    assert second.id != first.id
    assert (second.people, second.meals) == (4, 2)
    assert first.items[0].id != second.items[0].id
    assert db.state["baskets"][HOUSEHOLD, first.id].response.status == BasketStatus.ABANDONED
    assert db.state["prefs"][HOUSEHOLD].last_shop_meals == 2
    assert_error(
        ErrorCode.CONFLICT, lambda: service.confirm_shop(USER, first.id, bought(first), uid("old"))
    )


def test_shop_confirmation_uses_actual_packs_and_creates_new_batch_then_replays(setup):
    db, service, time = setup
    db.state["inventory"][HOUSEHOLD] = [batch(count=1)]
    basket = shopping(service)
    body, key = bought(basket, packs=2), uid("purchase")
    result = service.confirm_shop(USER, basket.id, body, key)
    assert result.items[0].count == 20
    assert result.items[0].source == ItemSource.SHOP_CONFIRM
    assert len(db.state["inventory"][HOUSEHOLD]) == 2  # Never merged into old batch.
    assert result.items[0].acquired_at == NOW.date()
    time[0] += timedelta(days=2)
    assert service.confirm_shop(USER, basket.id, body, key) == result
    assert db.stock_attempts == 1
    assert db.state["baskets"][HOUSEHOLD, basket.id].actual_lines[0].packs == 2


def test_shop_failed_save_rolls_back_purchase_and_basket(setup):
    db, service, _ = setup
    db.state["inventory"][HOUSEHOLD] = []
    basket = shopping(service)
    before = deepcopy(db.state)
    db.fail_on = "save_confirmation"
    with pytest.raises(RuntimeError):
        service.confirm_shop(USER, basket.id, bought(basket), uid("rollback"))
    assert db.stock_attempts == 1
    assert db.state == before


def test_missing_purchase_conversion_never_defaults_to_one_pack(setup):
    db, service, _ = setup
    db.state["inventory"][HOUSEHOLD] = []
    cat = db.state["catalogue"]
    purchases = dict(cat.purchases)
    purchases[uid("egg")] = purchases[uid("egg")].model_copy(
        update={"purchase_unit": None, "purchase_unit_size": None, "purchase_unit_measure": None}
    )
    db.state["catalogue"] = replace(cat, purchases=purchases)
    basket = shopping(service)
    assert basket.items[0].suggested_packs is None
    assert basket.items[0].countable
    assert basket.items[0].purchase_unit_size is None
    assert_error(
        ErrorCode.VALIDATION,
        lambda: service.confirm_shop(
            USER, basket.id, bought(basket, packs=1), uid("no-conversion")
        ),
    )
    assert db.stock_attempts == 0


@pytest.mark.parametrize("packs", [None, 2])
def test_incompatible_recipe_measure_preserves_actual_or_unknown_quantity_and_replays(setup, packs):
    db, service, _ = setup
    meal = recipe(ingredients=("egg",))
    meal.ingredients[0].quantity, meal.ingredients[0].unit = 150, "g"
    set_recipes(db, meal)
    db.state["inventory"][HOUSEHOLD] = []
    basket = shopping(service)
    item = basket.items[0]
    assert item.countable and item.suggested_packs is None
    assert (item.purchase_unit, item.purchase_unit_size, item.purchase_unit_measure) == (
        "tray",
        10,
        "pcs",
    )
    body, key = bought(basket, packs=packs), uid("actual-or-unknown-count")
    result = service.confirm_shop(USER, basket.id, body, key)
    assert result.items[0].count == (None if packs is None else 20)
    assert result.items[0].unit == (None if packs is None else "pcs")
    assert db.state["baskets"][HOUSEHOLD, basket.id].actual_lines[0].packs == packs
    assert service.confirm_shop(USER, basket.id, body, key) == result
    assert db.stock_attempts == 1


def test_counted_purchase_without_a_pack_count_is_kept_with_an_unknown_amount(setup):
    # The basket had no count to suggest and the shopper gave none: still record the purchase,
    # rather than failing the whole basket over one line.
    db, service, _ = setup
    db.state["inventory"][HOUSEHOLD] = []
    cat = db.state["catalogue"]
    purchases = dict(cat.purchases)
    purchases[uid("egg")] = purchases[uid("egg")].model_copy(
        update={"purchase_unit": None, "purchase_unit_size": None, "purchase_unit_measure": None}
    )
    db.state["catalogue"] = replace(cat, purchases=purchases)
    basket = shopping(service)
    assert basket.items[0].suggested_packs is None
    result = service.confirm_shop(USER, basket.id, bought(basket), uid("unknown-amount"))
    assert result.items[0].ingredient_id == uid("egg")
    assert result.items[0].count is None and result.items[0].unit is None
    assert result.items[0].remaining_state == RemainingState.ENOUGH
    assert db.state["baskets"][HOUSEHOLD, basket.id].actual_lines[0].packs is None


def test_shop_plans_the_recipe_asked_for_and_keeps_it_through_adjustment(setup):
    db, service, _ = setup
    set_recipes(db, recipe("starred", starred=True), recipe("asked", ingredients=("tomato",)))
    db.state["inventory"][HOUSEHOLD] = []
    basket = service.start_shop(USER, ShopSessionCreate(meals=1, recipe_ids=[uid("asked")]))
    assert [meal.id for meal in basket.planned_meals] == [uid("asked")]
    adjusted = service.adjust_shop(USER, basket.session_id, ShopAdjust(people=4))
    assert [meal.id for meal in adjusted.planned_meals] == [uid("asked")]


def test_shop_says_so_when_every_meal_can_already_be_cooked(setup):
    db, service, _ = setup
    set_recipes(db, recipe("covered", ingredients=("tomato",)))
    db.state["inventory"][HOUSEHOLD] = [batch("tomato")]
    with pytest.raises(ApiError) as caught:
        shopping(service)
    assert caught.value.code == ErrorCode.NO_RESULT
    assert caught.value.details["all_stocked"] is True


def test_shop_state_purchase_and_not_bought_lines(setup):
    db, service, _ = setup
    set_recipes(db, recipe(ingredients=("tomato", "egg")))
    db.state["inventory"][HOUSEHOLD] = []
    basket = shopping(service)
    body = BasketConfirm(
        lines=[
            BoughtLine(basket_item_id=item.id, bought=item.ingredient_id == uid("tomato"))
            for item in basket.items
        ]
    )
    result = service.confirm_shop(USER, basket.id, body, uid("state-shop"))
    assert len(result.items) == 1
    assert result.items[0].ingredient_id == uid("tomato")
    assert result.items[0].count is None
    assert result.items[0].remaining_state == RemainingState.ENOUGH


@pytest.mark.parametrize("change", ["duplicate", "extra", "missing"])
def test_shop_confirmation_checks_saved_line_membership(setup, change):
    db, service, _ = setup
    set_recipes(db, recipe(ingredients=("tomato", "egg")))
    db.state["inventory"][HOUSEHOLD] = []
    basket = shopping(service)
    body = bought(basket)
    if change == "missing":
        body.lines.pop()
    else:
        body.lines.append(
            body.lines[0].model_copy(
                update={} if change == "duplicate" else {"basket_item_id": uid("foreign")}
            )
        )
    assert_error(
        ErrorCode.VALIDATION,
        lambda: service.confirm_shop(USER, basket.id, body, uid("invalid-shop")),
    )
    assert db.stock_attempts == 0


@pytest.mark.parametrize("kind", ["cook", "shop"])
def test_sessions_expire_at_twelve_hours_without_sliding_on_adjustment(setup, kind):
    db, service, time = setup
    db.state["inventory"][HOUSEHOLD] = []
    if kind == "cook":
        first = service.start_cook(USER, CookSessionCreate())
        time[0] += timedelta(hours=11)
        service.adjust_cook(USER, first.session_id, CookAdjust(people=3))
        time[0] += timedelta(hours=1)
        assert_error(ErrorCode.NOT_FOUND, lambda: service.next_cook(USER, first.session_id))
    else:
        first = shopping(service)
        time[0] += timedelta(hours=11)
        second = service.adjust_shop(USER, first.session_id, ShopAdjust(people=3))
        time[0] += timedelta(hours=1)
        assert_error(
            ErrorCode.NOT_FOUND,
            lambda: service.confirm_shop(USER, second.id, bought(second), uid("expired")),
        )


@pytest.mark.parametrize(
    "operation",
    [
        "adjust_cook",
        "next_cook",
        "previous_cook",
        "select_cook",
        "confirm_cook",
        "feedback",
        "adjust_shop",
        "confirm_shop",
    ],
)
def test_foreign_household_cannot_read_or_change_session_record_or_basket(setup, operation):
    db, service, _ = setup
    record = selected(service)
    db.state["inventory"][HOUSEHOLD] = []
    basket = shopping(service)
    calls = {
        "adjust_cook": lambda: service.adjust_cook(
            STRANGER, record.session_id, CookAdjust(people=3)
        ),
        "next_cook": lambda: service.next_cook(STRANGER, record.session_id),
        "previous_cook": lambda: service.previous_cook(STRANGER, record.session_id),
        "select_cook": lambda: service.select_cook(STRANGER, record.session_id),
        "confirm_cook": lambda: service.confirm_cook(
            STRANGER, record.id, consumption(record), uid("foreign")
        ),
        "feedback": lambda: service.feedback(STRANGER, record.id, CookFeedback(rating=Rating.LIKE)),
        "adjust_shop": lambda: service.adjust_shop(
            STRANGER, basket.session_id, ShopAdjust(people=3)
        ),
        "confirm_shop": lambda: service.confirm_shop(
            STRANGER, basket.id, bought(basket), uid("foreign")
        ),
    }
    before = deepcopy(db.state)
    assert_error(ErrorCode.NOT_FOUND, calls[operation])
    assert db.state == before
    assert db.stock_attempts == 0


def test_previous_does_not_reintroduce_an_allergen_after_preferences_change(setup):
    db, service, _ = setup
    first = service.start_cook(USER, CookSessionCreate())
    service.next_cook(USER, first.session_id)
    db.state["prefs"][HOUSEHOLD] = prefs(allergens=[Allergen.EGG])
    assert_error(ErrorCode.CONFLICT, lambda: service.previous_cook(USER, first.session_id))


def test_same_household_members_share_learning_but_records_keep_creator(setup):
    db, service, _ = setup
    member = replace(USER, user_id=uid("another-household-member"))
    record = selected(service)
    assert db.state["cook_records"][HOUSEHOLD, record.id].user_id == USER.user_id
    service.confirm_cook(member, record.id, consumption(record), uid("member-confirms"))
    service.feedback(member, record.id, CookFeedback(rating=Rating.LIKE))
    assert taste_weights(db.state["learning"][HOUSEHOLD]) == {"cuisine:chinese": 0.25}
    assert taste_weights(db.state["learning"][OTHER]) == {}


def test_confirmation_keys_cannot_be_reused_between_cook_and_shop(setup):
    db, service, _ = setup
    record = selected(service)
    key = uid("shared-operation-key")
    service.confirm_cook(USER, record.id, consumption(record), key)
    db.state["inventory"][HOUSEHOLD] = []
    basket = shopping(service)
    assert_error(
        ErrorCode.CONFLICT, lambda: service.confirm_shop(USER, basket.id, bought(basket), key)
    )
    assert db.stock_attempts == 1


def test_same_key_in_another_household_does_not_replay_foreign_confirmation(setup):
    db, service, _ = setup
    record = selected(service)
    key = uid("shared-key")
    service.confirm_cook(USER, record.id, consumption(record), key)
    suggestion = service.start_cook(STRANGER, CookSessionCreate())
    other_record = service.select_cook(STRANGER, suggestion.session_id)
    result = service.confirm_cook(STRANGER, other_record.id, consumption(other_record), key)
    assert result.cook_record_id == other_record.id
    assert result.event.user_id == STRANGER.user_id
    assert len(db.state["events"]) == 2


def test_shop_failed_adjustment_preserves_old_confirmable_basket(setup):
    db, service, _ = setup
    db.state["inventory"][HOUSEHOLD] = []
    basket = shopping(service)
    db.state["prefs"][HOUSEHOLD] = prefs(allergens=[Allergen.EGG])
    before = deepcopy(db.state)
    assert_error(
        ErrorCode.NO_RESULT,
        lambda: service.adjust_shop(USER, basket.session_id, ShopAdjust(people=4)),
    )
    assert db.state == before
    assert db.state["baskets"][HOUSEHOLD, basket.id].response.status == BasketStatus.SUGGESTED


def test_shop_double_confirmation_and_edit_after_purchase_are_rejected(setup):
    db, service, _ = setup
    db.state["inventory"][HOUSEHOLD] = []
    basket = shopping(service)
    service.confirm_shop(USER, basket.id, bought(basket), uid("first-purchase"))
    assert db.state["baskets"][HOUSEHOLD, basket.id].actual_lines[0].packs == 1
    assert_error(
        ErrorCode.CONFLICT,
        lambda: service.confirm_shop(USER, basket.id, bought(basket), uid("second-purchase")),
    )
    assert_error(
        ErrorCode.CONFLICT,
        lambda: service.adjust_shop(USER, basket.session_id, ShopAdjust(people=3)),
    )
    assert db.stock_attempts == 1


def test_no_stock_consumed_is_still_an_explicit_confirmed_cooking(setup):
    db, service, _ = setup
    record = selected(service)
    body = CookConfirm(
        lines=[
            ConsumptionLine(
                inventory_item_id=line.item.id,
                revision=line.item.revision,
                outcome=ConsumptionOutcome.NOT_USED,
            )
            for line in record.proposed_consumption
        ]
    )
    result = service.confirm_cook(USER, record.id, body, uid("all-not-used"))
    assert not result.items
    assert not result.event.lines
    assert db.state["inventory"][HOUSEHOLD][0].count == 10
    assert len(db.state["learning"][HOUSEHOLD].meals) == 1
