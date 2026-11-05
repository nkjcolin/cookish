# Role 5: recipe catalogue and ingredient handoff

Status after [PR #21](https://github.com/nkjcolin/cookish/pull/21) merged on
5 November 2026: the 48 reviewed recipes, Role 2's 42-row ingredient catalogue
and seed loader are available. Role 5's pure Cook/Shop engines, feedback learning,
SQL input reader, recipe details, household stars and use-first endpoint are
implemented. Cook/Shop session, confirmation and rating endpoints still use mocks
pending the agreed persistence adapter. See the [service handoff](role5-integration.md)
for that remaining work.

Role 2's `ingredients.csv` is the authoritative ingredient source for Role 5
recommendations and Role 4 matching. The request manifest records the original
content handoff; it does not replace the delivered catalogue or establish the
status of Role 4's AI implementation.

## What is available

| File | Status and purpose |
|---|---|
| [`backend/seed/recipes/`](../backend/seed/recipes/) | 48 original AI-assisted recipes: 28 base recipes and 20 variants. Wenlong approved all contents on 2026-10-20; fixed UUIDs and `reviewed: true`. |
| [`recipe_plan.yaml`](../backend/seed/recipe_plan.yaml) | Index of all 48 reviewed files, their ingredients and base/variant relationships. No outlines remain. |
| [`ingredient_requests.yaml`](../backend/seed/ingredient_requests.yaml) | Original 42-name request manifest, with suggested aliases, recipe units and mapping notes. All 42 names now resolve against the delivered catalogue. |
| [`ingredients.csv`](../backend/seed/ingredients.csv) and [`seed.py`](../backend/seed/seed.py) | Role 2's authoritative ingredient metadata and implemented catalogue/recipe loader. |
| [`recipe-review.md`](recipe-review.md) | Human review guide with all 48 recipe cards, selection rationale, external references and review checks. |
| [`recipe_review.yaml`](../backend/seed/recipe_review.yaml) | Review coordination metadata, separate from the runtime recipe format. |
| [`validate_recipe_handoff.py`](../backend/scripts/validate_recipe_handoff.py) | Checks the files together, including enum values, UUIDs, variants, ingredient coverage, amounts and review status. |

The manifests are inputs for coordination and review, not new runtime seed
formats. The agreed recipe YAML and `ingredients.csv` formats remain those in
[`backend/seed/README.md`](../backend/seed/README.md).

Every recipe describes a full meal portion, including any rice, noodles or
potatoes served with the dish, so the planner can assess those requirements.
Shop now excludes meals with unavailable non-buyable essentials; the remaining
unit and purchase-entry issues are recorded in the [quality review](role5-catalogue-quality-review.md).
Timings include these components, with parallel cooking specified where assumed.
Wenlong has approved the contents. Quantities, estimated times,
flavour balance and portion suitability have not been checked through cooking trials.
Recipes listing `cooked rice` start from safely stored, prepared rice; their
timings exclude its original cooking and cooling.

All recipe UUIDs remain unchanged.
Keep those identities when correcting quantities, wording or titles.

## Delivered catalogue and continuing agreements

The catalogue and loader are implemented; they are no longer requests for Role 2
to start. Role 5's SQL reader resolves reviewed recipes against the ingredient
rows and reads household preferences, inventory and stars in the caller's transaction.

- Preserve recipe UUIDs and exact canonical names. Agree future renaming with
  Role 2 and update the recipe/index/review material together.
- Use Role 2's stored tracking modes, purchase definitions, shelf-life estimates,
  allergens and diet flags. Request changes instead of editing their schema or
  substituting synthetic fixture metadata.
- Check diet/allergen suitability against **all** listed ingredients, including
  optional seasonings. The runtime reader uses current ingredient metadata.
- Validate recipe changes against the existing CSV using the command below.
  Role 4 consumes that same authoritative catalogue; its implementation remains
  outside Role 5's ownership.

The recipe content handoff is approved by Wenlong and available to Role 2.
All 48 review flags are true; the approval record identifies the exact recipe
version and the user statement. Cooking trials and full Cook/Shop persistence
remain separate work. Future unreviewed additions should remain excluded from a release
until their review is recorded.

### Current ingredient policies and remaining quantity decisions

- **Water:** the delivered catalogue marks it as a staple with no purchase unit.
  The engine assumes an untracked staple is available, and Shop does not purchase
  water. Explicit tracked absence or uncertainty still follows stock assessment;
  the staple flag is not permission to invent confirmed inventory.
- **Counts versus grams:** `recipe_units` describes amounts in recipes, not the
  inventory tracking mode. A 300 g tomato requirement must not be compared to
  “two tomatoes” without an agreed conversion. Tofu has a catalogue purchase-pack
  definition of 300 g, but applying it to an existing batch still requires an
  agreed meaning for that batch's `pack` unit. Use the existing uncertainty/check flow
  when units cannot be reconciled.
- **Food forms:** `cooked rice` and `uncooked rice` are separate entries; fresh
  mushrooms, canned chickpeas and dry lentils are named explicitly. Avoid
  aliases that erase preparation state.
- **Specific products:** recipes use `canola oil` and `cod fillet`.
  Do not map every oil or fish to those names. The manifest flags product
  composition questions for sauces, noodles and other processed ingredients.
- **Aliases:** the request manifest's suggestions are historical coordination
  inputs. Use the delivered CSV aliases at runtime; Role 2 owns their mappings
  and Role 4 can report observed matching gaps.

## Shared data decisions before service integration

The [service integration handoff](role5-integration.md) now contains the implemented
workflow and repository port, Role 5's adapter responsibilities, proposed storage
for Role 2 and remaining Postgres workflow tests. Cook/Shop sessions, confirmations
and ratings remain mocked. Recipe details, stars and use-first already use the
database without the proposed migration.

The table distinguishes implemented behavior from decisions still needing Roles
1/2's agreement; it does not introduce shared contract changes.
The existing service signatures, API schemas, enum values and migrations are
unchanged by this handoff.

| Topic | Proposed next step |
|---|---|
| Taste tags | Use the existing `TasteTag` values. `low_oil` means at most 5 ml total added cooking oil, including seasoning oils, per two servings. Reserve `high_protein` for explicit protein additions to a base recipe. `vegetable_rich` requires at least 300 g of the defined vegetable set per two servings. The [review guide](recipe-review.md) details these transparent authoring heuristics; they are culinary ranking features, and nutrition metrics or user-facing nutrition claims require separate work. |
| Internal feedback state | Keep learned weights per household, as SPEC A6 requires. `get_preferences()` currently returns `Preferences`, which omits `taste_weights`. Agree internal database/repository access with Role 2; the public preferences response does not need to expose learned weights. |
| Weight representation | Pure Cook/Shop default to an empty map and treat absent features as zero, using `tag:low_oil` and `cuisine:chinese` namespaces. Pure learning now produces this map. Agree how to derive main-protein features from ingredient metadata before adding them. |
| Learning updates | Implemented policy: step 0.25, bounds −2 to +2; confirmed cooking gives provisional +0.0625. Like/Maybe/Dislike replace that meal's contribution with +0.25/0/−0.25. Retries are no-ops. Replay one evidence entry per cook record in first-confirmation order to handle changed ratings after clipping. Agree persistence of feature snapshots, order and current ratings; the clipped map alone cannot support exact replacement. See the [learning handoff](../backend/app/reco/README.md#feedback-learning-implemented-milestone). |
| Shop purchase metadata | The SQL reader supplies category, buyable flag, pack unit/size/measure and default-storage shelf-life estimate from the existing catalogue. Null/incompatible pack conversion retains a check item rather than inventing packs. Roles 1/2/5 still need to agree how the UI and confirmation flow resolve counted ingredients requiring a quantity check. Do not default these cases to one verified pack. |
| Basket revisions | Persist `to_basket` item IDs, derived from basket UUID plus ingredient UUID. A revised basket needs a fresh saved UUID. Confirm only its saved lines and actual purchases through Role 2's stock-event service. The pure planner does not mutate stock. |
| First use, no ratings | Implemented in the pure Cook engine: hard constraints, inventory and fixed scoring defaults with zero learned weights and no history penalty. The SQL reader supplies actual preferences/inventory; session endpoints still need the persistence adapter and workflow wiring. |
| First use, no inventory | Do not mark missing stock as available or fabricate an inventory batch for `StockCheck.item`. SPEC B5 permits missing-essential fallback suggestions; agree with Role 1 how their missing ingredients lead to adding stock or shopping before cooking. |

Role 2 still owns every database migration and ingredient row. Role 5 owns
recipe content and queries for recommendation sessions, feedback and baskets.
Changes to shared contracts follow the procedure in
[`docs/init.md`](init.md#changing-an-agreement-between-roles).

## Evaluation and report handoff

The 70 development scenarios are implemented. The separate held-out runner has
been rehearsed with copies of those development cases: 70 scenarios and 85 steps
passed, with zero held-out scenarios executed. The final freeze and 30 independent
cases remain pending; use the [evaluation protocol](../eval/reco_scenarios/README.md)
to preserve the first result and distinguish later regressions.

The [Role 5 report draft](role5-report-notes.md) covers cold start, recipe provenance,
household learning and evaluation terminology. The [business-case draft](business-case.md)
contains references and provisional costs; final measured figures require Roles 3/4.

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
suitability or nutrition. Wenlong approved all 48 recipe contents in the project
chat on 2026-10-20; `recipe_review.yaml` records the statement and the approved
commit. The catalogue is not a third-party recipe API or a tested research
dataset. Cooking trials have not been performed.

For further review and cooking trials, use the guide's checks to assess ingredient names and amounts, full meal
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

Validate against the delivered Role 2 catalogue:

```bash
uv run python scripts/validate_recipe_handoff.py --ingredients-csv seed/ingredients.csv
```

Verify that every delivered recipe retains its recorded review flag:

```bash
uv run python scripts/validate_recipe_handoff.py --require-reviewed
```

That last command now passes for all 48 recipes. It checks the review flags;
the human content approval is recorded separately and does not claim cooking trials.
