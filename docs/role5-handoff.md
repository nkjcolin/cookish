# Role 5: first recipe and ingredient handoff

Role 2 can use these files to start the ingredient catalogue and recipe loader.
Role 4 can then use Role 2's `ingredients.csv` for receipt and photo matching.
This handoff provides catalogue inputs; it does not implement recommendations,
database seeding, or AI matching.

## What is available

| File | Status and purpose |
|---|---|
| [`backend/seed/recipes/`](../backend/seed/recipes/) | 10 original AI-assisted recipe drafts: eight base recipes and two less-oil variants. All have fixed UUIDs and `reviewed: false`. |
| [`recipe_plan.yaml`](../backend/seed/recipe_plan.yaml) | 48 proposed catalogue entries, including the 10 drafts and 38 outlines. Each lists its intended ingredients and base/variant relationship. Outlines are not completed recipes. |
| [`ingredient_requests.yaml`](../backend/seed/ingredient_requests.yaml) | 42 proposed canonical names, with suggested aliases, recipe units and mapping notes. The starter recipes use 24 of these names. |
| [`validate_recipe_handoff.py`](../backend/scripts/validate_recipe_handoff.py) | Checks the files together, including enum values, UUIDs, variants, ingredient coverage, amounts and review status. |

The two planning manifests are inputs for coordination, not new runtime seed
formats. The agreed recipe YAML and `ingredients.csv` formats remain those in
[`backend/seed/README.md`](../backend/seed/README.md).

## Role 2: first integration steps

1. Review the proposed canonical names and aliases in `ingredient_requests.yaml`.
   `recipe_plan.yaml` shows where each name will be used, including upcoming
   recipes. Agree any renaming with Role 5 and update both manifests and recipes
   together.
2. Create the authoritative `ingredients.csv` with your fixed ingredient UUIDs,
   tracking modes, purchase units, source-backed shelf-life estimates, allergen
   tags and diet flags. The request manifest deliberately does not assign these.
3. Read `recipes/*.yaml` using the existing format. Resolve `canonical_name`
   against the CSV and `variant_of` against a recipe UUID. Preserve the recipe
   UUIDs: later ratings and stars will reference them.
4. Derive recipe diet suitability and allergens from **all** listed ingredients,
   including optional ones, as the existing agreement requires. An optional
   seasoning is still part of the stored recipe; silently omitting it is not a
   dietary substitution.
5. Once the CSV exists, run the optional CSV validation below. Give the same CSV
   to Role 4 for bundling with the AI service.

The initial batch can exercise loading and development fixtures while humans
review the recipes. It is not a reviewed catalogue for the user study. A proposed
loader policy is to allow drafts only through an explicit development option and
to exclude them from the catalogue offered to study participants.

### Ingredient details to settle during catalogue review

- **Water:** present in the recipes so instructions have a complete ingredient
  list, including steamer water. Proposed treatment: assume it is available,
  mark it as a staple, and omit it from stock consumption and Shop purchases.
  Role 2 and Role 5 need to agree this treatment before integration.
- **Counts versus grams:** `recipe_units` describes amounts in recipes, not the
  inventory tracking mode. A 300 g tomato requirement must not be compared to
  “two tomatoes” without an agreed conversion. Likewise, 300 g tofu does not
  imply a particular number of packs. Use the existing uncertainty/check flow
  when units cannot be reconciled.
- **Food forms:** `cooked rice` and `uncooked rice` are separate entries; fresh
  mushrooms, canned chickpeas and dry lentils are named explicitly. Avoid
  aliases that erase preparation state.
- **Specific products:** starter recipes use `canola oil` and `cod fillet`.
  Do not map every oil or fish to those names. The manifest flags product
  composition questions for sauces, noodles and other processed ingredients.
- **Aliases:** these are proposed search/matching inputs, not verified coverage
  of every receipt label. Role 2 owns final mappings; Role 4 can add observed
  misses through that same catalogue.

## Shared data decisions before algorithm integration

These are proposals for Roles 1 and 2 to review, not implemented contract changes.
The existing service signatures, API schemas, enum values and migrations are
unchanged by this handoff.

| Topic | Proposed next step |
|---|---|
| Taste tags | Use the existing `TasteTag` values. No new tags are needed for this starter batch. `low_oil` is a qualitative cooking tag, not a measured nutrition claim. |
| Internal feedback state | Keep learned weights per household, as SPEC A6 requires. `get_preferences()` currently returns `Preferences`, which omits `taste_weights`. Agree internal database/repository access with Role 2; the public preferences response does not need to expose learned weights. |
| Weight representation | Propose an empty map initially, treating an absent feature as zero; namespace features such as `tag:low_oil` and `cuisine:chinese`. Agree how to derive main-protein features from ingredient metadata before adding them. |
| Learning updates | SPEC B5 says Like adds a step, Dislike subtracts one, and Maybe/skip leave weights unchanged. Choose and document the step size and bounds in Role 5's future scoring configuration. Agree how the small “cooked without rating” reward interacts with a later rating, repeated requests and changed ratings, so an HTTP retry cannot train the profile twice. |
| First use, no ratings | After onboarding, use the hard constraints, inventory and fixed scoring defaults with zero learned weights and no history penalty. A new household must not receive invented rating history. |
| First use, no inventory | Do not mark missing stock as available or fabricate an inventory batch for `StockCheck.item`. SPEC B5 permits missing-essential fallback suggestions; agree with Role 1 how their missing ingredients lead to adding stock or shopping before cooking. |

Role 2 still owns every database migration and ingredient row. Role 5 owns
recipe content and queries for recommendation sessions, feedback and baskets.
Changes to shared contracts follow the procedure in
[`docs/init.md`](init.md#changing-an-agreement-between-roles).

## Recipe provenance and human review

The initial recipe prose was drafted specifically for this project with AI
assistance. No third-party recipe text, photos or research dataset records were
copied into this batch. Each file records `source: 'original; AI-assisted draft'`
and remains `reviewed: false`. This is a provenance statement, not a claim of
human approval, cooking trials or nutrition analysis.

For each recipe, a human reviewer should check the ingredient names and amounts,
servings, equipment, timing, complete instructions, optional ingredients and
variant behaviour. Cooking instructions and handling of meat, fish, eggs and
cooked rice need review before use with participants. Record the reviewer,
date and any cooking-trial evidence in the eventual review PR, then change
`reviewed` to true for the specific recipes actually reviewed.

Keep the AI drafting, validation assistance and human corrections in the final
report's AI-use declaration. Record external sources and licences if future
recipes use external material; do not imply this original batch came from a
third-party recipe API.

## Validation

Run from `backend/`:

```bash
uv sync --frozen
uv run python scripts/validate_recipe_handoff.py
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The normal validator accepts honestly labelled drafts and reports how many still
need human review. It checks the supplied manifests and recipe structures, not
culinary quality, nutritional claims or food safety. The repository-data test
runs as part of the existing backend CI job.

When Role 2's catalogue is available:

```bash
uv run python scripts/validate_recipe_handoff.py --ingredients-csv seed/ingredients.csv
```

Before treating the delivered recipe files as reviewed:

```bash
uv run python scripts/validate_recipe_handoff.py --require-reviewed
```

That last command is expected to fail for this initial draft batch. It checks
the review flags; it cannot verify that a human actually performed the review.
