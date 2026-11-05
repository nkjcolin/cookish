"""Development quality review using real seed content and declared synthetic kitchens.

Run from backend: python -m evaluation.catalogue_review --output PATH
This is neither held-out evaluation nor a taste, food-safety or user study.
"""

import argparse
import hashlib
import json
import platform
import subprocess
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.clock import SINGAPORE
from app.db import models as m
from app.reco import new_session, new_shop_session, plan_shop, skip_current, suggest
from app.reco.config import DEFAULT_CONFIG, DEFAULT_SHOP_CONFIG
from app.reco.cook import filter_recipes
from app.reco.inventory import assess_ingredients
from app.reco.models import HardConstraints
from app.schemas.common import Allergen, Diet, Equipment
from app.schemas.identity import Preferences
from app.services.recommendation_inputs import (
    ingredient_metadata,
    purchase_metadata,
    recipe_candidate,
)
from app.services.stock_events import item_view
from seed.demo import PREFERENCES, build_items
from seed.seed import INGREDIENTS_CSV, RECIPES_DIR, read_ingredients, read_recipes

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 5, 12, tzinfo=SINGAPORE)


def load_catalogue():
    rows, errors = read_ingredients(INGREDIENTS_CSV)
    recipes, links, problems = read_recipes(RECIPES_DIR, rows)
    if errors or problems:
        raise ValueError(errors + problems)
    orm = {row["id"]: m.Ingredient(**row) for row in rows}
    metadata = {key: ingredient_metadata(row) for key, row in orm.items()}
    purchases = {key: purchase_metadata(row) for key, row in orm.items()}
    candidates = tuple(
        recipe_candidate(
            m.Recipe(**row),
            [m.RecipeIngredient(**line) for line in links if line["recipe_id"] == row["id"]],
            metadata,
            False,
        )
        for row in recipes
        if row["reviewed"]
    )
    return rows, orm, candidates, metadata, purchases


def kitchens(rows, orm):
    demo = build_items({r["canonical_name"]: r for r in rows}, NOW.date(), NOW)
    full = [
        dict(
            id=uuid5(NAMESPACE_URL, "catalogue-review/" + str(key)),
            ingredient_id=key,
            display_name=row.canonical_name,
            count=100 if row.countable else None,
            unit=row.default_unit if row.countable else None,
            remaining_state="enough",
            storage=row.default_storage,
            source="manual",
            acquired_at=NOW.date(),
            # Deliberate synthetic valid dates isolate quantity/unit behavior.
            label_date=NOW.date() + timedelta(days=7),
            label_date_kind="use_by",
            last_confirmed_at=NOW,
            revision=1,
        )
        for key, row in orm.items()
    ]
    return {
        "empty": [],
        "demo": [
            item_view(m.InventoryItem(**r), orm[r["ingredient_id"]], NOW.date(), NOW) for r in demo
        ],
        "all_catalogue_units": [
            item_view(m.InventoryItem(**r), orm[r["ingredient_id"]], NOW.date(), NOW) for r in full
        ],
    }


def preferences(**changes):
    return Preferences(
        **{
            **PREFERENCES,
            "equipment": list(Equipment),
            "cuisines": [],
            "max_cook_minutes": 60,
            "max_difficulty": 3,
            "updated_at": NOW,
            **changes,
        }
    )


def blockers(recipe, inventory, metadata, people):
    return [
        {"ingredient": line.name, "status": line.status.value, "amount": line.amount}
        for line in assess_ingredients(recipe, inventory, metadata, people, as_of=NOW)
        if line.essential
        and (
            line.status in {"unknown", "check", "missing"}
            or (metadata[line.ingredient_id].countable and line.status == "low")
        )
    ]


def cook_review(name, prefs, inventory_name, inventory, recipes, metadata):
    safe = filter_recipes(recipes, HardConstraints.from_preferences(prefs), metadata)
    eligible = [
        r
        for r in safe
        if (prefs.max_cook_minutes is None or r.total_minutes <= prefs.max_cook_minutes)
        and (prefs.max_difficulty is None or r.difficulty <= prefs.max_difficulty)
    ]
    ready = [r for r in eligible if not blockers(r, inventory, metadata, prefs.last_cook_people)]
    session, suggestions = new_session(prefs), []
    for _ in range(5):
        result = suggest(recipes, inventory, prefs, session, metadata, as_of=NOW)
        if result.selected is None:
            break
        recipe = result.selected.recipe
        suggestions.append(
            dict(
                id=str(recipe.id),
                title=recipe.title,
                family=str(recipe.base_recipe_id or recipe.id),
                minutes=recipe.total_minutes,
                cuisine=recipe.cuisine.value,
                missing_fallback=result.missing_essential_fallback,
                selection_blockers=blockers(recipe, inventory, metadata, session.people),
                score_terms=result.selected.score.terms,
            )
        )
        session = skip_current(result.session)
    checked_inventory = [
        item.model_copy(update={"remaining_state": "enough", "last_confirmed_at": NOW})
        for item in inventory
    ]
    first_recipe = next(
        (r for r in recipes if suggestions and str(r.id) == suggestions[0]["id"]), None
    )
    return dict(
        profile=name,
        kitchen=inventory_name,
        preferences=prefs.model_dump(mode="json"),
        hard_eligible=len(safe),
        within_time_and_difficulty=len(eligible),
        ready_to_select=len(ready),
        first_five=suggestions,
        distinct_families_in_first_five=len({r["family"] for r in suggestions}),
        first_after_have_it_blockers=(
            blockers(first_recipe, checked_inventory, metadata, prefs.last_cook_people)
            if first_recipe is not None
            else []
        ),
    )


def shop_review(name, prefs, inventory, recipes, metadata, purchases, people, meals):
    plan = plan_shop(
        recipes,
        inventory,
        prefs,
        new_shop_session(prefs, people, meals),
        metadata,
        purchases,
        as_of=NOW,
    )
    unbuyable = []
    for recipe in plan.planned_meals:
        for line in assess_ingredients(recipe, inventory, metadata, people, as_of=NOW):
            if line.essential and not line.is_staple and not purchases[line.ingredient_id].buyable:
                if line.status not in {"have", "low"}:
                    unbuyable.append(
                        dict(recipe=recipe.title, ingredient=line.name, status=line.status.value)
                    )
    return dict(
        profile=name,
        preferences=prefs.model_dump(mode="json"),
        requested_meals=meals,
        people=people,
        planned_meals=[
            dict(
                id=str(r.id),
                title=r.title,
                cuisine=r.cuisine.value,
                family=str(r.base_recipe_id or r.id),
            )
            for r in plan.planned_meals
        ],
        score_terms=plan.score_terms,
        shopping_lines=[
            dict(
                ingredient=line.name,
                countable=metadata[line.ingredient_id].countable,
                amount=line.amount,
                needs_check=line.needs_check,
                suggested_packs=line.suggested_packs,
            )
            for line in plan.items
        ],
        essential_unavailable_nonbuyable=unbuyable,
    )


def run():
    rows, orm, recipes, metadata, purchases = load_catalogue()
    inventory = kitchens(rows, orm)
    profiles = [
        ("unrestricted", preferences()),
        ("stove_only", preferences(equipment=[Equipment.STOVE])),
        ("microwave_only", preferences(equipment=[Equipment.MICROWAVE])),
        ("no_equipment", preferences(equipment=[])),
    ]
    profiles += [(diet.value, preferences(diets=[diet])) for diet in Diet]
    profiles += [("avoid_" + a.value, preferences(allergens=[a])) for a in Allergen]
    profiles += [
        (f"max_{minutes}_minutes", preferences(max_cook_minutes=minutes))
        for minutes in (15, 20, 30)
    ]
    profiles += [
        (
            "avoid_soy_gluten_sesame",
            preferences(allergens=[Allergen.SOY, Allergen.GLUTEN, Allergen.SESAME]),
        )
    ]
    cook = [
        cook_review(
            name, prefs, "all_catalogue_units", inventory["all_catalogue_units"], recipes, metadata
        )
        for name, prefs in profiles
    ]
    cook += [
        cook_review("new_user_empty", preferences(), "empty", [], recipes, metadata),
        cook_review(
            "seeded_demo", preferences(**PREFERENCES), "demo", inventory["demo"], recipes, metadata
        ),
    ]
    shops = [
        shop_review(name, prefs, inventory[kitchen], recipes, metadata, purchases, people, meals)
        for name, prefs, kitchen, people, meals in [
            ("empty_3", preferences(), "empty", 2, 3),
            ("empty_7", preferences(), "empty", 2, 7),
            ("family_4_7", preferences(), "empty", 4, 7),
            ("vegan_7", preferences(diets=[Diet.VEGAN]), "empty", 2, 7),
            ("halal_7", preferences(diets=[Diet.HALAL]), "empty", 2, 7),
            ("microwave_7", preferences(equipment=[Equipment.MICROWAVE]), "empty", 2, 7),
            ("demo_3", preferences(**PREFERENCES), "demo", 2, 3),
        ]
    ]
    mismatches = []
    for recipe in recipes:
        for line in recipe.ingredients:
            ingredient = orm[line.ingredient_id]
            if ingredient.countable and line.unit != ingredient.default_unit:
                mismatches.append(
                    dict(
                        recipe=recipe.title,
                        ingredient=line.name,
                        essential=line.essential,
                        recipe_unit=line.unit,
                        inventory_unit=ingredient.default_unit,
                        purchase_unit=purchases[line.ingredient_id].purchase_unit_measure,
                    )
                )
    source_files = sorted(
        [
            INGREDIENTS_CSV,
            *RECIPES_DIR.glob("*.yaml"),
            *(ROOT / "backend/app/reco").glob("*.py"),
            Path(__file__),
            ROOT / "backend/app/services/recommendation_inputs.py",
            ROOT / "backend/seed/seed.py",
            ROOT / "backend/seed/demo.py",
            ROOT / "backend/app/services/stock_events.py",
            ROOT / "backend/app/services/freshness.py",
            ROOT / "backend/app/db/models.py",
            ROOT / "backend/app/clock.py",
            *(ROOT / "backend/app/schemas").glob("*.py"),
        ]
    )
    hashes = {
        str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(
            p.read_text(encoding="utf-8").encode()
        ).hexdigest()
        for p in source_files
    }

    def git(*args):
        return subprocess.check_output(
            ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args], cwd=ROOT, text=True
        ).strip()

    # Check returned hard constraints directly against raw catalogue rows,
    # separately from the engine's filter and its CatalogIngredient mapping.
    raw_by_id = {str(row["id"]): row for row in rows}
    recipes_by_id = {str(recipe.id): recipe for recipe in recipes}
    for profile in [*cook, *shops]:
        prefs = profile["preferences"]
        for chosen in profile.get("first_five", profile.get("planned_meals", [])):
            recipe = recipes_by_id[chosen["id"]]
            assert {e.value for e in recipe.equipment} <= set(prefs["equipment"])
            for ingredient in recipe.ingredients:
                raw = raw_by_id[str(ingredient.ingredient_id)]
                assert not set(raw["allergen_tags"]) & set(prefs["allergens"])
                assert set(prefs["diets"]) <= set(raw["diet_flags"])
    return dict(
        kind="real-catalogue development quality review",
        held_out_executed=0,
        fixed_clock=NOW.isoformat(),
        source_commit=git("rev-parse", "HEAD"),
        source_dirty=bool(git("status", "--porcelain", "--untracked-files=normal")),
        runtime={
            "python": platform.python_version(),
            "packages": {name: version(name) for name in ("pydantic", "sqlalchemy", "pyyaml")},
        },
        source_sha256_lf_utf8=hashes,
        scoring=asdict(DEFAULT_CONFIG),
        shop_config=asdict(DEFAULT_SHOP_CONFIG),
        assumptions={
            "all_catalogue_units": (
                "100 of each counted default unit; all state items enough; synthetic valid "
                "seven-day labels; confirmed now. No grams/count conversion assumed."
            ),
            "empty": "No stock, feedback or stars; absent staples assumed by existing policy.",
            "demo": "Role 2 demo kitchen, reconstructed at the fixed clock.",
            "readiness": "Mirrors selection blockers, not a cooking/portion/safety guarantee.",
            "coverage": "Development probes, not population estimates or held-out tests.",
            "have_it_probe": (
                "Set existing batches to enough and confirmed now; preserve counts/units/dates. "
                "Missing batches remain absent."
            ),
        },
        catalogue=dict(
            recipes=len(recipes),
            families=len({r.base_recipe_id or r.id for r in recipes}),
            ingredients=len(rows),
            cuisines=dict(Counter(r.cuisine.value for r in recipes)),
        ),
        unit_mismatches=mismatches,
        cook=cook,
        shop=shops,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "catalogue": result["catalogue"],
                "cook": [
                    {
                        k: p[k]
                        for k in (
                            "profile",
                            "hard_eligible",
                            "within_time_and_difficulty",
                            "ready_to_select",
                        )
                    }
                    for p in result["cook"]
                ],
                "shop": [
                    dict(
                        profile=p["profile"],
                        planned=len(p["planned_meals"]),
                        requested=p["requested_meals"],
                        check_lines=sum(i["needs_check"] for i in p["shopping_lines"]),
                        unbuyable=p["essential_unavailable_nonbuyable"],
                    )
                    for p in result["shop"]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
