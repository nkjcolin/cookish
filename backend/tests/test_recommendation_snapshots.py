"""Persistence boundaries preserve workflow evidence, not just response shape."""

import json
from copy import deepcopy
from dataclasses import replace
from itertools import count

import pytest

from app.auth import CurrentUser
from app.reco.learning import LearningState, learn, taste_weights
from app.schemas.cook import (
    ConsumptionLine,
    CookConfirm,
    CookFeedback,
    CookRecordStatus,
    CookSessionCreate,
    Rating,
)
from app.schemas.shop import BasketConfirm, BoughtLine, ShopSessionCreate
from app.services.recommendation_repository import (
    Confirmation,
    CookSessionRow,
    ShopSessionRow,
)
from app.services.recommendation_snapshots import dump_snapshot, load_snapshot
from app.services.recommendation_workflow import RecommendationWorkflow
from tests.reco_fixtures import NOW, recipe, uid
from tests.recommendation_repository_fake import HOUSEHOLD, FakeDatabase

USER = CurrentUser(uid("snapshot-user"), HOUSEHOLD, "snapshot@example.test")


@pytest.fixture
def records():
    database = FakeDatabase()
    ids = count()
    workflow = RecommendationWorkflow(
        database.transaction, now=lambda: NOW, new_id=lambda: uid(f"snapshot/{next(ids)}")
    )
    first = workflow.start_cook(USER, CookSessionCreate(people=3))
    workflow.next_cook(USER, first.session_id)
    workflow.previous_cook(USER, first.session_id)
    selected = workflow.select_cook(USER, first.session_id)
    selected_row = database.state["cook_records"][HOUSEHOLD, selected.id]
    workflow.confirm_cook(
        USER,
        selected.id,
        CookConfirm(
            lines=[
                ConsumptionLine(
                    inventory_item_id=line.item.id,
                    revision=line.item.revision,
                    new_count=line.proposed_count,
                    outcome=line.proposed_outcome,
                )
                for line in selected.proposed_consumption
            ]
        ),
        uid("snapshot-cook-confirm"),
    )
    workflow.feedback(USER, selected.id, CookFeedback(rating=Rating.LIKE))
    database.state["inventory"][HOUSEHOLD] = []
    basket = workflow.start_shop(USER, ShopSessionCreate(people=3, meals=2))
    workflow.confirm_shop(
        USER,
        basket.id,
        BasketConfirm(
            lines=[
                BoughtLine(basket_item_id=item.id, bought=True, packs=item.suggested_packs)
                for item in basket.items
            ]
        ),
        uid("snapshot-shop-confirm"),
    )
    return {
        "cook_session": database.state["cook_sessions"][HOUSEHOLD, first.session_id],
        "selection": selected_row,
        "cook_record": database.state["cook_records"][HOUSEHOLD, selected.id],
        "shop_session": database.state["shop_sessions"][HOUSEHOLD, basket.session_id],
        "basket": database.state["baskets"][HOUSEHOLD, basket.id],
        "learning": database.state["learning"][HOUSEHOLD],
        "cook_confirmation": database.state["confirmations"][
            HOUSEHOLD, uid("snapshot-cook-confirm")
        ],
        "shop_confirmation": database.state["confirmations"][
            HOUSEHOLD, uid("snapshot-shop-confirm")
        ],
    }


@pytest.mark.parametrize(
    "name",
    [
        "cook_session",
        "selection",
        "cook_record",
        "shop_session",
        "basket",
        "learning",
        "cook_confirmation",
        "shop_confirmation",
    ],
)
def test_saved_workflow_records_survive_json_storage_without_aliasing(records, name):
    original = records[name]
    wire = json.loads(json.dumps(dump_snapshot(original)))
    restored = load_snapshot(wire, type(original))
    assert restored == original
    assert restored is not original
    assert dump_snapshot(restored) == wire
    wire["payload"].clear()
    assert restored == original


def test_selected_consumption_keeps_original_batch_revisions_and_portions(records):
    row = records["selection"]
    restored = load_snapshot(dump_snapshot(row), type(row))
    line = restored.response.proposed_consumption[0]
    assert restored.response.people == 3
    assert line.item.revision == 1
    assert line.item.count == 10
    assert line.proposed_count == 5.5
    assert records["cook_confirmation"].response.items[0].revision == 2
    records["cook_confirmation"].response.items[0].count = 1000
    assert line.item.count == 10


def test_older_basket_responses_recover_only_their_frozen_purchase_metadata(records):
    original = records["basket"]
    wire = dump_snapshot(original)
    fields = ("countable", "purchase_unit", "purchase_unit_size", "purchase_unit_measure")
    for item in wire["payload"]["response"]["items"]:
        for name in fields:
            del item[name]
    unchanged = deepcopy(wire)
    restored = load_snapshot(wire, type(original))
    assert restored == original
    assert wire == unchanged  # Loading does not rewrite original planning evidence.


@pytest.mark.parametrize("field", ["countable", "purchase_unit_size"])
def test_basket_response_cannot_disagree_with_frozen_purchase_metadata(records, field):
    original = records["basket"]
    wire = dump_snapshot(original)
    item = wire["payload"]["response"]["items"][0]
    item[field] = not item[field] if field == "countable" else 999
    with pytest.raises(ValueError, match="frozen purchase metadata"):
        load_snapshot(wire, type(original))


def test_partial_new_basket_metadata_is_rejected_without_defaulting(records):
    original = records["basket"]
    wire = dump_snapshot(original)
    del wire["payload"]["response"]["items"][0]["countable"]
    with pytest.raises(ValueError, match="incomplete"):
        load_snapshot(wire, type(original))


def test_previous_history_and_current_cursor_survive_roundtrip(records):
    row = load_snapshot(dump_snapshot(records["cook_session"]), CookSessionRow)
    assert len(row.history) == 2
    assert row.position == 0
    assert row.state.current_recipe_id == row.history[0].recipe.id
    assert row.state.shown_recipe_ids == tuple(item.recipe.id for item in row.history)
    assert row.history[0].recipe.id in row.state.skipped_recipe_ids


def test_legacy_cook_history_loads_with_no_advertised_nudges_without_rewriting_evidence(records):
    wire = dump_snapshot(records["cook_session"])
    for suggestion in wire["payload"]["history"]:
        del suggestion["available_nudges"]
    original = deepcopy(wire)
    restored = load_snapshot(wire, CookSessionRow)
    assert all(suggestion.available_nudges == [] for suggestion in restored.history)
    assert restored.state == records["cook_session"].state
    assert restored.position == records["cook_session"].position
    assert wire == original


def test_legacy_nudge_upgrade_does_not_hide_other_missing_history_fields(records):
    wire = dump_snapshot(records["cook_session"])
    del wire["payload"]["history"][0]["available_nudges"]
    del wire["payload"]["history"][0]["has_previous"]
    with pytest.raises(ValueError, match="missing"):
        load_snapshot(wire, CookSessionRow)


def test_learning_roundtrip_preserves_order_for_edited_saturated_rating():
    state = LearningState(HOUSEHOLD)
    meal = recipe("liked")
    for index in range(12):
        state = learn(
            state,
            household_id=HOUSEHOLD,
            record_id=uid(f"learn/{index}"),
            recipe=meal,
            status=CookRecordStatus.CONFIRMED,
            rating=Rating.LIKE,
        )
    assert taste_weights(state) == {"cuisine:chinese": 2.0}
    restored = load_snapshot(dump_snapshot(state), LearningState)
    edited = learn(
        restored,
        household_id=HOUSEHOLD,
        record_id=uid("learn/11"),
        recipe=meal,
        status=CookRecordStatus.CONFIRMED,
        rating=Rating.DISLIKE,
    )
    assert taste_weights(edited) == {"cuisine:chinese": 1.75}
    assert [item.record_id for item in edited.meals] == [item.record_id for item in state.meals]


@pytest.mark.parametrize("version", [0, 2, True, "1", 1.0, None])
def test_unknown_or_coerced_version_is_rejected(records, version):
    wire = dump_snapshot(records["learning"])
    wire["schema_version"] = version
    with pytest.raises(ValueError, match="version"):
        load_snapshot(wire, LearningState)


def test_missing_default_fields_are_not_silently_recreated(records):
    wire = dump_snapshot(records["cook_session"])
    del wire["payload"]["state"]["skipped_recipe_ids"]
    with pytest.raises(ValueError, match="missing"):
        load_snapshot(wire, CookSessionRow)
    wire = dump_snapshot(records["learning"])
    del wire["payload"]["meals"]
    with pytest.raises(ValueError, match="missing"):
        load_snapshot(wire, LearningState)


def test_a_shop_session_saved_before_pins_loads_with_none(records):
    # The one field added after version 1 shipped: older sessions meant "nothing pinned".
    wire = dump_snapshot(records["shop_session"])
    del wire["payload"]["state"]["pinned_recipe_ids"]
    loaded = load_snapshot(wire, ShopSessionRow)
    assert loaded == records["shop_session"]
    assert loaded.state.pinned_recipe_ids == ()


@pytest.mark.parametrize("location", ["envelope", "dataclass", "response"])
def test_extra_fields_are_rejected_at_every_storage_boundary(records, location):
    wire = dump_snapshot(records["cook_session"])
    target = {
        "envelope": wire,
        "dataclass": wire["payload"]["state"],
        "response": wire["payload"]["history"][0],
    }[location]
    target["unexpected"] = True
    with pytest.raises(ValueError):
        load_snapshot(wire, CookSessionRow)


@pytest.mark.parametrize("people", [True, "3", 3.0])
def test_coerced_session_values_are_rejected(records, people):
    wire = dump_snapshot(records["cook_session"])
    wire["payload"]["state"]["people"] = people
    with pytest.raises(ValueError):
        load_snapshot(wire, CookSessionRow)


def test_naive_datetime_and_invalid_cursor_are_rejected(records):
    wire = dump_snapshot(records["cook_session"])
    wire["payload"]["expires_at"] = "2026-11-07T12:00:00"
    with pytest.raises(ValueError, match="timezone-aware"):
        load_snapshot(wire, CookSessionRow)
    wire = dump_snapshot(records["cook_session"])
    wire["payload"]["position"] = 30
    with pytest.raises(ValueError, match="cursor"):
        load_snapshot(wire, CookSessionRow)


def test_wrong_kind_legacy_missing_payload_and_nonfinite_learning_are_rejected(records):
    wire = dump_snapshot(records["learning"])
    with pytest.raises(ValueError, match="kind"):
        load_snapshot(wire, CookSessionRow)
    for invalid in (None, {}, {"schema_version": 1, "kind": "learning"}):
        with pytest.raises(ValueError):
            load_snapshot(invalid, LearningState)
    wire["payload"]["config"]["step"] = float("nan")
    with pytest.raises(ValueError):
        load_snapshot(wire, LearningState)


def test_confirmation_kind_target_and_request_must_match(records):
    original = records["cook_confirmation"]
    for invalid in (
        replace(original, operation="shop"),
        replace(original, target_id=uid("another-record")),
        replace(original, request_json="[]"),
    ):
        with pytest.raises(ValueError):
            dump_snapshot(invalid)
    wire = dump_snapshot(original)
    wire["payload"]["response"]["basket_id"] = str(uid("another-basket"))
    with pytest.raises(ValueError):
        load_snapshot(wire, Confirmation)


def test_duplicate_evidence_or_set_entries_are_rejected(records):
    wire = dump_snapshot(records["learning"])
    wire["payload"]["meals"].append(deepcopy(wire["payload"]["meals"][0]))
    with pytest.raises(ValueError):
        load_snapshot(wire, LearningState)
    wire = dump_snapshot(records["learning"])
    features = wire["payload"]["meals"][0]["features"]
    features.append(features[0])
    with pytest.raises(ValueError, match="duplicate"):
        load_snapshot(wire, LearningState)
