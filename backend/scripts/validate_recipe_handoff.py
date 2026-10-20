"""Validate Role 5's recipe drafts and ingredient handoff without a database.

Run from backend: uv run python scripts/validate_recipe_handoff.py
Add --require-reviewed before release, or --ingredients-csv seed/ingredients.csv
when Role 2's authoritative ingredient catalogue is available.
"""

import argparse
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.common import Cuisine, Equipment, TasteTag  # noqa: E402

SEED_DIR = Path(__file__).resolve().parents[1] / "seed"


def nonempty(value: str) -> str:
    if not value or value != value.strip():
        raise ValueError("must be nonempty with no surrounding whitespace")
    return value


Text = Annotated[StrictStr, AfterValidator(nonempty)]
PositiveInt = Annotated[StrictInt, Field(gt=0)]
Quantity = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
Unit = Literal["g", "ml", "pcs"]


class SeedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Ingredient(SeedModel):
    canonical_name: Text
    quantity: Quantity | None = None
    unit: Unit | None = None
    coarse_amount: Text | None = None
    essential: StrictBool
    prep_note: Text | None = None

    @model_validator(mode="after")
    def check_amount(self):
        amount_fields = self.model_fields_set & {"quantity", "unit", "coarse_amount"}
        if amount_fields == {"quantity", "unit"}:
            if self.quantity is not None and self.unit is not None:
                return self
        elif amount_fields == {"coarse_amount"} and self.coarse_amount is not None:
            return self
        raise ValueError("give quantity + unit OR coarse_amount; never mix them or use null")


class Recipe(SeedModel):
    id: UUID
    title: Text
    variant_of: UUID | None
    variant_label: Text | None = None
    cuisine: Cuisine
    total_minutes: PositiveInt
    active_minutes: PositiveInt
    difficulty: Annotated[StrictInt, Field(ge=1, le=3)]
    servings: PositiveInt
    equipment: list[Equipment]
    taste_tags: list[TasteTag]
    ingredients: Annotated[list[Ingredient], Field(min_length=1)]
    steps: Annotated[list[Text], Field(min_length=1)]
    source: Text
    reviewed: StrictBool

    @model_validator(mode="after")
    def check_recipe(self):
        if self.active_minutes > self.total_minutes:
            raise ValueError("active_minutes must not exceed total_minutes")
        if self.variant_of is not None and self.variant_label is None:
            raise ValueError("a variant requires variant_label")
        for label, values in (
            ("ingredient canonical names", [item.canonical_name for item in self.ingredients]),
            ("equipment", self.equipment),
            ("taste_tags", self.taste_tags),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"duplicate {label}")
        return self


class PlanEntry(SeedModel):
    slug: Text
    title: Text
    status: Literal["draft", "planned"]
    variant_of: Text | None
    ingredients: Annotated[list[Text], Field(min_length=1)]

    @model_validator(mode="after")
    def check_ingredients(self):
        if len(set(self.ingredients)) != len(self.ingredients):
            raise ValueError("duplicate ingredient canonical names in plan")
        return self


class Plan(SeedModel):
    recipes: Annotated[list[PlanEntry], Field(min_length=1)]


class IngredientRequest(SeedModel):
    canonical_name: Text
    aliases: list[Text]
    recipe_units: Annotated[list[Literal["g", "ml", "pcs", "coarse"]], Field(min_length=1)]
    notes: StrictStr

    @model_validator(mode="after")
    def check_lists(self):
        if len(set(self.recipe_units)) != len(self.recipe_units):
            raise ValueError("duplicate recipe_units")
        if len({alias.casefold() for alias in self.aliases}) != len(self.aliases):
            raise ValueError("duplicate aliases")
        return self


class Requests(SeedModel):
    ingredients: Annotated[list[IngredientRequest], Field(min_length=1)]


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    recipe_count: int = 0
    plan_count: int = 0
    ingredient_count: int = 0
    unreviewed_count: int = 0


def read_model(path: Path, model: type[SeedModel], result: ValidationResult):
    try:
        return model.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        result.errors.append(f"{path.name}: cannot read YAML: {exc}")
    except ValidationError as exc:
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"]) or "<root>"
            result.errors.append(f"{path.name}:{location}: {error['msg']}")
    return None


def check_variant_references(
    parents: dict[str, str | None], label: str, result: ValidationResult
) -> None:
    checked: set[str] = set()
    for start, parent in parents.items():
        if parent is not None and parent not in parents:
            result.errors.append(f"{label} {start}: unknown variant_of {parent}")
        if parent == start:
            result.errors.append(f"{label} {start}: variant_of cannot reference itself")
        trail: list[str] = []
        current = start
        while current in parents and current not in checked:
            if current in trail:
                cycle = trail[trail.index(current) :] + [current]
                result.errors.append(f"{label}: variant cycle: {' -> '.join(cycle)}")
                break
            trail.append(current)
            current = parents[current]
        checked.update(trail)


def read_catalogue(path: Path, result: ValidationResult) -> set[str] | None:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if "canonical_name" not in (reader.fieldnames or []):
                result.errors.append(f"{path.name}: missing canonical_name CSV column")
                return None
            return {row["canonical_name"] for row in reader}
    except (OSError, UnicodeError, csv.Error) as exc:
        result.errors.append(f"{path.name}: cannot read ingredient catalogue: {exc}")
        return None


def validate_handoff(
    seed_dir: Path = SEED_DIR,
    *,
    require_reviewed: bool = False,
    ingredients_csv: Path | None = None,
) -> ValidationResult:
    result = ValidationResult()
    paths = sorted((seed_dir / "recipes").glob("*.yaml"))
    result.recipe_count = len(paths)
    recipes: dict[str, Recipe] = {}
    ids: dict[UUID, str] = {}
    for path in paths:
        recipe = read_model(path, Recipe, result)
        if recipe is None:
            continue
        recipes[path.stem] = recipe
        if recipe.id in ids:
            result.errors.append(f"{path.name}: duplicate UUID also used by {ids[recipe.id]}.yaml")
        ids[recipe.id] = path.stem
        if not recipe.reviewed:
            result.unreviewed_count += 1
            if require_reviewed:
                result.errors.append(f"{path.name}: reviewed must be true for release")
    check_variant_references(
        {
            str(recipe.id): str(recipe.variant_of) if recipe.variant_of else None
            for recipe in recipes.values()
        },
        "recipe",
        result,
    )

    plan = read_model(seed_dir / "recipe_plan.yaml", Plan, result)
    requests = read_model(seed_dir / "ingredient_requests.yaml", Requests, result)
    if plan is not None:
        result.plan_count = len(plan.recipes)
        by_slug: dict[str, PlanEntry] = {}
        for entry in plan.recipes:
            if entry.slug in by_slug:
                result.errors.append(f"recipe_plan.yaml: duplicate slug {entry.slug}")
            by_slug[entry.slug] = entry
        check_variant_references(
            {entry.slug: entry.variant_of for entry in plan.recipes}, "recipe plan", result
        )
        draft_slugs = {entry.slug for entry in plan.recipes if entry.status == "draft"}
        file_slugs = {path.stem for path in paths}
        for slug in sorted(draft_slugs - file_slugs):
            result.errors.append(f"recipe_plan.yaml: draft {slug} has no recipe file")
        for slug in sorted(file_slugs - draft_slugs):
            result.errors.append(f"{slug}.yaml: recipe file must have a draft entry in recipe_plan")
        for slug, recipe in recipes.items():
            if slug not in by_slug:
                continue
            entry = by_slug[slug]
            if entry.title != recipe.title:
                result.errors.append(f"{slug}.yaml: title does not match recipe_plan")
            if set(entry.ingredients) != {item.canonical_name for item in recipe.ingredients}:
                result.errors.append(f"{slug}.yaml: ingredient set does not match recipe_plan")
            actual_parent = ids.get(recipe.variant_of) if recipe.variant_of else None
            if entry.variant_of != actual_parent:
                result.errors.append(f"{slug}.yaml: variant_of does not match recipe_plan")

    if requests is not None:
        result.ingredient_count = len(requests.ingredients)
        by_name: dict[str, IngredientRequest] = {}
        names_and_aliases: dict[str, str] = {}
        for request in requests.ingredients:
            name = request.canonical_name
            if name in by_name:
                result.errors.append(f"ingredient_requests.yaml: duplicate canonical_name {name}")
            by_name[name] = request
            for token in [name, *request.aliases]:
                previous = names_and_aliases.setdefault(token.casefold(), name)
                if previous != name:
                    result.errors.append(
                        f"ingredient_requests.yaml: name/alias {token!r} collides "
                        f"between {previous!r} and {name!r}"
                    )
        if plan is not None:
            planned_names = {name for entry in plan.recipes for name in entry.ingredients}
            for name in sorted(planned_names - by_name.keys()):
                result.errors.append(f"ingredient_requests.yaml: missing planned ingredient {name}")
            for name in sorted(by_name.keys() - planned_names):
                result.errors.append(f"ingredient_requests.yaml: unused ingredient {name}")
        for slug, recipe in recipes.items():
            for item in recipe.ingredients:
                request = by_name.get(item.canonical_name)
                if request is None:
                    result.errors.append(
                        f"{slug}.yaml: ingredient {item.canonical_name} missing from requests"
                    )
                elif (item.unit or "coarse") not in request.recipe_units:
                    result.errors.append(
                        f"{slug}.yaml: unit {item.unit or 'coarse'} for {item.canonical_name} "
                        "missing from ingredient_requests.recipe_units"
                    )

    if ingredients_csv is not None:
        catalogue_names = read_catalogue(ingredients_csv, result)
        if catalogue_names is not None:
            used_names = {
                item.canonical_name for recipe in recipes.values() for item in recipe.ingredients
            }
            for name in sorted(used_names - catalogue_names):
                result.errors.append(
                    f"{ingredients_csv.name}: recipe ingredient {name!r} has no canonical row"
                )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-dir", type=Path, default=SEED_DIR)
    parser.add_argument("--require-reviewed", action="store_true")
    parser.add_argument("--ingredients-csv", type=Path)
    args = parser.parse_args()
    result = validate_handoff(
        args.seed_dir,
        require_reviewed=args.require_reviewed,
        ingredients_csv=args.ingredients_csv,
    )
    if result.errors:
        print(f"Recipe handoff failed ({len(result.errors)} errors):")
        for error in result.errors:
            print(f"- {error}")
        return 1
    print(
        f"Recipe handoff valid: {result.recipe_count} recipe files, "
        f"{result.plan_count} planned entries, {result.ingredient_count} requested ingredients; "
        f"{result.unreviewed_count} drafts still need human review."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
