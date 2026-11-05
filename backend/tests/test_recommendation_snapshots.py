"""Persistence JSON retains historical values and rejects incompatible data."""

import json
from copy import deepcopy

import pytest

from app.errors import ApiError, ErrorCode
from app.reco.config import LearningConfig
from app.reco.learning import MealEvidence
from app.reco.models import CookSession
from app.schemas.cook import Rating
from app.services import recommendation_snapshots as codec
from tests.reco_fixtures import uid


def test_json_round_trip_preserves_feature_sets_evidence_order_and_custom_config():
    value = codec.Evidence(
        meals=(
            MealEvidence(
                uid("b"), uid("r"), frozenset({"cuisine:chinese", "tag:low_oil"}), Rating.LIKE
            ),
            MealEvidence(uid("a"), uid("r"), frozenset({"tag:low_oil"}), None),
        ),
        config=LearningConfig(step=0.5),
    )
    document = json.loads(json.dumps(codec.dump("learning", codec.Evidence, value)))
    assert codec.restore("learning", codec.Evidence, document) == value


@pytest.mark.parametrize("version", [None, 0, 2, True, "1"])
def test_unknown_version_is_rejected(version):
    document = {"schema_version": version, "kind": "learning", "payload": {}}
    with pytest.raises(ApiError) as error:
        codec.restore("learning", codec.Evidence, document)
    assert error.value.code == ErrorCode.CONFLICT


def test_missing_snapshot_requires_restart_instead_of_inventing_history():
    with pytest.raises(ApiError, match="start again"):
        codec.restore("cook_session", codec.CookState, None)


@pytest.mark.parametrize("change", ["extra", "nested_extra", "invalid_people", "wrong_kind"])
def test_corrupt_state_is_rejected(change):
    document = codec.dump(
        "cook_session",
        codec.CookState,
        codec.CookState(state=CookSession(), history=(), position=-1, selected_record_id=None),
    )
    document = deepcopy(document)
    if change == "extra":
        document["future_field"] = True
    elif change == "nested_extra":
        document["payload"]["state"]["future_field"] = True
    elif change == "invalid_people":
        document["payload"]["state"]["people"] = 99
    else:
        document["kind"] = "shop_session"
    with pytest.raises(ApiError):
        codec.restore("cook_session", codec.CookState, document)
