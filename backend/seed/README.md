# seed

The catalogue that every database starts with: ingredients (Role 2) and recipes (Role 5). These formats are agreed between Roles 2, 4 and 5; change them only by agreement. Role 2's tasks are in [app/db/README.md](../app/db/README.md), Role 5's in [app/reco/README.md](../app/reco/README.md).

| Path | Owner | Contents |
|---|---|---|
| `ingredients.csv` | Role 2 | One row per ingredient. Also bundled into the `ai` Lambda |
| `recipes/<slug>.yaml` | Role 5 | One recipe per file |
| `seed.py` | Role 2 | Loads both; safe to run again |

## First Role 5 handoff

The [handoff notes](../../docs/role5-handoff.md) explain the starter recipe drafts,
human review status, and the next integration steps for Roles 2 and 4.
`recipe_plan.yaml` lists the proposed 48-recipe scope; `ingredient_requests.yaml`
lists the canonical names and aliases proposed for Role 2's catalogue.
These two manifests are planning inputs, not files consumed by `seed.py`.

From `backend/`, validate the handoff with:

```bash
uv run python scripts/validate_recipe_handoff.py
```

Add `--ingredients-csv seed/ingredients.csv` when Role 2's CSV is available.
Add `--require-reviewed` to reject recipe drafts before release; the starter
recipes currently need human review and correctly fail that stricter check.

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
id: 6a1f3c2e-0d4b-4f7e-9a51-2c8e7b0d1f34
title: Tomato and egg stir-fry
variant_of: null
cuisine: chinese
total_minutes: 15
active_minutes: 10
difficulty: 1
servings: 2
equipment: [stove]
taste_tags: [light]
ingredients:
  - {canonical_name: tomato, quantity: 2, unit: pcs, essential: true, prep_note: cut into wedges}
  - {canonical_name: egg, quantity: 3, unit: pcs, essential: true}
  - {canonical_name: spring onion, coarse_amount: a little, essential: false}
steps:
  - Beat the eggs with a pinch of salt.
  - Scramble the eggs until just set, then set aside.
  - Fry the tomato until soft, return the eggs, and season.
source: original
reviewed: true
```

- `canonical_name` must match a row of `ingredients.csv` exactly.
- Give either `quantity` and `unit`, or `coarse_amount`.
- A variant ("less oil", "vegetarian") sets `variant_of` to its base recipe's `id` and adds `variant_label`.
- Do not write `diet_flags` or allergens; the loader works them out from the ingredients.
- `cuisine`, `equipment` and `taste_tags` take only the values in `backend/app/schemas/common.py`.
