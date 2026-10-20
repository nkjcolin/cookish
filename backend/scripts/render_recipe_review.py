"""Render the human review guide from recipe YAML and research notes.

Run from backend: uv run python scripts/render_recipe_review.py
Use --check to detect a stale guide without writing it.
"""

import argparse
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "backend" / "seed"
OUTPUT = ROOT / "docs" / "recipe-review.md"


def read_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def render(seed: Path = SEED) -> str:
    plan = read_yaml(seed / "recipe_plan.yaml")["recipes"]
    notes = read_yaml(seed / "recipe_review.yaml")
    recipes = {path.stem: read_yaml(path) for path in sorted((seed / "recipes").glob("*.yaml"))}
    if set(recipes) != set(notes["recipes"]):
        raise ValueError("Every recipe needs exactly one research/review record")
    if set(recipes) != {entry["slug"] for entry in plan}:
        raise ValueError("Review order must cover every recipe")
    by_id = {recipe["id"]: slug for slug, recipe in recipes.items()}
    number = {entry["slug"]: index for index, entry in enumerate(plan, start=1)}
    tags = Counter(tag for recipe in recipes.values() for tag in recipe["taste_tags"])
    cuisines = Counter(recipe["cuisine"] for recipe in recipes.values())
    ingredients = Counter(
        item["canonical_name"] for recipe in recipes.values() for item in recipe["ingredients"]
    )
    bases = sum(recipe["variant_of"] is None for recipe in recipes.values())
    quick = sum(recipe["total_minutes"] <= 30 for recipe in recipes.values())
    pending = sum(not recipe["reviewed"] for recipe in recipes.values())
    lines = [
        "# Cookish recipe catalogue: Wenlong's review pack",
        "",
        f"**{len(recipes)} complete recipes: {bases} base meals and "
        f"{len(recipes) - bases} variants, using {len(ingredients)} canonical ingredients. "
        f"{pending} still await human review.**",
        "",
        "This is the coursework recipe catalogue. The SPEC calls for "
        "**40–60 human-reviewed recipes including variants**; "
        f"the number marked human-reviewed is currently {len(recipes) - pending}. "
        "Recipe quantities and "
        "instructions are original AI-assisted project drafts. Named creator pages informed "
        "dish concepts and techniques; they do not validate these exact formulations. "
        "There have been no cooking trials, nutrition calculations or user acceptance tests.",
        "",
        "## Why this selection fits Cookish",
        "",
        "- **Meals that Shop can count:** every suggestion includes rice, noodles or potato "
        "instead of quietly assuming the user will add a separate staple. All base quantities "
        "serve two. This is a portion-design choice, not a claim of nutritional completeness.",
        "- **A manageable shared pantry:** rice, eggs, tofu, chicken and common vegetables "
        "recur across dishes. The 42-name ingredient list stays small enough for Role 2 to "
        "catalogue and Role 4 to match; it is not a price-verified shopping list.",
        "- **Useful recommendation choices:** there are distinct soups, rice dishes, "
        "noodles, curries and assembled meals, with meaningful less-oil, quicker, "
        "extra-vegetable and added-protein variants.",
        "- **Singapore home-cooking context:** familiar rice/noodle/vegetable combinations "
        "are prioritised. The mix is weighted toward Chinese home cooking, with Indian, "
        "Malay-inspired and other options; it is not representative coverage of every cuisine. "
        "Simplified dishes are named plainly rather than claimed to be authentic versions.",
        "- **Explicit appliance constraints:** stove meals dominate; one microwave-only "
        "meal, one rice-cooker-only meal and a no-appliance assembled meal exercise equipment "
        "filtering. Rice-cooker compatibility needs a model-specific check.",
        "",
        "The selection is suitable as a bounded prototype catalogue. It cannot guarantee "
        "results for every combination of allergies, dietary restrictions, equipment and "
        "time limits. Those cases still need the agreed no-result/relaxation behaviour. "
        "A load test with more simultaneous sessions can reuse this catalogue: increasing "
        "recipe count does not by itself demonstrate service scale-out.",
        "",
        "## Review priorities",
        "",
        "1. Review the shortlist below for dishes you actually want to include. Check "
        "the simplified flavours, repetition, portions and the choice of cod and soba "
        "against your intended users' budgets and preferences.",
        "2. Open each numbered recipe for its ingredients, method, reference scope and "
        "specific review questions. Ingredients marked optional still participate in "
        "stored-recipe dietary/allergen checks under the current contract.",
        "3. Trial the appliance-specific meals, steamed custards, low-oil methods and "
        "rice dishes first. All timings are estimates for two servings. Larger portions "
        "may need more cookware or time, even when ingredient quantities scale.",
        "4. Record reviewer, date, corrections and any cooking-trial evidence in the "
        "review PR. Set reviewed: true only for recipes actually reviewed; an automated "
        "schema check cannot approve culinary quality.",
        "",
        "Freshly cooked rice time is included where uncooked rice is an ingredient. "
        "Recipes listing **cooked rice** assume it is already prepared; their times exclude "
        "its original cooking and cooling. The cold salad requires safely chilled rice. "
        "No raw/cooked rice yield conversion is assumed.",
        "",
        "## Coverage and authoring rules",
        "",
        f"- {quick} meals are estimated at 30 minutes or less; "
        f"{len(recipes) - quick} need longer. Porridge takes about 60 minutes.",
        "- Cuisine labels: "
        + ", ".join(f"{name} {count}" for name, count in sorted(cuisines.items()))
        + ". These are catalogue groupings, not authenticity certifications.",
        f"- low_oil: {tags['low_oil']} recipes, each with at most **5 ml of added cooking "
        "oils per two servings**, including sesame oil. This does not mean low total fat.",
        f"- vegetable_rich: {tags['vegetable_rich']} recipes, each with at least **300 g "
        "of counted vegetables per two servings**. Counted here: bok choy, broccoli, cabbage, "
        "carrot, cauliflower, chye sim, cucumber, fresh shiitake, long bean, pumpkin, "
        "spinach, tomato and water spinach. Potato, peas, pulses, rice and aromatics "
        "(including onion, garlic, ginger and spring onion) "
        "are excluded from this editorial threshold.",
        f"- high_protein: {tags['high_protein']} explicit **added-protein variants only**: "
        "chicken added to egg fried rice, eggs added to vegetable bee hoon, and tofu added "
        "to steamed egg. The existing enum is used as an internal adjustment marker. "
        "It is not a measured high-protein nutrition claim; absence does not mean a dish "
        "is low in protein. Swapping tofu for chicken does not automatically earn this tag.",
        "- light, rich, spicy and soupy describe the drafted cooking style or texture. "
        "Diet suitability and allergens must come from Role 2's authoritative ingredient "
        "metadata, including sauces, noodles and optional ingredients.",
        "",
        "These rules make the authored examples consistent; the recommendation services "
        "and learning updates still need implementation. A variant relationship alone "
        "does not prove that it satisfies every adjustment: compare actual time, tags and "
        "hard constraints.",
        "",
        "## Shortlist",
        "",
        "| # | Meal | Estimated total / active minutes | Relationship |",
        "|---|---|---|---|",
    ]
    approval = notes.get("human_content_review")
    if approval:
        lines[6:6] = [
            "## Human content approval",
            "",
            f"**{approval['reviewer']} approved all {approval['recipe_count']} recipes "
            f"on {approval['date']}**, covering recipe content at commit "
            f"`{approval['recipe_commit']}`.",
            "",
            f"> {approval['statement']}",
            "",
            approval["scope"],
            "",
            "Approval was given in the project chat and recorded in recipe_review.yaml "
            "and the review PR. Later content changes need their own review.",
            "",
        ]
    for entry in plan:
        slug = entry["slug"]
        recipe = recipes[slug]
        parent = recipe["variant_of"]
        relationship = (
            "Base"
            if parent is None
            else f"{recipe['variant_label']} (#{number[by_id[parent]]:02d})"
        )
        lines.append(
            f"| {number[slug]:02d} | [{recipe['title']}](#{slug}) | "
            f"{recipe['total_minutes']} / {recipe['active_minutes']} | {relationship} |"
        )
    lines += [
        "",
        "## Shared food-handling references",
        "",
        "These sources inform general handling guidance; they are not endorsements of "
        "the recipes or substitutes for cooking trials.",
        "",
        "- [SFA: Fried Rice Syndrome](https://www.sfa.gov.sg/food-safety-tips/"
        "food-risk-concerns/risk-at-a-glance/fried-rice-syndrome): promptly chill cooked "
        "rice below 4°C. Reheating cannot reliably remove hazards caused by poor storage.",
        "- [SFA: Food Safety Tips](https://www.sfa.gov.sg/food-safety-tips/"
        "safe-food-practices/food-safety-tips): thorough cooking, prompt storage, and "
        "reheating guidance. Drafts use a 75°C-for-two-minutes thermometer check "
        "where specified; microwave heating needs stirring and checks in several places.",
        "- [SFA: December 2024 food safety advisory](https://www.sfa.gov.sg/docs/"
        "default-source/circulars/others/2024/"
        "advisory-on-food-safety-practices-for-food-establishments_dec-24.pdf): "
        "temperature/time guidance used as the conservative drafting benchmark for "
        "raw meat and fish. Actual times depend on equipment, portion and thickness.",
        "",
        f"Reference pages accessed for this research: **{notes['reference_access_date']}**. "
        "Dish-specific creator references and their limited use appear in every card below. "
        "The project does not import source photographs, ratings or nutrition panels, "
        "and does not assert a licence to redistribute third-party recipe text.",
        "",
    ]
    for entry in plan:
        slug = entry["slug"]
        recipe = recipes[slug]
        review = notes["recipes"][slug]
        equipment = ", ".join(recipe["equipment"]) or "none (prepared ingredients)"
        lines += [
            f'<a id="{slug}"></a>',
            "",
            f"## {number[slug]:02d}. {recipe['title']}",
            "",
            f"**{recipe['servings']} servings · {recipe['total_minutes']} min total / "
            f"{recipe['active_minutes']} min active · equipment: {equipment}**",
            "",
            f"**Why include it:** {review['rationale']}",
            "",
            f"**Variant/design choice:** {review['adjustment_note']}",
            "",
            "**Tags:** " + ", ".join(recipe["taste_tags"]) + ".",
            "",
            "| Ingredient | Amount for two | Preparation / optionality |",
            "|---|---|---|",
        ]
        for item in recipe["ingredients"]:
            amount = (
                f"{item['quantity']:g} {item['unit']}"
                if "quantity" in item
                else item["coarse_amount"]
            )
            preparation = item.get("prep_note", "")
            if not item["essential"]:
                preparation = "Optional. " + preparation
            lines.append(f"| {item['canonical_name']} | {amount} | {preparation or '—'} |")
        lines += ["", "**Method**", ""]
        lines += [f"{index}. {step}" for index, step in enumerate(recipe["steps"], start=1)]
        lines += ["", "**Research references**", ""]
        lines += [
            f"- [{ref['title']}]({ref['url']}) — {ref['usage']}" for ref in review["references"]
        ]
        lines += [
            "",
            f"**Review focus:** {review['review_focus']}",
            "",
            "- [ ] Ingredient forms, quantities, portions and flavour reviewed.",
            "- [ ] Equipment, timing, cooking steps and handling reviewed.",
            "- [ ] Variant differences and tags make sense for the project.",
            "",
            "Content approval is recorded above when available. Record later changes and "
            "any cooking-trial evidence in the review PR. These checkboxes are a checklist, "
            "not the evidence record.",
            "",
            f"[Recipe YAML](../backend/seed/recipes/{slug}.yaml) · "
            f"reviewed: {str(recipe['reviewed']).lower()}",
            "",
        ]
    lines += [
        "## Ingredient reuse",
        "",
        "Counts include variants and optional ingredients. This shows catalogue reuse, "
        "not expected purchase quantities or required stock.",
        "",
        "| Canonical ingredient | Recipes using it |",
        "|---|---|",
    ]
    lines += [f"| {name} | {count} |" for name, count in sorted(ingredients.items())]
    lines += [
        "",
        "Generated from the recipe YAML files, recipe_plan.yaml and recipe_review.yaml. "
        "Update those sources and run `uv run python scripts/render_recipe_review.py` "
        "from backend/ to refresh this guide.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Reject a stale generated guide")
    args = parser.parse_args()
    content = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
            print("Recipe review guide is stale; run scripts/render_recipe_review.py")
            return 1
        print("Recipe review guide is current.")
        return 0
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
