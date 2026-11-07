"""Versioned JSON snapshots for Role 5 persistence, with no database access.

Every field is stored, including nulls and empty collections. A malformed or
older payload must never silently turn into a fresh session or empty learning
state. The SQL adapter remains responsible for comparing household, record IDs
and expiry with its locked relational rows before using the decoded value.
"""

import json
import math
from dataclasses import fields, is_dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, TypeAdapter

from app.reco.learning import LearningState
from app.schemas.cook import CookConfirmResult
from app.schemas.shop import BasketConfirmResult
from app.services.recommendation_repository import (
    BasketRow,
    Confirmation,
    CookRecordRow,
    CookSessionRow,
    ShopSessionRow,
)

_KINDS = {
    CookSessionRow: "cook_session",
    CookRecordRow: "cook_record",
    ShopSessionRow: "shop_session",
    BasketRow: "basket",
    LearningState: "learning",
    Confirmation: "confirmation",
}
_ADAPTERS = {kind: TypeAdapter(kind) for kind in _KINDS}


def _fields(value):
    if isinstance(value, BaseModel):
        return {name: getattr(value, name) for name in type(value).model_fields}
    if is_dataclass(value):
        return {field.name: getattr(value, field.name) for field in fields(value)}
    return None


def _check_complete(raw, value) -> None:
    """Pydantic validates types; also forbid ignored extras and defaulted fields."""
    values = _fields(value)
    if values is not None:
        if not isinstance(raw, dict) or raw.keys() != values.keys():
            raise ValueError("Snapshot fields are missing or unexpected")
        for name, child in values.items():
            _check_complete(raw[name], child)
    elif isinstance(value, dict):
        if not isinstance(raw, dict) or raw.keys() != {str(key) for key in value}:
            raise ValueError("Snapshot map keys are not canonical or contain duplicates")
        for key, child in value.items():
            _check_complete(raw[str(key)], child)
    elif isinstance(value, (list, tuple)):
        for original, child in zip(raw, value, strict=True):
            _check_complete(original, child)
    elif isinstance(value, (set, frozenset)):
        if len(raw) != len(value):
            raise ValueError("Snapshot set contains duplicate entries")
    elif isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Snapshot timestamps must be timezone-aware")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Snapshot numbers must be finite")


def _stable_sets(raw, value):
    """Preserve ordered evidence/history while giving sets a stable JSON order."""
    values = _fields(value)
    if values is not None:
        return {name: _stable_sets(raw[name], child) for name, child in values.items()}
    if isinstance(value, dict):
        return {str(key): _stable_sets(raw[str(key)], child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_stable_sets(item, child) for item, child in zip(raw, value, strict=True)]
    if isinstance(value, (set, frozenset)):
        return sorted(raw, key=lambda item: json.dumps(item, sort_keys=True))
    return raw


def _check_consistency(value) -> None:
    if isinstance(value, CookSessionRow):
        if not value.history:
            if value.position != -1 or value.state.current_recipe_id is not None:
                raise ValueError("Empty Cook history has an invalid cursor")
        elif not 0 <= value.position < len(value.history):
            raise ValueError("Cook history cursor is outside its saved history")
        elif value.state.current_recipe_id != value.history[value.position].recipe.id:
            raise ValueError("Current recipe does not match the Cook history cursor")
        if any(entry.session_id != value.id for entry in value.history):
            raise ValueError("Cook history belongs to a different session")
    elif isinstance(value, CookRecordRow):
        if value.recipe_snapshot.id != value.response.recipe.id:
            raise ValueError("Cook record recipe does not match its frozen candidate")
    elif isinstance(value, BasketRow):
        if any(key != meta.id for key, meta in value.ingredients.items()):
            raise ValueError("Basket ingredient metadata has mismatched IDs")
        if value.purchases.keys() != value.ingredients.keys():
            raise ValueError("Basket purchase and ingredient metadata do not match")
        item_ids = {item.id for item in value.response.items}
        if len(item_ids) != len(value.response.items):
            raise ValueError("Basket contains duplicate item IDs")
        actual_ids = [line.basket_item_id for line in value.actual_lines]
        if len(actual_ids) != len(set(actual_ids)) or not set(actual_ids) <= item_ids:
            raise ValueError("Actual purchases do not match the saved basket")
    elif isinstance(value, Confirmation):
        result_type = {"cook": CookConfirmResult, "shop": BasketConfirmResult}.get(value.operation)
        if result_type is None or not isinstance(value.response, result_type):
            raise ValueError("Confirmation operation does not match its response")
        target = (
            value.response.cook_record_id
            if isinstance(value.response, CookConfirmResult)
            else value.response.basket_id
        )
        if value.target_id != target or value.response.event.ref_id != target:
            raise ValueError("Confirmation target does not match its saved response")
        if not isinstance(json.loads(value.request_json), dict):
            raise ValueError("Confirmation request must be a JSON object")


def dump_snapshot(value) -> dict[str, Any]:
    """Return a fresh JSON-compatible schema-version-1 envelope for a port record."""
    kind = type(value)
    if kind not in _KINDS:
        raise TypeError("Unsupported recommendation snapshot type")
    payload = _ADAPTERS[kind].dump_python(value, mode="json", warnings="error")
    snapshot = {
        "schema_version": 1,
        "kind": _KINDS[kind],
        "payload": _stable_sets(payload, value),
    }
    # Validate writes too: dataclasses/model_copy can bypass normal type checking.
    load_snapshot(snapshot, kind)
    return snapshot


def _upgrade(kind, payload):
    """Fill fields added after version 1 was first written, with the value they then meant.

    Shop sessions gained pinned_recipe_ids: one saved before it pinned nothing.
    """
    if kind is ShopSessionRow and isinstance(payload, dict):
        state = payload.get("state")
        if isinstance(state, dict) and "pinned_recipe_ids" not in state:
            return {**payload, "state": {**state, "pinned_recipe_ids": []}}
    return payload


def load_snapshot[T](snapshot: object, expected_type: type[T]) -> T:
    """Decode a complete snapshot, rejecting unsupported versions and record kinds.

    ValueError includes Pydantic ValidationError for invalid persisted contents.
    None/legacy rows are intentionally rejected; the adapter can map those to a
    restart-session error without inventing history or resetting learned taste.
    """
    if expected_type not in _KINDS:
        raise TypeError("Unsupported recommendation snapshot type")
    if not isinstance(snapshot, dict) or snapshot.keys() != {"schema_version", "kind", "payload"}:
        raise ValueError("Invalid recommendation snapshot envelope")
    if type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1:
        raise ValueError("Unsupported recommendation snapshot version")
    if snapshot["kind"] != _KINDS[expected_type]:
        raise ValueError("Unexpected recommendation snapshot kind")
    payload = _upgrade(expected_type, snapshot["payload"])
    encoded = json.dumps(payload, allow_nan=False)
    decoded = _ADAPTERS[expected_type].validate_json(encoded, strict=True)
    _check_complete(payload, decoded)
    _check_consistency(decoded)
    return decoded
