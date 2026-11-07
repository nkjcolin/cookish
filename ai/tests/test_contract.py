"""Check that this Lambda serves exactly the /ai part of the shared contract.

docs/openapi.json is generated from the backend's schemas, and app/schemas.py is a copy of
them. Any difference in a path or a schema the /ai routes use fails here.
"""

import json
from pathlib import Path
from typing import Any

from app.main import app

CONTRACT = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def _referenced_schemas(node: Any, components: dict[str, Any], found: dict[str, Any]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            name = ref.rsplit("/", 1)[-1]
            if name not in found:
                found[name] = components[name]
                _referenced_schemas(components[name], components, found)
        for value in node.values():
            _referenced_schemas(value, components, found)
    elif isinstance(node, list):
        for value in node:
            _referenced_schemas(value, components, found)


def _ai_part(spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = {path: item for path, item in spec["paths"].items() if path.startswith("/ai/")}
    schemas: dict[str, Any] = {}
    _referenced_schemas(paths, spec["components"]["schemas"], schemas)
    return paths, schemas


def test_paths_match_the_contract() -> None:
    expected, _ = _ai_part(json.loads(CONTRACT.read_text()))
    actual, _ = _ai_part(app.openapi())

    assert actual == expected


def test_schemas_match_the_contract() -> None:
    _, expected = _ai_part(json.loads(CONTRACT.read_text()))
    _, actual = _ai_part(app.openapi())

    assert sorted(actual) == sorted(expected)
    for name in expected:
        assert actual[name] == expected[name], name


def test_draft_item_has_no_ingredient_identifier() -> None:
    item = app.openapi()["components"]["schemas"]["DraftItem"]
    assert "ingredient_id" not in item["properties"]
