# Role 5: recipe catalogue and ingredient handoff

Role 2 can use these files to start the ingredient catalogue and recipe loader.
Role 4 can then use Role 2's `ingredients.csv` for receipt and photo matching.
This handoff provides catalogue inputs; it does not implement recommendations,
database seeding, or AI matching.

## What is available

| File | Status and purpose |
|---|---|
| [`backend/seed/recipes/`](../backend/seed/recipes/) | 48 complete original AI-assisted recipe drafts: 28 base recipes and 20 variants. All have fixed UUIDs and `reviewed: false`. |
| [`recipe_plan.yaml`](../backend/seed/recipe_plan.yaml) | Index of all 48 draft files, their ingredients and base/variant relationships. No outlines remain. |
| [`ingredient_requests.yaml`](../backend/seed/ingredient_requests.yaml) | The same 42 proposed canonical names, with suggested aliases, recipe units and mapping notes. All 42 are used by the completed drafts. |
| [`recipe-review.md`](recipe-review.md) | Human review guide with all 48 recipe cards, selection rationale, external references and review checks. |
| [`recipe_review.yaml`](../backend/seed/recipe_review.yaml) | Review coordination metadata, separate from the runtime recipe format. |
| [`validate_recipe_handoff.py`](../backend/scripts/validate_recipe_handoff.py) | Checks the files together, including enum values, UUIDs, variants, ingredient coverage, amounts and review status. |

The manifests are inputs for coordination and review, not new runtime seed
formats. The agreed recipe YAML and `ingredients.csv` formats remain those in
[`backend/seed/README.md`](../backend/seed/README.md).

Every draft describes a full meal portion, including any rice, noodles or
potatoes served with the dish. This prevents a suggestion or shopping basket
from silently leaving out the staple. Timings include these components, with
parallel cooking specified where assumed. The quantities, estimated times,
flavour balance and portion suitability still need review.
Recipes listing `cooked rice` start from safely stored, prepared rice; their
timings exclude its original cooking and cooling.

The earlier recipe UUIDs remain unchanged; the new drafts also have fixed UUIDs.
Keep those identities when correcting quantities, wording or titles.

## Role 2: first integration steps

1. Review the proposed canonical names and aliases in `ingredient_requests.yaml`.
   `recipe_plan.yaml` shows where each name is used across the 48 drafts. Agree
   any renaming with Role 5 and update the manifests, review material and recipes
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

The full draft catalogue can exercise loading and development fixtures while
humans review the recipes. It is not a reviewed catalogue for the user study. A proposed
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
- **Specific products:** recipes use `canola oil` and `cod fillet`.
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
| Taste tags | Use the existing `TasteTag` values. `low_oil` means at most 5 ml total added cooking oil, including seasoning oils, per two servings. Reserve `high_protein` for explicit protein additions to a base recipe. `vegetable_rich` requires at least 300 g of the defined vegetable set per two servings. The [review guide](recipe-review.md) details these transparent authoring heuristics; they are culinary ranking features, and nutrition metrics or user-facing nutrition claims require separate work. |
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

The recipe prose and constrained ingredient combinations were drafted
specifically for this project with AI assistance. Named external recipe authors
provide concept or technique references; each recipe's `source` records its
original AI-assisted status and an exact reference URL. The
[review guide](recipe-review.md) identifies each reference and explains which
ideas informed the draft and what changed.

These are original project prototypes, not copies of the external authors'
complete recipes. No third-party photos or recipe prose are included. An
external reference does not validate our adaptations, timings, dietary
suitability or nutrition. No recipe has yet been marked as human-reviewed, and
the catalogue is not a third-party recipe API or a tested research dataset.
The 48 drafts have not been cooking-tested.

Use the guide's review checks to assess ingredient names and amounts, full meal
portions, equipment, timing, complete instructions, optional ingredients and
variant behaviour. Check meat, fish, egg and cooked-rice handling before use
with participants. All equipment entries are required together; reviewers
should check the parallel-cooking and appliance assumptions as well as the
ingredient list.

Record the reviewer, review date, corrections and any cooking-trial evidence in
the review PR. The generated guide's checkboxes are a checklist, not a persistent
evidence record. Change `reviewed` to true only for the
specific recipes actually reviewed; a structural validator cannot grant
culinary approval. Keep AI drafting, research/validation assistance and human
corrections in the final report's AI-use declaration, and cite the named
external sources for the limited role they played.

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

That last command is expected to fail for all 48 current drafts. It checks
the review flags; it cannot verify that a human actually performed the review.
