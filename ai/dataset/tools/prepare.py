"""Prepare synthetic receipt specifications; never calls a model or edits backend files."""

import hashlib
import json
import math
import random
import re
from pathlib import Path

DATASET = Path(__file__).resolve().parents[1]
HERE = DATASET / "work/receipts/draft_20261024"
ROOT = DATASET.parent.parent
SEED = 20261024
SCENARIOS = ("enough", "missing_some", "below_half")


def read_recipe(path):
    """Read only the simple scalar fields used in these checked-in recipe fixtures."""
    text = path.read_text(encoding="utf-8")
    header, ingredient_text = text.split("\ningredients:\n", 1)
    ingredient_text = ingredient_text.split("\nsteps:\n", 1)[0]
    fields = {}
    for key in ("id", "title", "servings"):
        fields[key] = re.search(rf"^{key}: (.+)$", header, re.MULTILINE).group(1)
    ingredients = []
    for block in re.split(r"(?m)^- canonical_name: ", ingredient_text)[1:]:
        name = block.splitlines()[0].strip()
        if name == "water":
            continue
        quantity = re.search(r"(?m)^  quantity: ([0-9.]+)$", block)
        unit = re.search(r"(?m)^  unit: (g|ml|pcs)$", block)
        essential = re.search(r"(?m)^  essential: (true|false)$", block)
        if not all((quantity, unit, essential)):
            raise ValueError(f"Unsupported ingredient specification: {path}: {name}")
        ingredients.append(
            {
                "canonical_name": name,
                "required_count": float(quantity.group(1)),
                "unit": unit.group(1),
                "essential": essential.group(1) == "true",
            }
        )
    return {
        "recipe_id": fields["id"],
        "title": fields["title"],
        "servings": int(fields["servings"]),
        "source": str(path.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "ingredients": ingredients,
    }


def purchase_amount(item):
    name, needed = item["canonical_name"], item["required_count"]
    packs = {
        "egg": 6,
        "soy sauce": 150,
        "spring onion": 100,
        "uncooked rice": 500,
        "firm tofu": 400,
        "coconut milk": 250,
        "carrot": 500,
        "long bean": 250,
        "onion": 500,
        "garlic": 100,
        "ginger": 100,
        "turmeric powder": 50,
        "chilli paste": 100,
        "canola oil": 250,
        "salt": 500,
        "cabbage": 500,
        "chicken thigh": 500,
        "potato": 500,
        "lemon": 1,
        "black pepper": 50,
        "broccoli": 500,
        "rice vermicelli": 400,
        "cucumber": 300,
        "tomato": 500,
        "canned chickpea": 400,
        "cooked rice": 500,
        "soba noodle": 250,
        "sesame oil": 150,
    }
    return math.ceil(needed / packs[name]) * packs[name]


def price_for(name):
    return {"egg": 3.20, "soy sauce": 1.80, "spring onion": 0.75, "uncooked rice": 1.50}.get(
        name, 2.00
    )


def receipt_text(case_id, purchases, layout):
    lines = [
        "COOKISH TEST MART",
        "SYNTHETIC TEST RECEIPT",
        f"CASE {case_id}",
        "24 OCT 2026  12:00",
        "--------------------------------",
        "DESCRIPTION              SGD",
    ]
    for item in purchases:
        name = item["canonical_name"].upper()
        if name == "CANNED CHICKPEA":
            name = "CHICKPEAS DRAINED"
        quantity = f"{item['count']:g} {item['unit'].upper()}"
        description = f"{name:<23} {item['price_sgd']:.2f}"
        if layout == "leading":
            lines.extend([f"  QTY {quantity}", description])
        elif layout == "inline":
            lines.extend([name, f"  QTY {quantity:<14} {item['price_sgd']:.2f}"])
        else:
            lines.extend([description, f"  QTY {quantity}"])
    total = sum(item["price_sgd"] for item in purchases)
    lines.extend(
        [
            "--------------------------------",
            f"TOTAL SGD               {total:.2f}",
            f"CASH                    {total:.2f}",
            "CHANGE                  0.00",
            "TEST DATA - NOT FOR CLAIMS",
            "END",
        ]
    )
    return "\n".join(lines)


def main():
    HERE.mkdir(parents=True, exist_ok=True)
    recipes = [
        read_recipe(path)
        for path in random.Random(SEED).sample(
            sorted((ROOT / "backend/seed/recipes").glob("*.yaml")), 10
        )
    ]
    cases = []
    for number, recipe in enumerate(recipes, 1):
        essential = [i for i in recipe["ingredients"] if i["essential"]]
        for scenario in SCENARIOS:
            if scenario == "enough":
                present = recipe["ingredients"]
            elif scenario == "missing_some":
                missing = {
                    i["canonical_name"] for i in essential[: max(1, min(2, len(essential) // 3))]
                }
                present = [i for i in recipe["ingredients"] if i["canonical_name"] not in missing]
            else:
                present = essential[: (len(essential) - 1) // 2]
            names = {i["canonical_name"] for i in present}
            purchases = [
                {**i, "count": purchase_amount(i), "price_sgd": price_for(i["canonical_name"])}
                for i in present
            ]
            code = {"enough": "ENOUGH", "missing_some": "MISSING", "below_half": "BELOW-HALF"}[
                scenario
            ]
            case_id = f"R{number:02}-{code}"
            stem = Path(recipe["source"]).stem
            image = f"images/{number:02}_{stem}__{scenario}.png"
            present_essential = sum(i["essential"] for i in present)
            assert all(i["count"] >= i["required_count"] for i in purchases)
            if scenario == "enough":
                assert len(present) == len(recipe["ingredients"])
            elif scenario == "missing_some":
                assert len(essential) / 2 <= present_essential < len(essential)
            else:
                assert present_essential < len(essential) / 2
                assert len(present) < len(recipe["ingredients"]) / 2
            # The first generated receipt already uses trailing quantity lines.
            layout = (
                "trailing"
                if number == 1 and scenario == "enough"
                else (("trailing", "leading", "inline")[(number + SCENARIOS.index(scenario)) % 3])
            )
            text = receipt_text(case_id, purchases, layout)
            prompt = (
                "Use case: photorealistic-natural. Asset type: synthetic supermarket receipt photograph "
                "for Cookish ingredient extraction tests. Generate ONE separate portrait image, approximately "
                "1024x1536. Reference image is STYLE ONLY: imitate thermal paper, monospaced printing and "
                "Singapore supermarket receipt layout; never copy real store names, addresses, phone numbers, "
                "tax IDs, payment details or original purchases. New fictional shop COOKISH TEST MART. "
                "Receipt on a neutral tabletop, nearly overhead camera, mild natural paper creases, "
                "even lighting. Entire receipt visible with margins. Prioritize crisp readable exact text. "
                "Make all item and quantity lines equally legible; slightly smaller text is fine for long receipts. "
                "Each QTY line is the actual measured purchase, NOT package size. All values are explicit; "
                "do not replace amounts with pack counts. CHICKPEAS DRAINED means the edible drained weight. "
                "The price is one line total; do not add unit-price text. No extra food items, no substitutions, "
                "no recipe names or scenario explanations, no ingredient IDs. Keep SYNTHETIC TEST RECEIPT "
                "and TEST DATA - NOT FOR CLAIMS visible. Black print on off-white paper. Render this exact text:\n"
                + text
            )
            cases.append(
                {
                    "id": case_id,
                    "scenario": scenario,
                    "recipe_id": recipe["recipe_id"],
                    "recipe_title": recipe["title"],
                    "servings": recipe["servings"],
                    "image": image,
                    "required_essential_count": len(essential),
                    "present_essential_count": present_essential,
                    "essential_coverage": present_essential / len(essential),
                    "missing_ingredients": [
                        i["canonical_name"]
                        for i in recipe["ingredients"]
                        if i["canonical_name"] not in names
                    ],
                    "purchases": purchases,
                    "receipt_text": text,
                    "generation_prompt": prompt,
                    "image_review": "pending",
                }
            )
    data = {
        "synthetic": True,
        "seed": SEED,
        "selection": "random.Random(seed).sample(sorted(recipe_paths), 10)",
        "assumptions": [
            "Empty starting inventory, except tap water is available.",
            "Use each recipe's original two servings, without scaling or substitutions.",
            "Enough includes every listed non-water ingredient, including optional ones.",
            "Missing_some omits one or two essential ingredients; at least half remain.",
            "Below_half includes strictly fewer than half the essential AND all listed non-water ingredients.",
            "Present ingredients always have enough quantity; below_half concerns ingredient coverage, not portions.",
            "QTY is explicit purchased mass/volume/piece count, not a package size.",
            "Chickpea purchase weight is drained edible weight; cooked and uncooked rice remain distinct.",
            "Intended labels are synthetic specifications, not human-reviewed real-receipt ground truth.",
            "Coverage scenarios do not assert current recommendation rankings or inventory quantity semantics.",
        ],
        "reference_images": [
            "ai/dataset/receipt/fairprice-receipt.jpeg",
            "ai/dataset/receipt/giant-receipt.jpeg",
        ],
        "recipes": recipes,
        "cases": cases,
    }
    (HERE / "images").mkdir(exist_ok=True)
    target = HERE / "cases.json"
    if target.exists():
        raise FileExistsError("Refusing to overwrite the existing scenario specifications")
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (HERE / "prompts.md").write_text(
        "# Built-in image generation prompts\n\n"
        + "\n\n".join(
            f"## {case['id']}\n\n```text\n{case['generation_prompt']}\n```" for case in cases
        )
        + "\n"
    )
    print(json.dumps({"recipes": [r["title"] for r in recipes], "cases": len(cases)}))


if __name__ == "__main__":
    main()
