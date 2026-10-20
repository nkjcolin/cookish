# seed

The catalogue that every database starts with: ingredients (Role 2) and recipes (Role 5). These formats are agreed between Roles 2, 4 and 5; change them only by agreement. Role 2's tasks are in [app/db/README.md](../app/db/README.md), Role 5's in [app/reco/README.md](../app/reco/README.md).

| Path | Owner | Contents |
|---|---|---|
| `ingredients.csv` | Role 2 | One row per ingredient. Also bundled into the `ai` Lambda |
| `recipes/<slug>.yaml` | Role 5 | 48 recipes with human content approval, one per file |
| `seed.py` | Role 2 | Planned loader for ingredients and recipes; must be safe to run again |
| `recipe_plan.yaml` | Role 5 | Index of the 48 reviewed files and their ingredient/variant relationships |
| `ingredient_requests.yaml` | Role 5 / Role 2 review | 42 proposed canonical names and aliases |
| `recipe_review.yaml` | Role 5 / human reviewer | Review coordination metadata; not a runtime seed format |

## Role 5 catalogue handoff

The [handoff notes](../../docs/role5-handoff.md) explain the next integration
steps for Roles 2 and 4. All 48 catalogue entries now have complete recipe files:
28 base recipes and 20 variants, using the same 42 proposed canonical ingredients.
Wenlong approved all 48 recipe contents on 2026-10-20; every recipe is now
`reviewed: true`. The approval record is in `recipe_review.yaml`.

Find the content approval record and further trial checklist in the [recipe review guide](../../docs/recipe-review.md),
which provides all 48 recipe cards, selection rationale, sources and checks.
The recipes are original AI-assisted project drafts with named external
concept/technique references. These references do not establish approval of the
adapted recipe, its nutrition, timing or safety.

Recipes include their meal portions and any rice, noodles or potatoes used to
serve them. Total-time estimates include preparing those components; some rice
meals assume parallel cooking on the stove. Human content approval is recorded;
amounts and timing have not been verified through cooking trials.
Existing recipe UUIDs are preserved.
Where `cooked rice` is listed, the timing starts with already-prepared, safely
stored rice and excludes its original cooking and cooling.

`recipe_plan.yaml`, `ingredient_requests.yaml` and `recipe_review.yaml` support
coordination and review. They do not add runtime fields to the agreed recipe
format. The recipe files do not themselves implement database loading or change
the Cook/Shop service stubs.

From `backend/`, validate the handoff with:

```bash
uv run python scripts/validate_recipe_handoff.py
uv run python scripts/render_recipe_review.py --check
```

After editing recipe content or `recipe_review.yaml`, refresh the review guide
with `uv run python scripts/render_recipe_review.py`.

Add `--ingredients-csv seed/ingredients.csv` when Role 2's CSV is available.
Add `--require-reviewed` to require the human-review flags; all 48 approved
recipes now pass that check. It does not certify cooking trials or nutrition.

## Agreed seed formats

Every row and every recipe carries a fixed UUID written in the file. Generate one with `python -c "import uuid; print(uuid.uuid4())"`, and never change it afterwards: inventory, ratings and stars refer to it.

## ingredients.csv

```csv
id,canonical_name,aliases,category,countable,default_unit,allergen_tags,diet_flags,shelf_life_days_pantry,shelf_life_days_fridge,shelf_life_days_freezer,default_storage,is_staple,purchase_unit,purchase_unit_size,purchase_unit_measure
0f7d…,egg,eggs|telur,egg,true,pcs,egg,vegetarian|pescatarian|halal|no_pork|no_beef,,28,,fridge,false,tray,10,pcs
4b21…,water spinach,kangkong|kang kong,produce,false,,,vegetarian|vegan|pescatarian|halal|no_pork|no_beef,,3,,fridge,false,bunch,1,pcs
9c03…,soy sauce,light soy sauce,condiment,false,,soy|gluten,vegetarian|vegan|pescatarian|halal|no_pork|no_beef,365,,,pantry,true,bottle,500,ml
```

- `|` separates the items of a list; an empty cell is null.
- `countable` decides whether the kitchen tracks a count (eggs) or only a state (kangkong).
- `diet_flags` lists the diets the ingredient is suitable for. Recipes inherit them (C3).
- Shelf-life days are estimates, for example from the USDA FoodKeeper data. Leave a storage empty if the ingredient is not kept there.

## recipes/*.yaml

```yaml
id: 645a8d38-bfae-47f2-b00e-3ca6828a964e
title: Tomato and egg rice bowls
variant_of: null
cuisine: chinese
total_minutes: 35
active_minutes: 20
difficulty: 1
servings: 2
equipment: [stove]
taste_tags: [light]
ingredients:
  - {canonical_name: uncooked rice, quantity: 200, unit: g, essential: true}
  - {canonical_name: tomato, quantity: 300, unit: g, essential: true, prep_note: cut into wedges}
  - {canonical_name: egg, quantity: 3, unit: pcs, essential: true}
  - {canonical_name: canola oil, quantity: 15, unit: ml, essential: true}
  - {canonical_name: salt, quantity: 1, unit: g, essential: false}
  - {canonical_name: water, coarse_amount: for the rice according to its packet and a splash for the tomatoes, essential: true}
  - {canonical_name: spring onion, quantity: 10, unit: g, essential: false, prep_note: thinly sliced}
steps:
  - Cook the rice in a covered saucepan with water according to its packet; prepare the topping while it cooks.
  - Beat the eggs. Warm two thirds of the oil in a nonstick pan, cook the eggs until set and transfer to a clean bowl.
  - Soften the tomatoes in the remaining oil, add a splash of water and cover until they release a sauce.
  - Return the eggs, add salt if using and heat until the eggs are completely cooked and everything is hot.
  - Serve the topping over the rice with spring onion if using.
source: 'original AI-assisted draft; concept/technique reference: https://thewoksoflife.com/stir-fried-tomato-and-egg/'
reviewed: false
```

- `canonical_name` must match a row of `ingredients.csv` exactly.
- Give either `quantity` and `unit`, or `coarse_amount`.
- A variant ("less oil", "vegetarian") sets `variant_of` to its base recipe's `id` and adds `variant_label`.
- Do not write `diet_flags` or allergens; the loader works them out from the ingredients.
- `cuisine`, `equipment` and `taste_tags` take only the values in `backend/app/schemas/common.py`.
- All listed equipment is required; the list means AND, not a choice between appliances.
- `low_oil` means no more than 5 ml of total added cooking oil per two servings
  in this catalogue, including seasoning oils. It describes the method, not
  total fat or a regulated nutrition claim.
- `high_protein` is reserved for an explicit protein addition to a base recipe.
  It is a qualitative ranking tag pending nutrition metrics, not a measured
  nutrition claim or an automatic label for every meat, egg or legume meal.
- `vegetable_rich` uses an authoring threshold of at least 300 g of the defined
  vegetable set per two servings. The [review guide](../../docs/recipe-review.md)
  specifies the counted ingredients and other transparent tag heuristics;
  these are culinary ranking features, not nutrition claims.

Role 2 still needs to resolve water's proposed assumed-available/no-purchase
treatment and conversions between recipe amounts, inventory counts and pack
sizes. See the [ingredient handoff details](../../docs/role5-handoff.md#ingredient-details-to-settle-during-catalogue-review).
