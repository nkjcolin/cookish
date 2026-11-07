"""Loads the ingredient catalogue and the recipes into the database. Role 2 owns this file.

    uv run python -m seed.seed          # from backend/

Safe to run again. Rows are matched by the fixed UUID written in each file, so a second run
updates what changed and inserts what is new. Nothing is ever deleted: inventory items,
ratings and stars point at these rows.

All files are checked first and every problem is reported together. If there is any problem,
nothing is written. The write itself is one transaction, so it is all or nothing.

What it works out for you (recipe files do not contain these):
- diet_flags: the diets that EVERY ingredient of the recipe is suitable for.
- allergens: every allergen that ANY ingredient contains.
Optional ingredients count too: leaving one out silently would be a dietary substitution.
"""

import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from app.db.models import Ingredient, Recipe, RecipeIngredient
from app.db.session import transaction
from app.schemas.common import (
    Allergen,
    Cuisine,
    Diet,
    Equipment,
    IngredientCategory,
    Storage,
    TasteTag,
)

SEED_DIR = Path(__file__).resolve().parent
INGREDIENTS_CSV = SEED_DIR / "ingredients.csv"
RECIPES_DIR = SEED_DIR / "recipes"

CSV_COLUMNS = [
    "id",
    "canonical_name",
    "aliases",
    "category",
    "countable",
    "default_unit",
    "allergen_tags",
    "diet_flags",
    "shelf_life_days_pantry",
    "shelf_life_days_fridge",
    "shelf_life_days_freezer",
    "default_storage",
    "is_staple",
    "purchase_unit",
    "purchase_unit_size",
    "purchase_unit_measure",
    "grams_per_piece",
]
SHELF_LIFE_BY_STORAGE = {
    "pantry": "shelf_life_days_pantry",
    "fridge": "shelf_life_days_fridge",
    "freezer": "shelf_life_days_freezer",
}


class SeedError(Exception):
    """One or more problems in the seed files. `problems` lists every one of them."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__(f"{len(problems)} problem(s) in the seed files")


def _allowed(enum: Any) -> set[str]:
    return {member.value for member in enum}


def _split(cell: str) -> list[str]:
    return [part.strip() for part in cell.split("|") if part.strip()]


def _uuid(value: Any, where: str, problems: list[str]) -> UUID | None:
    try:
        return UUID(str(value))
    except ValueError:
        problems.append(f"{where}: id {value!r} is not a valid UUID")
        return None


def _in(values: list[str], enum: Any, what: str, where: str, problems: list[str]) -> None:
    unknown = sorted(set(values) - _allowed(enum))
    if unknown:
        problems.append(f"{where}: unknown {what} {unknown}; allowed: {sorted(_allowed(enum))}")


# ----------------------------------------------------------------------------- ingredients


def read_ingredients(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse and check ingredients.csv. Returns (rows shaped like the table, problems)."""
    problems: list[str] = []
    if not path.exists():
        return [], [f"{path} does not exist"]

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != CSV_COLUMNS:
            return [], [
                f"ingredients.csv columns must be exactly {CSV_COLUMNS}, got {reader.fieldnames}"
            ]
        raw_rows = list(reader)

    rows: list[dict[str, Any]] = []
    seen_ids: set[UUID] = set()
    seen_names: set[str] = set()
    owner_of_alias: dict[str, str] = {}

    for line_no, raw in enumerate(raw_rows, start=2):
        name = raw["canonical_name"].strip()
        where = f"ingredients.csv line {line_no} ({name or 'no name'})"
        if not name:
            problems.append(f"{where}: canonical_name is empty")
            continue
        if name in seen_names:
            problems.append(f"{where}: canonical_name appears twice")
        seen_names.add(name)

        row_id = _uuid(raw["id"], where, problems)
        if row_id is not None:
            if row_id in seen_ids:
                problems.append(f"{where}: id {row_id} is used by another row")
            seen_ids.add(row_id)

        aliases = _split(raw["aliases"])
        for alias in aliases:
            key = alias.lower()
            if key in owner_of_alias and owner_of_alias[key] != name:
                problems.append(
                    f"{where}: alias {alias!r} is also an alias of {owner_of_alias[key]!r}"
                )
            owner_of_alias[key] = name

        allergens = _split(raw["allergen_tags"])
        diets = _split(raw["diet_flags"])
        _in(allergens, Allergen, "allergen", where, problems)
        _in(diets, Diet, "diet flag", where, problems)
        if raw["category"] not in _allowed(IngredientCategory):
            problems.append(f"{where}: unknown category {raw['category']!r}")
        if raw["default_storage"] not in _allowed(Storage):
            problems.append(f"{where}: unknown default_storage {raw['default_storage']!r}")

        countable = _bool(raw["countable"], "countable", where, problems)
        is_staple = _bool(raw["is_staple"], "is_staple", where, problems)
        default_unit = raw["default_unit"].strip() or None
        if countable and default_unit is None:
            problems.append(f"{where}: a countable ingredient needs a default_unit")

        shelf: dict[str, int | None] = {}
        for column in SHELF_LIFE_BY_STORAGE.values():
            shelf[column] = _int(raw[column], column, where, problems)
        needed = SHELF_LIFE_BY_STORAGE.get(raw["default_storage"])
        if needed and shelf[needed] is None and not is_staple:
            problems.append(
                f"{where}: no {needed} although {raw['default_storage']} is the default storage"
            )

        purchase_unit = raw["purchase_unit"].strip() or None
        purchase_measure = raw["purchase_unit_measure"].strip() or None
        purchase_size = _decimal(raw["purchase_unit_size"], where, problems)
        given = [purchase_unit is not None, purchase_size is not None, purchase_measure is not None]
        if any(given) and not all(given):
            problems.append(
                f"{where}: purchase_unit, size and measure must be all set or all empty"
            )
        if purchase_size is not None and purchase_size <= 0:
            problems.append(f"{where}: purchase_unit_size must be above 0")
        if countable and purchase_measure is not None and purchase_measure != default_unit:
            problems.append(
                f"{where}: a counted ingredient is bought in its own unit ({default_unit}),"
                f" not {purchase_measure}"
            )

        # How recipes written in grams are counted against a kitchen kept in pieces.
        grams_per_piece = _decimal(raw["grams_per_piece"], where, problems, "grams_per_piece")
        if grams_per_piece is not None:
            if grams_per_piece <= 0:
                problems.append(f"{where}: grams_per_piece must be above 0")
            if not countable or default_unit != "pcs":
                problems.append(f"{where}: grams_per_piece is only for ingredients counted in pcs")

        rows.append(
            {
                "id": row_id,
                "canonical_name": name,
                "aliases": aliases,
                "category": raw["category"],
                "countable": countable,
                "default_unit": default_unit,
                "allergen_tags": allergens,
                "diet_flags": diets,
                **shelf,
                "default_storage": raw["default_storage"],
                "is_staple": is_staple,
                "purchase_unit": purchase_unit,
                "purchase_unit_size": purchase_size,
                "purchase_unit_measure": purchase_measure,
                "grams_per_piece": grams_per_piece,
            }
        )
    return rows, problems


def _bool(cell: str, column: str, where: str, problems: list[str]) -> bool:
    value = cell.strip().lower()
    if value not in ("true", "false"):
        problems.append(f"{where}: {column} must be true or false, got {cell!r}")
    return value == "true"


def _int(cell: str, column: str, where: str, problems: list[str]) -> int | None:
    if not cell.strip():
        return None
    try:
        number = int(cell)
    except ValueError:
        problems.append(f"{where}: {column} must be a whole number, got {cell!r}")
        return None
    if number < 0:
        problems.append(f"{where}: {column} cannot be negative")
    return number


def _decimal(
    cell: str, where: str, problems: list[str], column: str = "purchase_unit_size"
) -> Decimal | None:
    if not cell.strip():
        return None
    try:
        return Decimal(cell)
    except InvalidOperation:
        problems.append(f"{where}: {column} must be a number, got {cell!r}")
        return None


# ----------------------------------------------------------------------------- recipes


def read_recipes(
    recipes_dir: Path, ingredients: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    """Parse and check recipes/*.yaml against the catalogue.

    Returns (recipe rows, recipe_ingredient rows, problems). A recipe's diet_flags and
    allergens are worked out here from its ingredients.
    """
    problems: list[str] = []
    by_name = {row["canonical_name"]: row for row in ingredients}
    recipes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    seen_ids: dict[UUID, str] = {}

    for path in sorted(recipes_dir.glob("*.yaml")):
        where = f"recipes/{path.name}"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            problems.append(f"{where}: not a YAML mapping")
            continue

        for key in (
            "id",
            "title",
            "cuisine",
            "total_minutes",
            "difficulty",
            "servings",
            "ingredients",
            "steps",
        ):
            if data.get(key) in (None, "", []):
                problems.append(f"{where}: {key} is missing")

        recipe_id = _uuid(data.get("id"), where, problems)
        if recipe_id is not None:
            if recipe_id in seen_ids:
                problems.append(f"{where}: id is also used by {seen_ids[recipe_id]}")
            seen_ids[recipe_id] = path.name

        variant_of = None
        if data.get("variant_of"):
            variant_of = _uuid(data["variant_of"], f"{where} variant_of", problems)
            if not data.get("variant_label"):
                problems.append(f"{where}: a variant needs a variant_label")

        if data.get("cuisine") not in _allowed(Cuisine):
            problems.append(f"{where}: unknown cuisine {data.get('cuisine')!r}")
        equipment = list(data.get("equipment") or [])
        taste_tags = list(data.get("taste_tags") or [])
        _in(equipment, Equipment, "equipment", where, problems)
        _in(taste_tags, TasteTag, "taste tag", where, problems)
        if data.get("difficulty") not in (1, 2, 3):
            problems.append(f"{where}: difficulty must be 1, 2 or 3")
        for key in ("total_minutes", "servings"):
            if not isinstance(data.get(key), int) or data[key] <= 0:
                problems.append(f"{where}: {key} must be a whole number above 0")
        steps = data.get("steps") or []
        if not all(isinstance(step, str) and step.strip() for step in steps):
            problems.append(f"{where}: every step must be text")

        diet_sets: list[set[str]] = []
        allergen_sets: list[set[str]] = []
        seen_ingredients: set[str] = set()
        for item in data.get("ingredients") or []:
            name = item.get("canonical_name")
            ing = by_name.get(name)
            if ing is None:
                problems.append(f"{where}: ingredient {name!r} is not in ingredients.csv")
                continue
            if name in seen_ingredients:
                problems.append(f"{where}: ingredient {name!r} is listed twice")
            seen_ingredients.add(name)

            quantity, unit, coarse = (
                item.get("quantity"),
                item.get("unit"),
                item.get("coarse_amount"),
            )
            if coarse is None and (quantity is None or not unit):
                problems.append(f"{where}: {name} needs quantity and unit, or a coarse_amount")
            if quantity is not None and (not isinstance(quantity, int | float) or quantity <= 0):
                problems.append(f"{where}: {name} quantity must be a number above 0")
            # A counted ingredient is compared with the kitchen's count, so the recipe must be
            # in the same unit, or in grams that grams_per_piece turns into pieces.
            if quantity is not None and unit and ing["countable"]:
                convertible = unit == "g" and ing["grams_per_piece"] is not None
                if unit != ing["default_unit"] and not convertible:
                    problems.append(
                        f"{where}: {name} is counted in {ing['default_unit']}, so its amount"
                        f" must be in {ing['default_unit']} (or g, with grams_per_piece set"
                        f" in ingredients.csv), not {unit}"
                    )

            diet_sets.append(set(ing["diet_flags"]))
            allergen_sets.append(set(ing["allergen_tags"]))
            if recipe_id is not None:
                links.append(
                    {
                        "recipe_id": recipe_id,
                        "ingredient_id": ing["id"],
                        "quantity": None if quantity is None else Decimal(str(quantity)),
                        "unit": unit,
                        "coarse_amount": coarse,
                        "essential": bool(item.get("essential", True)),
                        "prep_note": item.get("prep_note"),
                    }
                )

        diets_for_all = set.intersection(*diet_sets) if diet_sets else set()
        allergens_in_any = set.union(*allergen_sets) if allergen_sets else set()
        recipes.append(
            {
                "id": recipe_id,
                "title": data.get("title"),
                "base_recipe_id": variant_of,
                "variant_label": data.get("variant_label"),
                "cuisine": data.get("cuisine"),
                "total_minutes": data.get("total_minutes"),
                "active_minutes": data.get("active_minutes"),
                "difficulty": data.get("difficulty"),
                "servings": data.get("servings"),
                "equipment": equipment,
                "taste_tags": taste_tags,
                "diet_flags": [d.value for d in Diet if d.value in diets_for_all],
                "allergens": [a.value for a in Allergen if a.value in allergens_in_any],
                "steps": steps,
                "source": data.get("source"),
                "reviewed": bool(data.get("reviewed", False)),
            }
        )

    ids = {r["id"] for r in recipes}
    base_ids = {r["id"] for r in recipes if r["base_recipe_id"] is None}
    for recipe in recipes:
        base = recipe["base_recipe_id"]
        if base is not None and base not in ids:
            problems.append(
                f"recipe {recipe['title']!r}: variant_of {base} is not a recipe in recipes/"
            )
        elif base is not None and base not in base_ids:
            problems.append(
                f"recipe {recipe['title']!r}: variant_of must point at a base recipe, not a variant"
            )
    return recipes, links, problems


# ----------------------------------------------------------------------------- writing


def _upsert(s: Any, model: Any, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    statement = insert(model).values(rows)
    changeable = {column: statement.excluded[column] for column in rows[0] if column != "id"}
    s.execute(statement.on_conflict_do_update(index_elements=["id"], set_=changeable))


def seed(
    ingredients_csv: Path = INGREDIENTS_CSV, recipes_dir: Path = RECIPES_DIR
) -> dict[str, int]:
    """Check every file, then write everything in one transaction."""
    ingredients, problems = read_ingredients(ingredients_csv)
    recipes, links, recipe_problems = read_recipes(recipes_dir, ingredients)
    problems += recipe_problems
    if problems:
        raise SeedError(problems)

    bases = [r for r in recipes if r["base_recipe_id"] is None]
    variants = [r for r in recipes if r["base_recipe_id"] is not None]
    with transaction() as s:
        _upsert(s, Ingredient, ingredients)
        _upsert(s, Recipe, bases)  # bases first: a variant points at its base
        _upsert(s, Recipe, variants)
        # A recipe's ingredient list is replaced as a whole, so removed lines disappear.
        s.execute(
            delete(RecipeIngredient).where(
                RecipeIngredient.recipe_id.in_([r["id"] for r in recipes])
            )
        )
        if links:
            s.execute(insert(RecipeIngredient).values(links))
    return {
        "ingredients": len(ingredients),
        "recipes": len(recipes),
        "variants": len(variants),
        "recipe_ingredients": len(links),
    }


def main() -> int:
    try:
        counts = seed()
    except SeedError as error:
        print("Seeding stopped, nothing was written. Fix these first:", file=sys.stderr)
        for problem in error.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(
        "Seeded {ingredients} ingredients and {recipes} recipes "
        "({variants} variants, {recipe_ingredients} recipe lines).".format(**counts)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
