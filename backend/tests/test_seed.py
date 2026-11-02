"""The catalogue must load: ingredients.csv is valid and every recipe resolves against it.

These tests need no database. They run the same checks as `python -m seed.seed`, so a bad
edit to a recipe or the CSV fails in CI instead of stopping everyone's backend at start-up.
"""

from pathlib import Path

from seed.seed import INGREDIENTS_CSV, RECIPES_DIR, read_ingredients, read_recipes


def _catalogue():
    rows, problems = read_ingredients(INGREDIENTS_CSV)
    assert problems == []
    return rows


def test_ingredients_csv_is_valid():
    rows = _catalogue()
    assert rows
    assert len({row["id"] for row in rows}) == len(rows)


def test_every_recipe_resolves_against_the_catalogue():
    recipes, links, problems = read_recipes(RECIPES_DIR, _catalogue())
    assert problems == []
    assert len(links) >= len(recipes)


def test_variants_point_at_a_base_recipe():
    recipes, _, _ = read_recipes(RECIPES_DIR, _catalogue())
    base_ids = {r["id"] for r in recipes if r["base_recipe_id"] is None}
    assert all(r["base_recipe_id"] in base_ids for r in recipes if r["base_recipe_id"])


def _write_recipe(directory: Path, ingredients: list[str]) -> None:
    lines = "\n".join(
        f"  - {{canonical_name: {name}, quantity: 1, unit: pcs, essential: true}}"
        for name in ingredients
    )
    (directory / "r.yaml").write_text(
        "id: 11111111-1111-4111-8111-111111111111\n"
        "title: Test\ncuisine: chinese\ntotal_minutes: 10\ndifficulty: 1\nservings: 2\n"
        f"ingredients:\n{lines}\nsteps:\n  - Cook.\n",
        encoding="utf-8",
    )


def test_diet_flags_are_shared_by_all_ingredients_and_allergens_are_pooled(tmp_path):
    _write_recipe(tmp_path, ["egg", "tomato", "soy sauce"])
    recipes, _, problems = read_recipes(tmp_path, _catalogue())
    assert problems == []
    # egg is not vegan, so the recipe is not vegan; everything else is shared
    assert "vegan" not in recipes[0]["diet_flags"]
    assert "vegetarian" in recipes[0]["diet_flags"]
    assert set(recipes[0]["allergens"]) == {"egg", "soy", "gluten"}


def test_an_unknown_ingredient_is_reported(tmp_path):
    _write_recipe(tmp_path, ["egg", "dragon fruit"])
    _, _, problems = read_recipes(tmp_path, _catalogue())
    assert any("dragon fruit" in problem for problem in problems)


def test_chicken_is_not_vegetarian_or_halal(tmp_path):
    _write_recipe(tmp_path, ["chicken thigh", "tomato"])
    recipes, _, _ = read_recipes(tmp_path, _catalogue())
    assert "vegetarian" not in recipes[0]["diet_flags"]
    assert "halal" not in recipes[0]["diet_flags"]
