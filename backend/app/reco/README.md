# Role 5 — Recommendation and recipes

You own what Cookish suggests: the recipe catalogue, the Cook and Shop algorithms, and the services that turn them into sessions, suggestions and baskets. Read [docs/init.md](../../../docs/init.md) first for the conventions everyone follows.

The design is in [SPEC.md](../../../docs/SPEC.md), **B5**: the Cook algorithm (hard filter, availability, score, adjustments, learning from ratings), the freshness gate, the Shop algorithm and the use-first estimate. **A6** has the tables for sessions, ratings and baskets.

## What you own

| Path | Contents |
|---|---|
| `backend/app/reco/` | Pure Cook and Shop planning, stock assessment, scoring, adjustments and feedback learning |
| `backend/seed/recipes/*.yaml` | Target: 40 to 60 reviewed recipes; 48 AI-assisted recipes have human content approval; no cooking trials |
| `backend/app/services/cook.py` | `start_session`, `adjust`, `next_suggestion`, `previous_suggestion`, `select`, `confirm`, `give_feedback`, `get_recipe`, `set_star`, `use_first` (optional) |
| `backend/app/services/shop.py` | `start_session`, `adjust`, `confirm_basket` |
| `eval/reco_scenarios/` | 70 development scenarios (40 Cook, 30 Shop); 30 held-out scenarios reserved |

You also own the taste-tag list in `app/schemas/common.py` (change it through the contract procedure), and the business case and pricing section of the final report.

The [business case draft](../../../docs/business-case.md) now has market and
competitor references, traceable review evidence and a reproducible initial cost
model. Workload and payment assumptions remain provisional; Role 3's measured
costs and user research are still required.

## What already exists

- **Cook/Shop services now use the SQL workflow.** Sessions, recipe selection,
  confirmations and ratings call `RecommendationWorkflow` through
  `SqlRecommendationRepository`; recipe details, stars and use-first also use
  real database services. Apply migration `6f2c8d471a90` before deploying these
  endpoints. The new integration has not yet been verified on AWS.
- **Role 2's functions you call**, now implemented against PostgreSQL: household preferences, inventory snapshots and stock events. The agreed signatures are unchanged.
- **`app/db/session.py`**: `transaction()`, one per request.
- **`app/clock.py`**: today's date in Singapore.
- **The recipe file format**, agreed with Role 2, in [seed/README.md](../../seed/README.md).
- **The pure Cook/Shop engines and learning**, described below, with separate engine, workflow and database tests.

On 7 November 2026, Wenlong explicitly authorised the required database models
and migration as an exception to the normal Role 2 ownership boundary. See the
[storage handoff](../../../docs/role5-storage-proposal.md) for the added snapshots,
learning evidence and confirmation replay records. This does not transfer
ownership of unrelated inventory or database work.

## Implemented database reads and catalogue services

The [Role 5 report draft](../../../docs/role5-report-notes.md) explains cold start,
recipe provenance, household feedback updates and evaluation terminology, with
implementation references and the current integration limits.

### Use first

`cook.use_first` now calls Role 2's `get_inventory_snapshot` for the authenticated
household and delegates to the pure `reco/use_first.py` function. It returns only
`use_soon` batches with a non-past date and known positive counted stock or a
state of `enough`/`low`. Unknown/out states, absent/invalid counts or units, and
stale perishable confirmations are excluded. Freshness statuses and estimated
dates are read unchanged from Role 2's snapshot; no shelf-life policy is duplicated.

Dates are ordered earliest first, then acquisition date and batch ID; batches are
never merged. `days_left` uses the Singapore date. Empty kitchens return an empty
list. The snapshot's `use_soon` status currently covers today through three days
ahead; the Cook ranking's four-day urgency coefficient is a separate policy.
The endpoint is read-only for inventory and retains the existing API schema.
Frontend integration and reminders are not part of this implementation.

### Recipe detail and household stars

`cook.get_recipe` and `cook.set_star` now delegate to the Role 5
[`recipe_details`](../services/recipe_details.py) service using the existing
recipe, ingredient and feedback tables. Detail returns reviewed catalogue content
with household-specific star state; unknown or unreviewed IDs return `NOT_FOUND`.
The existing public signatures and response schemas are unchanged.

Star/unstar records the acting user in `recipe_feedback`, independently of cooked
ratings and learned taste weights. A household row lock serializes these actions;
repeating the current value creates no extra event. New event timestamps advance
past the prior star event even if clocks tie or move backwards. Detail and the
engine input reader use the same latest-event ordering. Other households' stars
are isolated; household members share their household's state.

Recipe details and stars themselves need no new database model or migration. The PostgreSQL tests in
`tests/db/test_recipe_details_db.py` cover all 48 detail responses, HTTP star
round trips, unknown/unreviewed IDs, household/member scope, concurrent updates,
event ordering, and rollback. These endpoints require the seeded catalogue.
The SQL Cook/Shop workflow now returns seeded catalogue IDs, including from
selection, so its recipe details resolve against the same data. Legacy mock IDs
remain invalid; no aliases or fabricated catalogue rows are introduced.

### Catalogue input reader

The [real-catalogue quality review](../../../docs/role5-catalogue-quality-review.md)
records the fixed non-buyable-essential planning gap and the remaining quantity
resolution and purchase-entry gaps. Resolve the remaining findings before the
final implementation freeze.

[`SqlRecommendationInputs`](../services/recommendation_inputs.py) reads the 48
reviewed recipes and 42 authoritative ingredients, household stars, preferences
and inventory in the caller's transaction. It supplies the existing pure engine
types without guessing counts, pack conversions or missing safety metadata.
It is the read component used by `SqlRecommendationRepository`.

The [storage handoff](../../../docs/role5-storage-proposal.md) records the implemented
snapshots, ordered learning evidence, confirmation replay storage and catalogue
mapping choices. The SQL adapter and versioned snapshot codecs are in
`services/recommendation_sql.py` and `services/recommendation_snapshots.py`.

`tests/test_recommendation_inputs.py` validates all delivered seed content at the
mapping boundary. `tests/db/test_recommendation_inputs_db.py` exercises real
Postgres reads, both engines, review filtering, optional-ingredient dietary
checks, household isolation and transaction rollback. CI requires Postgres for
these tests; a local run without Postgres skips them.

## Cook engine: implemented milestone

`cook.py` implements `filter_recipes`, `score_recipe`, `suggest`, `adjust`,
`skip_current`, `new_session` and `to_suggestion`. `inventory.py` scales amounts
and classifies stock. `models.py` defines internal inputs and results;
`config.py` contains all initial scoring weights. These modules perform no I/O,
database access, live clock reads or session persistence.

The **Cook/Shop session, confirmation and rating endpoints are wired to the SQL
adapter**. The [integration handoff](../../../docs/role5-integration.md) describes
the repository, snapshot validation and transactional confirmation/feedback
storage. Deployment requires migration `6f2c8d471a90`; deployed recommendation
flows remain to be verified. The
[development scenario suite](../../../eval/reco_scenarios/README.md) now contains
70 cases; the 30 independently authored held-out cases remain reserved.

### Inputs and integration

The service adapter supplies:

| Input | Required meaning |
|---|---|
| `Candidate` | Existing resolved recipe shape plus the stored `reviewed` flag. Ingredient UUIDs must be resolved from Role 2's catalogue. Unreviewed recipes are excluded. |
| `dict[UUID, CatalogIngredient]` | Authoritative ingredient identity, allergens, diet flags, tracking mode, staple flag and a perishable classification. All fields are required. Missing metadata excludes the entire recipe, including optional ingredients. These internal fields do not change the public ingredient response. |
| `list[InventoryItem]` | Household-scoped snapshot from `get_inventory_snapshot`; removed items excluded and freshness already computed by Role 2. Free-text/unmapped batches cannot satisfy a canonical ingredient. |
| `Preferences` | Current household preferences; all requested diets and all required equipment must be satisfied. |
| `CookSession` | People, accumulated constraints, shown/skipped/history IDs, and an optional explicitly strict time cap. New sessions use the remembered people count. |
| `as_of` | A timezone-aware instant from `app.clock.now()`, passed once by the service. Scoring uses its Singapore date. |
| `taste_weights` | Optional household feature map. An omitted map means zero learned preference. No history is invented. |

`SqlRecommendationInputs` maps `CatalogIngredient.perishable` using Role 2's
`PERISHABLE_CATEGORIES` and the stored ingredient category, not recipe names.
Main-protein learning features still need an agreed authoritative mapping. The engine
reads `tag:<tag>` and `cuisine:<cuisine>` weights. `learning.py` produces those
weights from confirmed cooking and subsequent feedback.

Engine calls made within the persisted service workflow:

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
not train preferences. The SQL workflow persists and replays these states,
applies session expiry and serializes household mutations within a transaction.
`previous` replays the saved entry rather than calling the engine again.

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
  `unknown`; a coarse amount cannot be compared to a numeric count. An explicit
  `unknown` state overrides any retained old numeric count.
- A perishable last confirmed over 14 days ago becomes `unknown`. No
  confirmation check is imposed on non-perishables by this rule.
- Trust the snapshot's freshness gate: `expired` contributes no stock; `check`
  contributes no confirmed stock and is returned for inspection. Both retain
  real batch IDs. Even a recently confirmed usable batch earns no urgency bonus
  for a date already past.
- An untracked staple is assumed available. Explicit tracked `out`, expired or
  uncertain stock overrides that assumption. Use Role 2's stored staple flags;
  the delivered catalogue already marks water as a staple.
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

## Shop engine: implemented milestone

`shop.py` provides `new_shop_session`, `adjust_shop`, `plan_shop`,
`shopping_list` and `to_basket`. `shop_models.py` holds internal inputs/results.
Use `plan_shop` for hard filtering before shopping; the lower-level
`shopping_list` assumes its caller has already selected eligible meals.

In addition to the Cook inputs, the adapter supplies a `PurchaseSpec` for every
eligible ingredient: category, explicit `buyable` flag, purchase unit, size and
measure, and the estimated shelf life at default storage. Pack fields must be
complete or all null. Missing rows raise an integration error rather than
silently dropping an ingredient or treating it as safe. `buyable=False` is an
explicit catalogue policy for something such as household tap water or cooked
rice; the engine does not infer it from a name. The SQL input reader supplies
this metadata from Role 2's ingredient catalogue.

The algorithm is deterministic and bounded, with no optimality claim:

1. Apply the same review/allergen/diet/equipment/strict-time gate as Cook.
   Before selecting families or taking the top candidates, exclude recipes with
   essential, non-staple, non-buyable ingredients not confirmed available at home.
   These require `have`: missing, low, unknown, stale, expired or unchecked stock
   cannot be replenished by a shopping line. Optional ingredients and assumed
   staples do not trigger this gate. Score the remaining recipes by learned/static
   preference and effort, ignoring buyable stock for admission. The public
   preferred time remains a soft penalty.
2. Keep the best-scoring variant in each family, then take at most 20 families.
   Choose up to the requested number of meals by beam search of width 10.
   No dish family repeats. Recheck non-buyable essential requirements across each
   whole combination, scaling by people and counting each usable batch once.
   If the bounded search cannot fill the requested plan, retry smaller sizes;
   report the actual meal count. An empty plan follows the existing `NO_RESULT`
   service path. State-tracked `enough` remains a state, not a numeric quantity.
3. Score combinations with preference/effort, +0.5 per shared non-staple
   occurrence beyond the first, +1 per ingredient with confirmed usable stock,
   +0.5 per additional cuisine, and −0.5 per leftover pack fraction.
   Main-protein variety awaits authoritative metadata. Coefficients are hand-set
   in `config.py`; these are not evaluation results.
4. Aggregate all ingredients, including optional ones and meal staples, scaled
   by people/recipe servings. Subtract each compatible confirmed counted batch
   once across the entire plan, then round the deficit up to whole packs.
   Rational arithmetic preserves exact decimal quantities during aggregation.
5. State-tracked ingredients marked `enough` and confirmed within 14 days are
   omitted. `low`/`out`/absent ingredients are included with the planned amount;
   no numeric stock or pack count is invented for state tracking. This
   confirmation rule applies to pantry stock too. Untracked staples retain the
   documented assumed-available policy.
6. `unknown`, stale/future/invalid confirmations, tracking/unit mismatches and
   freshness `check` stay visible with `needs_check=True`. Confirmed stock can
   reduce the tentative purchase; uncertain stock cannot. An uncertain second
   batch stays visible even when a confirmed batch already covers the plan.
   Expired stock never reduces a purchase. Refresh the inventory and rebuild
   the basket after a check; no stock is changed by planning.

For example, two meals needing three eggs each for two people become twelve
eggs for four people. With five confirmed eggs at home and ten eggs per tray,
the basket suggests one tray, with three eggs left over. If the five eggs are
uncertain, the tentative list suggests two trays and says to check at home.

Coarse or conflicting recipe units, missing pack metadata and incompatible
purchase measures retain the item with `suggested_packs=None` and an explicit
quantity/unit check. Counts are not converted between pieces and grams. A
suggestion over the existing 50-pack confirmation limit is similarly flagged.
**The service must resolve these cases or reject confirmation with an existing
validation error; it must never treat null as a verified one-pack purchase.**
The nullable public field is unchanged; this unresolved-counted-item behavior
still needs Role 1/2 UI and quantity-resolution work; SQL wiring does not resolve it.

`more_vegetables` adds +2 for `vegetable_rich`. `longer_lasting` adds up to +1
from mean non-staple shelf life, capped at 30 days; unknown life earns zero.
These tags bias ranking rather than eliminate all candidates.
`cover_more_meals` increases the request by one per deliberate adjustment,
capped at seven, unless the same patch explicitly supplies `meals`.
Tags accumulate; people and explicit meal counts can change in either direction.
Confirmation retries must replay their saved result. Start/adjust requests have
no idempotency key in the current public API; retry deduplication for those actions
is not implemented or claimed by the workflow.

`ShopPlan` retains the requested count; `to_basket` reports the actual number
of planned meals in `Basket.meals`. It derives stable item UUIDs from the saved
basket UUID and ingredient UUID. Persist those exact IDs for confirmation;
assign a fresh basket UUID to a new basket revision. An empty plan means no
eligible recipes remain after hard filtering and the non-buyable-essential
stock gate: map it to `NO_RESULT` with `relaxable: []`. A valid plan
with every ingredient at home can have zero purchase items. There are no prices,
cost totals or budget promises.

## Feedback learning: implemented milestone

`LearningState` belongs to one **household**, matching SPEC A6. This is not a
separate model for each household member. `learn` accepts a trusted cook-record
ID, its unchanged recipe/features, confirmed status and optional rating;
`taste_weights` returns the map consumed by both Cook and Shop.

| Evidence for one cooked meal | Feature contribution before clipping |
|---|---|
| Confirmed cooked, no rating yet | +0.0625 (step/4) |
| Like | +0.25 |
| Maybe | 0 |
| Dislike | −0.25 |
| Selected, skipped or abandoned | 0; a rating is rejected before confirmation |

The step is 0.25 and each feature is clipped to [−2, +2]. A meal contributes to
each distinct taste tag and its cuisine. A Like on a Chinese `low_oil` recipe,
for example, increases `cuisine:chinese` and `tag:low_oil` by 0.25 each before
clipping. A future recipe sharing both features gains 0.5 preference points;
one sharing only the cuisine gains 0.25. Hard filters still run first.

SPEC B5 mentions both no-rating neutrality and a small cooked-without-rating
reward. The implemented interpretation is a **provisional cooking reward**:
a later rating replaces it. Thus Like totals +0.25, not +0.3125, and Maybe
removes the provisional contribution so that meal has no taste effect.
No separate reward is given just for a missing feedback request.

The state holds one evidence entry per cook record in first-confirmation order.
Retries are no-ops; a late confirmation retry cannot erase a rating. Changed
ratings replace the same entry. The engine replays evidence, clipping after
each meal, because subtracting an old delta from a saturated weight loses
information. Recipe identity/features for an existing entry cannot change.
The current state starts from zero, rather than importing already clipped
weights without their evidence.

**Persistence:** the SQL adapter retains first-confirmation order, frozen
features and current ratings in `recommendation_learning`. It saves the evidence,
derived `preferences.taste_weights` and feedback events in the same household-scoped
transaction. The workflow checks ownership and confirmed status before learning;
the pure function is not an authorization layer. Legacy nonempty weights without
evidence are rejected for an explicit migration decision rather than reset.
Replaying evidence is linear in meal history and is acceptable for the
prototype; later compaction must preserve rating-edit semantics. The storage
migration changes no public API schema.

### Validation and remaining work

Run from `backend/`:

```bash
uv sync --frozen
uv run pytest tests/test_reco.py tests/test_shop.py tests/test_learning.py
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
Shop and learning tests cover aggregate stock subtraction, serving/pack
arithmetic, uncertain/freshness cases, family diversity, adjustments, unchanged
basket schema, bounded feedback, retries and replacement after saturation.
Two additional property tests generate 80 Shop cases and 80 feedback sequences.
A structural integration test loads all 48 approved recipe files and produces
a seven-meal plan with explicit synthetic metadata; it does not validate the
authoritative catalogue. Separate input-reader and real-catalogue tests exercise
Role 2's delivered 42 ingredient rows and the 48 reviewed recipes.

These unit, property and workflow tests remain separate from the report
scenario suite. The [scenario runner](../../../eval/reco_scenarios/README.md)
evaluates 70 development cases (40 Cook and 30 Shop), with checks after the
initial result and every adjustment, exact basket expectations and source-hash
provenance. Its fixture clock is `2026-10-24T12:00:00+08:00`. Its small synthetic
recipe records are separate from the 48 approved seed recipes.

The separate frozen-evaluation runner is implemented and rehearsed using
development copies, with zero held-out cases executed. It preserves source/input
hashes and first-attempt evidence and labels subsequent runs as regressions.
The 30 held-out scenarios have not been authored or used for tuning here.
They must remain unseen until a frozen implementation is evaluated, with the
first result preserved and reported separately. See the scenario README for
the protocol; no held-out pass claim is made.

The SQL adapter, real stock confirmations and retry-safe feedback persistence
passed [CI at `5c8ca30`](https://github.com/nkjcolin/cookish/actions/runs/42341902849):
547 backend tests, including the new migration test and 18 SQL workflow tests;
frontend and AI jobs also passed. This is PostgreSQL CI evidence, not an AWS
journey test. Held-out and deployed evaluation remain pending. No synthetic
test metadata should be seeded as the authoritative ingredient catalogue.

## What you may change, and what you must keep

**Yours to decide:** everything in `reco/`; the bodies of the Cook and Shop services; scoring weights (keep them in one config file and report them); the recipes; the queries on your own tables.

**Keep, because others depend on them:**

- The name, parameters and return type of every service function. The routers and the frontend call them.
- The recipe file format: Role 2's loader reads it.
- The table structure normally belongs to Role 2. Wenlong explicitly authorised
  migration `6f2c8d471a90` and its models on 7 November 2026 to complete this
  integration; future unrelated schema changes still require coordination.

## What the frontend expects from you

Keep the existing API expectations below. The [quality review](../../../docs/role5-catalogue-quality-review.md)
records unresolved quantity-check, purchase-entry and empty-stock navigation
issues for agreement with Roles 1/2; this section does not claim a completed UI flow.

- **Adjustments only add conditions.** `POST /cook/sessions/{id}/adjust` adds to what the session already holds; there is no way to remove one. To remove a condition, the frontend starts a new session and sends the rest again, and its **Reset** button starts a session with none.
- **Quick checks.** `Suggestion.needs_check` lists, for each essential ingredient of unknown stock, the batch to use first (`StockCheck.item`). `freshness_check` lists the batches whose `freshness_status` is `check`, with a reason. The frontend asks about exactly these before cooking and saves each answer on that batch with `PATCH /api/inventory/items/{id}`.
- **"No, I don't have it".** The frontend records that batch as `out`, then calls `POST /cook/sessions/{id}/next`. The next suggestion must reflect the new stock. The `skipped` signal that `next` records must not change taste weights.
- **Nothing fits.** Raise `ApiError(ErrorCode.NO_RESULT, …, {"relaxable": [...]})`. `relaxable` may contain only `"max_minutes"` and `"tags"`, and never a hard constraint. Shop returns fewer meals when possible. If no recipe remains after hard filtering and the non-buyable-essential stock gate, return `NO_RESULT` with an empty `relaxable`.
- **Expiry.** A session expires 12 hours after it starts. New session operations and first confirmations require an unexpired session. A previously successful confirmation with the same key/request replays its saved response after expiry; ratings for confirmed records also remain available. The SQL adapter persists the required response and learning evidence.
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

Role 2's ingredient catalogue and loader are delivered. Coordinate future recipe
ingredient additions or renaming through the existing handoff format.

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

The delivered catalogue includes water's staple/non-buyable policy and purchase
definitions. Recipe-to-inventory quantity resolution remains a shared decision;
existing purchase metadata does not authorize guessed count/weight conversions.
Role 4 consumes the same authoritative catalogue.

## Remaining Role 5 work

1. Coordinate migration `6f2c8d471a90` and backend deployment with Role 3.
   The SQL integration's PostgreSQL CI tests pass. Start fresh sessions after
   deployment; legacy rows without snapshots require a restart.
2. Resolve recipe quantity checks and counted shopping confirmation with Roles
   1/2, preserving uncertainty. Role 5 owns the recipe/engine behavior; UI and
   ingredient/schema changes remain with their respective owners.
3. Agree the recent-cooked history window and main-protein feature mapping, then
   supply those ranking inputs. Existing cuisine/tag learning is already implemented.
4. Freeze the completed implementation, obtain 30 independently authored unseen
   scenarios, and run the prepared held-out workflow. The 70 development cases
   and property tests are already available; held-out results must be separate.
5. Verify Cook/Shop against real inventory on the deployed stack after migration.
   Finalise the report and pricing conclusions with Roles 3/4's measured costs.

**Done when** all 100 scenarios pass, and Cook and Shop work on the deployed stack against real inventory.
