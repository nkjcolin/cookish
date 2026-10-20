from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from scripts.validate_recipe_handoff import validate_handoff

BASE_ID = "6a1f3c2e-0d4b-4f7e-9a51-2c8e7b0d1f34"
VARIANT_ID = "887f7504-3a88-414b-92b4-911ae3fdd4b3"


def write_yaml(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def change_yaml(path: Path, change) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data)
    write_yaml(path, data)


@pytest.fixture
def handoff(tmp_path):
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    base = {
        "id": BASE_ID,
        "title": "Tomato soup",
        "variant_of": None,
        "cuisine": "other",
        "total_minutes": 20,
        "active_minutes": 10,
        "difficulty": 1,
        "servings": 2,
        "equipment": ["stove"],
        "taste_tags": ["soupy"],
        "ingredients": [
            {"canonical_name": "tomato", "quantity": 2, "unit": "pcs", "essential": True},
            {"canonical_name": "salt", "coarse_amount": "a pinch", "essential": False},
        ],
        "steps": ["Simmer the chopped tomatoes with water.", "Season and serve."],
        "source": "original",
        "reviewed": False,
    }
    variant = deepcopy(base)
    variant.update(
        id=VARIANT_ID,
        title="Light tomato soup",
        variant_of=BASE_ID,
        variant_label="light",
    )
    variant["ingredients"][0].update(quantity=200, unit="g")
    write_yaml(recipes / "tomato-soup.yaml", base)
    write_yaml(recipes / "light-tomato-soup.yaml", variant)
    write_yaml(
        tmp_path / "recipe_plan.yaml",
        {
            "recipes": [
                {
                    "slug": "tomato-soup",
                    "title": "Tomato soup",
                    "status": "draft",
                    "variant_of": None,
                    "ingredients": ["tomato", "salt"],
                },
                {
                    "slug": "light-tomato-soup",
                    "title": "Light tomato soup",
                    "status": "draft",
                    "variant_of": "tomato-soup",
                    "ingredients": ["tomato", "salt"],
                },
                {
                    "slug": "noodle-soup",
                    "title": "Noodle soup",
                    "status": "planned",
                    "variant_of": None,
                    "ingredients": ["noodles", "salt"],
                },
            ]
        },
    )
    write_yaml(
        tmp_path / "ingredient_requests.yaml",
        {
            "ingredients": [
                {
                    "canonical_name": "tomato",
                    "aliases": ["tomatoes"],
                    "recipe_units": ["pcs", "g"],
                    "notes": "",
                },
                {
                    "canonical_name": "salt",
                    "aliases": [],
                    "recipe_units": ["coarse"],
                    "notes": "",
                },
                {
                    "canonical_name": "noodles",
                    "aliases": ["noodle"],
                    "recipe_units": ["g"],
                    "notes": "Planned recipe.",
                },
            ]
        },
    )
    return tmp_path


def errors(handoff, **kwargs) -> str:
    return "\n".join(validate_handoff(handoff, **kwargs).errors)


def test_repository_recipe_handoff_is_consistent():
    result = validate_handoff()
    assert not result.errors, "\n".join(result.errors)


def test_valid_handoff_allows_drafts_but_release_requires_review(handoff):
    result = validate_handoff(handoff)
    assert result.errors == []
    assert (result.recipe_count, result.plan_count, result.ingredient_count) == (2, 3, 3)
    assert result.unreviewed_count == 2
    assert errors(handoff, require_reviewed=True).count("reviewed must be true") == 2
    for path in (handoff / "recipes").glob("*.yaml"):
        change_yaml(path, lambda recipe: recipe.update(reviewed=True))
    assert errors(handoff, require_reviewed=True) == ""


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("id", "invalid", "UUID"),
        ("servings", True, "valid integer"),
        ("servings", 0, "greater than 0"),
        ("total_minutes", -1, "greater than 0"),
        ("active_minutes", 21, "must not exceed"),
        ("difficulty", 4, "less than or equal to 3"),
        ("cuisine", "fusion", "cuisine"),
        ("equipment", ["hob"], "equipment"),
        ("taste_tags", ["healthy"], "taste_tags"),
        ("reviewed", "false", "valid boolean"),
        ("steps", [], "at least 1"),
        ("source", "", "must be nonempty"),
        ("diet_flags", ["vegan"], "Extra inputs are not permitted"),
        ("allergens", [], "Extra inputs are not permitted"),
    ],
)
def test_recipe_rejects_invalid_contract_values(handoff, field, value, expected):
    change_yaml(handoff / "recipes/tomato-soup.yaml", lambda recipe: recipe.update({field: value}))
    assert expected in errors(handoff)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"coarse_amount": "a handful"}, "never mix"),
        ({"quantity": float("inf")}, "finite number"),
        ({"quantity": float("nan")}, "finite number"),
        ({"quantity": True}, "valid number"),
        ({"quantity": 0}, "greater than 0"),
        ({"quantity": None}, "never mix"),
        ({"unit": "cups"}, "unit"),
    ],
)
def test_recipe_rejects_ambiguous_or_invalid_amounts(handoff, change, expected):
    change_yaml(
        handoff / "recipes/tomato-soup.yaml",
        lambda recipe: recipe["ingredients"][0].update(change),
    )
    assert expected in errors(handoff)


def test_recipe_rejects_duplicate_ingredients_and_uuids(handoff):
    change_yaml(
        handoff / "recipes/tomato-soup.yaml",
        lambda recipe: recipe["ingredients"].append(deepcopy(recipe["ingredients"][0])),
    )
    assert "duplicate ingredient canonical names" in errors(handoff)
    change_yaml(
        handoff / "recipes/tomato-soup.yaml",
        lambda recipe: (recipe["ingredients"].pop(), recipe.update(id=VARIANT_ID)),
    )
    assert "duplicate UUID" in errors(handoff)


def test_variant_requires_label_known_base_and_no_cycles(handoff):
    variant = handoff / "recipes/light-tomato-soup.yaml"
    change_yaml(variant, lambda recipe: recipe.pop("variant_label"))
    assert "variant requires variant_label" in errors(handoff)
    change_yaml(
        variant,
        lambda recipe: recipe.update(
            variant_label="light", variant_of="f4f60765-0ef7-45bb-bbae-830ef60cf7bd"
        ),
    )
    assert "unknown variant_of" in errors(handoff)
    change_yaml(variant, lambda recipe: recipe.update(variant_of=VARIANT_ID))
    assert "cannot reference itself" in errors(handoff)
    change_yaml(variant, lambda recipe: recipe.update(variant_of=BASE_ID))
    change_yaml(
        handoff / "recipes/tomato-soup.yaml",
        lambda recipe: recipe.update(variant_of=VARIANT_ID, variant_label="original"),
    )
    assert "variant cycle" in errors(handoff)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda plan: plan["recipes"].append(deepcopy(plan["recipes"][0])), "duplicate slug"),
        (lambda plan: plan["recipes"][0].update(status="planned"), "must have a draft entry"),
        (lambda plan: plan["recipes"][2].update(status="draft"), "has no recipe file"),
        (lambda plan: plan["recipes"][0].update(title="Different"), "title does not match"),
        (
            lambda plan: plan["recipes"][0].update(ingredients=["salt"]),
            "ingredient set does not match",
        ),
        (lambda plan: plan["recipes"][1].update(variant_of=None), "variant_of does not match"),
        (lambda plan: plan["recipes"][2].update(variant_of="missing"), "unknown variant_of"),
        (
            lambda plan: plan["recipes"][0].update(variant_of="light-tomato-soup"),
            "variant cycle",
        ),
    ],
)
def test_plan_cannot_drift_from_delivered_recipes(handoff, change, expected):
    change_yaml(handoff / "recipe_plan.yaml", change)
    assert expected in errors(handoff)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda request: request["ingredients"].pop(), "missing planned ingredient noodles"),
        (
            lambda request: request["ingredients"].append(
                {
                    "canonical_name": "carrot",
                    "aliases": [],
                    "recipe_units": ["g"],
                    "notes": "",
                }
            ),
            "unused ingredient carrot",
        ),
        (
            lambda request: request["ingredients"].append(deepcopy(request["ingredients"][0])),
            "duplicate canonical_name",
        ),
        (
            lambda request: request["ingredients"][0].update(aliases=["Salt"]),
            "collides",
        ),
        (
            lambda request: request["ingredients"][0].update(aliases=["noodle"]),
            "collides",
        ),
        (
            lambda request: request["ingredients"][0].update(recipe_units=["pcs"]),
            "unit g for tomato",
        ),
        (
            lambda request: request["ingredients"][1].update(recipe_units=["g"]),
            "unit coarse for salt",
        ),
    ],
)
def test_ingredient_request_manifest_is_complete_and_unambiguous(handoff, change, expected):
    change_yaml(handoff / "ingredient_requests.yaml", change)
    assert expected in errors(handoff)


def test_optional_catalogue_requires_exact_canonical_recipe_names(handoff):
    catalogue = handoff / "ingredients.csv"
    catalogue.write_text("id,canonical_name\n1,tomato\n2,salt\n", encoding="utf-8")
    assert errors(handoff, ingredients_csv=catalogue) == ""
    catalogue.write_text("id,canonical_name\n1,tomatoes\n2,salt\n", encoding="utf-8")
    assert "recipe ingredient 'tomato' has no canonical row" in errors(
        handoff, ingredients_csv=catalogue
    )
    catalogue.write_text("id,name\n1,tomato\n", encoding="utf-8")
    assert "missing canonical_name CSV column" in errors(handoff, ingredients_csv=catalogue)


def test_unsafe_or_malformed_yaml_reports_errors_without_execution(handoff):
    recipe = handoff / "recipes/tomato-soup.yaml"
    recipe.write_text("!!python/object/apply:builtins.print ['unsafe']", encoding="utf-8")
    assert "cannot read YAML" in errors(handoff)
    recipe.write_text("ingredients: [", encoding="utf-8")
    assert "cannot read YAML" in errors(handoff)


def test_missing_manifest_reports_filename(handoff):
    (handoff / "ingredient_requests.yaml").unlink()
    assert "ingredient_requests.yaml: cannot read YAML" in errors(handoff)
