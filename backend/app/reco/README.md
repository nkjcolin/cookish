# Role 5 — Recommendation and recipes

You own what Cookish suggests: the recipe catalogue, the Cook and Shop algorithms, and the services that turn them into sessions, suggestions and baskets. Read [docs/init.md](../../../docs/init.md) first for the conventions everyone follows.

The design is in [SPEC.md](../../../docs/SPEC.md), **B5**: the Cook algorithm (hard filter, availability, score, adjustments, learning from ratings), the freshness gate, the Shop algorithm and the use-first estimate. **A6** has the tables for sessions, ratings and baskets.

## What you own

| Path | Contents |
|---|---|
| `backend/app/reco/` | Pure Cook filtering, stock assessment, scoring, suggestions and adjustments; Shop remains to implement |
| `backend/seed/recipes/*.yaml` | Target: 40 to 60 reviewed recipes; 48 AI-assisted recipes have human content approval; no cooking trials |
| `backend/app/services/cook.py` | `start_session`, `adjust`, `next_suggestion`, `previous_suggestion`, `select`, `confirm`, `give_feedback`, `get_recipe`, `set_star`, `use_first` (optional) |
| `backend/app/services/shop.py` | `start_session`, `adjust`, `confirm_basket` |
| `eval/reco_scenarios/` | The 100 evaluation scenarios |

You also own the taste-tag list in `app/schemas/common.py` (change it through the contract procedure), and the business case and pricing section of the final report.

## What already exists

- **Every service function above, as a stub** marked `STUB`, returning sample data from `app/mock.py`. The frontend is built against them.
- **Role 2's functions you call**, with agreed signatures and stubs that return sample data, so you can wire your services before the database exists (see below).
- **`app/db/session.py`**: `transaction()`, one per request.
- **`app/clock.py`**: today's date in Singapore.
- **The recipe file format**, agreed with Role 2, in [seed/README.md](../../seed/README.md).
- **The pure Cook engine**, described below, tested independently of those service stubs.

## Cook engine: implemented milestone

`cook.py` implements `filter_recipes`, `score_recipe`, `suggest`, `adjust`,
`skip_current`, `new_session` and `to_suggestion`. `inventory.py` scales amounts
and classifies stock. `models.py` defines internal inputs and results;
`config.py` contains all initial scoring weights. These modules perform no I/O,
database access, live clock reads or session persistence.

The **public Cook/Shop services still return mocks**. This milestone does not
claim a working deployed recommendation flow, feedback persistence, a basket
algorithm or completed evaluation scenarios.

### Inputs and integration

The future service adapter supplies:

| Input | Required meaning |
|---|---|
| `Candidate` | Existing resolved recipe shape plus the stored `reviewed` flag. Ingredient UUIDs must be resolved from Role 2's catalogue. Unreviewed recipes are excluded. |
| `dict[UUID, CatalogIngredient]` | Authoritative ingredient identity, allergens, diet flags, tracking mode, staple flag and a perishable classification. All fields are required. Missing metadata excludes the entire recipe, including optional ingredients. These internal fields do not change the public ingredient response. |
| `list[InventoryItem]` | Household-scoped snapshot from `get_inventory_snapshot`; removed items excluded and freshness already computed by Role 2. Free-text/unmapped batches cannot satisfy a canonical ingredient. |
| `Preferences` | Current household preferences; all requested diets and all required equipment must be satisfied. |
| `CookSession` | People, accumulated constraints, shown/skipped/history IDs, and an optional explicitly strict time cap. New sessions use the remembered people count. |
| `as_of` | A timezone-aware instant from `app.clock.now()`, passed once by the service. Scoring uses its Singapore date. |
| `taste_weights` | Optional household feature map. An omitted map means zero learned preference. No history is invented. |

Internal `CatalogIngredient.perishable` needs an agreed mapping from Role 2's
catalogue data; it is not inferred from recipe names. Main-protein learning
features remain pending a similarly authoritative mapping. The initial engine
reads `tag:<tag>` and `cuisine:<cuisine>` weights; it does not update them.

Typical service flow, once its repository adapter exists:

```python
from app import clock
from app.reco import adjust, new_session, suggest, to_suggestion

session = new_session(preferences, people=requested_people)
result = suggest(
    candidates,
    inventory,
    preferences,
    session,
    ingredient_metadata,
    as_of=clock.now(),
    taste_weights=household_weights,
)
# If result.selected is None: map to ApiError(NO_RESULT, ..., {
#     "relaxable": list(result.relaxable)
# }).
# Otherwise persist result.session, then return:
response = to_suggestion(result, session_id)

# For an adjustment, load the exact current Candidate and persisted session:
updated_session = adjust(result.session, adjustment_body, result.selected.recipe)
```

`suggest` returns a new session with the selected ID appended to its shown
history. `skip_current` adds only the current ID to the excluded set; it does
not train preferences. The service must persist and replay these states and
implement expiry, transactions, concurrency and request retry handling.
`previous` should replay the saved entry rather than call the engine again.

### Eligibility, stock and cold start

Allergen/diet/equipment filters run before availability and ranking and are
never relaxed. Recipe diet suitability is checked against every ingredient,
including optional seasonings. The public preference time limit is initially
applied but can be reported as relaxable; an explicit internal
`strict_max_minutes` is never relaxable. The current API has no field for setting
that strict cap; the engine does not add one to the API.

For stock assessment:

- Multiply numeric needs by `people / servings`. Sum compatible counted batches
  and mark a short count `low`. State-tracked `enough` and `low` remain those
  states regardless of the requested portions; no grams are invented.
- Compare count units exactly. Packs, grams and pieces are not interchangeable
  without an agreed conversion. Incompatible/missing units or counts produce
  `unknown`; a coarse amount cannot be compared to a numeric count.
- A perishable last confirmed over 14 days ago becomes `unknown`. No
  confirmation check is imposed on non-perishables by this rule.
- Trust the snapshot's freshness gate: `expired` contributes no stock; `check`
  contributes no confirmed stock and is returned for inspection. Both retain
  real batch IDs. Even a recently confirmed usable batch earns no urgency bonus
  for a date already past.
- An untracked staple is assumed available. Explicit tracked `out`, expired or
  uncertain stock overrides that assumption. Role 2 must agree which ingredients
  receive the staple flag, especially water.
- A missing essential excludes the recipe while any eligible recipe without a
  missing essential remains. If every eligible recipe is missing something,
  return the best fallback with its ingredients visibly marked `missing`.
  `low` and `unknown` are not promises that a full portion is available.
- Unknown essentials expose the earliest existing uncertain batch in
  `needs_check`. An absent ingredient has no invented batch. The frontend route
  from a missing-essential suggestion to shopping/adding stock still needs
  agreement with Role 1.

New users get deterministic ranking from inventory, cuisine choices, stars and
fixed effort defaults, with zero learned weights and no repetition penalty.
An empty kitchen gets an explicitly marked missing-stock fallback, provided a
recipe passes the hard and session constraints. If none does, return no result.

### Scores and adjustments

Initial coefficients in `config.py` are hand-set, not tuned evaluation results:

| Feature | Weight / definition |
|---|---|
| Coverage | +3; mean over non-staples: have=1, low=0.5, otherwise=0 |
| Expiry urgency | +1; mean of each non-staple's highest usable-batch urgency, `max(0, 1-days/4)` for nonnegative days only |
| Preference | +1; learned feature sum, +0.5 matching cuisine, +1 star, −1 per disliked ingredient, +2 per boosted tag |
| Effort | −0.5; average of time/preferred-time and difficulty/preferred-difficulty; defaults 60 minutes and difficulty 3 |
| Repetition | −1 per membership in shown history and recent cooked history |
| Uncertain essentials | −1 each for unknown or check |
| Similarity after adjustment | +0.5 times ingredient/tag Jaccard similarity to the prior recipe |

`ScoreBreakdown` exposes raw features and signed weighted terms for testing and
reporting. The UI receives the existing `Suggestion` shape with no explanation
text. Equal scores are resolved by fixed recipe UUID, independent of input order.

Adjustments accumulate:

- Quicker tightens time to current recipe time minus 10 minutes.
- Easier tightens difficulty by one.
- Less oil requires `low_oil`; More vegetables requires `vegetable_rich`.
- More protein boosts `high_protein` without excluding all other recipes.
- Explicit time/difficulty patches can only tighten existing limits. People
  can change in either direction. A people-only patch does not request a variant.
- A qualifying different recipe in the same base family is preferred over
  unrelated candidates after the stock-availability tier is selected. It must
  satisfy all accumulated restrictions and boosted tags. Similarity otherwise
  contributes to scoring.

At the minimum time/difficulty, Quicker/Easier can legitimately yield no result;
the engine never loosens a restriction to fabricate an answer. Only
`max_minutes` and `tags` can be returned in `relaxable`, and only when removing
those soft filters actually restores a candidate after the hard gate. Difficulty
caps and skipped IDs are not silently removed.

### Validation and remaining work

Run from `backend/`:

```bash
uv sync --frozen
uv run pytest tests/test_reco.py
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Development tests cover real catalogue recipes, serving scaling, all stock
states, incompatible units, freshness, cold start, accumulating adjustments,
variant preference, no-result diagnostics and the unchanged response schema.
Hypothesis generates 150 combinations of allergens, inventory states, counts,
freshness, people and up to three adjustments and checks that prohibited
ingredients never appear in a selected recipe.

These are development tests, **not the 100 report scenarios**. The 30 held-out
scenarios have not been authored or used for tuning here. Still to implement:
Shop basket search; bounded feedback updates and retry-safe persistence;
database-backed Cook/Shop sessions and stock confirmation; the scenario suite;
and deployed evaluation. No synthetic metadata from tests should be seeded as
the authoritative ingredient catalogue.

## What you may change, and what you must keep

**Yours to decide:** everything in `reco/`; the bodies of the Cook and Shop services; scoring weights (keep them in one config file and report them); the recipes; the queries on your own tables.

**Keep, because others depend on them:**

- The name, parameters and return type of every service function. The routers and the frontend call them.
- The recipe file format: Role 2's loader reads it.
- The table structure: Role 2 writes every migration, including for your tables. Ask for changes.

## What the frontend expects from you

The frontend is finished, so these behaviours are fixed.

- **Adjustments only add conditions.** `POST /cook/sessions/{id}/adjust` adds to what the session already holds; there is no way to remove one. To remove a condition, the frontend starts a new session and sends the rest again, and its **Reset** button starts a session with none.
- **Quick checks.** `Suggestion.needs_check` lists, for each essential ingredient of unknown stock, the batch to use first (`StockCheck.item`). `freshness_check` lists the batches whose `freshness_status` is `check`, with a reason. The frontend asks about exactly these before cooking and saves each answer on that batch with `PATCH /api/inventory/items/{id}`.
- **"No, I don't have it".** The frontend records that batch as `out`, then calls `POST /cook/sessions/{id}/next`. The next suggestion must reflect the new stock. The `skipped` signal that `next` records must not change taste weights.
- **Nothing fits.** Raise `ApiError(ErrorCode.NO_RESULT, …, {"relaxable": [...]})`. `relaxable` may contain only `"max_minutes"` and `"tags"`, and never a hard constraint. Shop avoids `NO_RESULT`: when it cannot fill every meal, it returns a basket for fewer. Only when no recipe at all passes the hard constraints does it return `NO_RESULT` with an empty `relaxable`.
- **Expiry.** A session expires 12 hours after it starts. Any request on an expired or unknown session returns `NOT_FOUND`; the frontend then starts a new one with the same conditions.
- **People.** `people` defaults to the household's last choice and is written back when a session starts or changes; amounts in a suggestion are already scaled to it.

## Role 2's functions you call

Open one transaction per request and pass `s` on:

```python
from app.db.session import transaction
from app.services.identity import get_preferences
from app.services.stock_events import (
    ChangeBatch,
    NewBatch,
    apply_stock_event,
    get_inventory_snapshot,
)


def confirm(user, record_id, body, idempotency_key):
    with transaction() as s:
        ...  # load and update the cook record
        change = apply_stock_event(
            s,
            user,
            StockEventType.CONSUME,
            [
                ChangeBatch(item_id=line.inventory_item_id, revision=line.revision, changes={...})
                for line in body.lines
            ],
            idempotency_key,
            StockRefType.COOK_SESSION,
            record_id,
        )
```

| Function | Gives you |
|---|---|
| `get_inventory_snapshot(s, household_id)` | Every batch not removed, as `InventoryItem`, each with `est_use_first_date` and `freshness_status` already computed |
| `get_preferences(s, household_id)` | The household's preferences, including `last_cook_people`, `last_shop_people`, `last_shop_meals` |
| `apply_stock_event(s, user, type, lines, idempotency_key, ref_type, ref_id)` | The only way to change stock. Cook confirm: one `ChangeBatch` per confirmed line. Shop confirm: one `NewBatch` per item bought. Returns the `InventoryChange` your endpoint returns |

The full rules of `apply_stock_event` (idempotency, revision check, what `changes` may hold) are in [Role 2's README](../db/README.md#role-5-changing-stock).

**Freshness is computed by Role 2, not by you.** Read `freshness_status` and apply the gate: `expired` is not stock, `check` is asked about and never promoted. Turn `est_use_first_date` into urgency when scoring, with `clock.today()`.

## Recipes

One file per recipe in `backend/seed/recipes/`, in the format in [seed/README.md](../../seed/README.md). In short:

- A fixed UUID in each file; never change it, because ratings and stars refer to it.
- Ingredients are named by `canonical_name`, exactly as in Role 2's `ingredients.csv`.
- No `diet_flags` or allergens in the file. The loader computes them from the ingredients: a recipe suits a diet only if every ingredient does, and its allergens are the union of its ingredients'.
- `cuisine`, `equipment` and `taste_tags` take only the values in `app/schemas/common.py`.

Role 2 builds the ingredient catalogue from your recipes, so **send them your ingredient list early**.

The [catalogue handoff](../../../docs/role5-handoff.md) contains 48 complete
recipes (28 bases and 20 variants), a synchronised recipe index, the same 42-name
ingredient request list and a validator. No outlines remain. Each recipe
includes its meal portions and any accompanying rice, noodles or potatoes, so
availability checks and basket generation must include those components.
Existing UUIDs are preserved. Wenlong approved all 48 recipe contents on
2026-10-20, recorded in `seed/recipe_review.yaml`; all flags are `reviewed: true`.

The [recipe review guide](../../../docs/recipe-review.md) provides all recipe
cards, selection rationale, named external concept/technique references and
human review checks. The prose is original and AI-assisted; source references
do not establish human approval or validate the adapted quantities, timings,
dietary suitability or nutrition. `seed/recipe_review.yaml` stores review
coordination metadata and adds no runtime fields to the recipe format.
Human approval covers the recipe content. Cooking trials have not been performed.

Use the existing taste-tag vocabulary consistently:

- `low_oil`: at most 5 ml total added cooking oil, including seasoning oils,
  per two servings. This is a cooking-method tag, not a total-fat claim.
- `high_protein`: reserved for an explicit protein addition to a base recipe;
  it is a qualitative ranking feature pending nutrition metrics, not a label
  inferred for every animal-protein or legume recipe.
- `vegetable_rich`: at least 300 g of the defined vegetable set per two
  servings. The review guide details the counted ingredients and the other
  transparent authoring heuristics; this is a culinary feature, not a
  nutrition claim.
- Equipment lists mean AND: all listed appliances are required. Total times
  include meal staples and can assume the stated parallel cooking.

Role 2 still needs to turn the ingredient request list into authoritative
catalogue rows, settle water's assumed-available/no-purchase treatment, and
agree count/weight/pack conversions. Role 4 consumes that same final catalogue.
The reviewed recipe set does not itself implement the loader, recommendation
algorithms or Cook/Shop services; those integration tasks remain.

## Tasks, in order

1. **Recipes first**, because Role 2's catalogue comes from them. Lean towards everyday Singapore home cooking. Use only original or properly licensed content: the repository is public.
2. `reco/` as pure functions, tested with fixture data: filter, score, suggest, adjust, build a basket. None of this needs the database.
3. Wire the Cook and Shop services to sessions and to Role 2's functions. Their stubs return sample data, so this can start now.
4. Fill `needs_check` and `freshness_check`, and return `NO_RESULT` as described above.
5. Ratings: Like and Dislike adjust `taste_weights` as in SPEC B5; Maybe and "Not tonight" do not.
6. 100 scenarios in `eval/reco_scenarios/`, keeping 30 unseen during development, plus property-based tests that an allergen never appears in any output.

**Done when** all 100 scenarios pass, and Cook and Shop work on the deployed stack against real inventory.
