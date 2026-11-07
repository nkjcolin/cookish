# Role 5 service integration handoff

Status on 7 November 2026: the public Cook/Shop services now delegate to the
real engines through a PostgreSQL repository. Wenlong authorized the required
storage additions for this integration. Migration `6f2c8d471a90` and the updated
backend are deployed. PR #26's frontend preview and exact-name inventory matching
are also live. Core user-flow checks passed; see the verification section below.

The implementation consists of:

- [`RecommendationWorkflow`](../backend/app/services/recommendation_workflow.py)
  implements Cook/Shop sessions, history, selection, confirmation and ratings.
- [`RecommendationRepository`](../backend/app/services/recommendation_repository.py)
  defines the internal persistence port and saved records.
- [`SqlRecommendationRepository`](../backend/app/services/recommendation_sql.py)
  implements that port using one household-scoped SQLAlchemy transaction.
- [`recommendation_snapshots.py`](../backend/app/services/recommendation_snapshots.py)
  validates and serializes the saved records.
- [`test_recommendation_workflow.py`](../backend/tests/test_recommendation_workflow.py)
  exercises these flows with a transactional test double.

The [SQL input reader](../backend/app/services/recommendation_inputs.py) supplies
reviewed recipes, ingredient metadata, household preferences and inventory.
Stock changes still go through Role 2's `apply_stock_event`; no competing
inventory writer was added. The [storage record](role5-storage-proposal.md)
describes the new models and migration. The test double remains confined to
`backend/tests/`; production no longer uses it or mock Cook/Shop responses.

Recipe detail and star/unstar are implemented independently in
[`recipe_details.py`](../backend/app/services/recipe_details.py), using the existing
tables and public service signatures. They return reviewed catalogue recipes and
persist household-scoped stars. New suggestions and selected records use actual
catalogue recipe IDs, so recipe details use the same identity. Old mock IDs still
return `NOT_FOUND`; users must start a new session after deployment.

The optional `cook.use_first` endpoint also reads real inventory, using Role 2's
freshness snapshot and Role 5's pure ordering/filtering function. It requires no
additional persistence, migration or API fields.

## Workflow behavior

These flows are implemented in the shared workflow and are wired to SQL.
The original integration's [CI](https://github.com/nkjcolin/cookish/actions/runs/42342203535)
included migration preservation and 20 PostgreSQL workflow tests. The later
[PR #26](https://github.com/nkjcolin/cookish/pull/26) passed 606 backend tests,
38 frontend tests and the AI job, including the protein/history additions.

| Flow | Implemented behavior |
|---|---|
| Start Cook | Load household preferences, inventory, catalogue, learned weights and recent cooked meals; suggest; save history and remembered people in one transaction. |
| Adjust / Not this | Apply accumulated adjustments or exclusions, then rerank using current household data. Valid restrictions/skips persist even when no recipe fits; no history entry is invented. Skips do not train taste weights. |
| Previous | Move through saved suggestions without rescoring. Restore displayed portions, retain accumulated constraints, and recheck current hard constraints. Historical suggestions that no longer meet soft adjustments cannot be selected. |
| Select | Recheck current hard/session constraints and essential stock; save a recipe snapshot and proposed batch consumption. Counted consumption follows earliest use-first date and spills into later batches. Repeated selection returns the existing record. |
| Confirm Cook | Validate exactly the saved proposed batch IDs, revisions, tracking modes, units and freshness. Apply corrected final counts/states through the stock-event port. Save confirmed record, provisional learning and retry response together. |
| Feedback | Require a confirmed record in the household. Replace its learning evidence using the saved recipe features; retain who submitted the update. Ratings remain available after session expiry. |
| Start / adjust Shop | Plan and save a basket with stable item IDs and purchase metadata. Each adjustment creates a fresh basket and marks the old one abandoned atomically. |
| Confirm Shop | Validate the saved basket's line IDs and actual purchases. Convert counted packs using the saved pack definition; create new batches without merging old stock. Save resolved actual pack counts and a retry response. |

Before every Cook ranking, the repository refreshes the household's recently
cooked recipe IDs. The window is the preceding seven elapsed days, inclusive,
using the successful consumption event's `created_at`. Only confirmed records
with a matching same-household consumption event count. Undone and future events
are excluded; selection time and later ratings do not extend the window. Each
recipe receives one repetition penalty (−1 with the default weight), not one per
meal. It remains eligible, and the separate shown-in-session penalty still applies.

New meal evidence includes cuisine, taste tags and the explicit protein categories
in [`protein.py`](../backend/app/reco/protein.py). Eight stable catalogue ingredient
IDs map to poultry, egg, soy, legume, fish and shellfish. Only essential ingredients
contribute; a mixed meal can have several categories, counted once each. Unknown
IDs and optional ingredients add no protein feature. This is a culinary mapping,
not a nutritional claim. Existing cuisine/tag-only evidence keeps its frozen
features on edits and retries; no historical protein rewards are added.

Sessions expire exactly 12 hours after creation. Adjusting a session does not
extend its lifetime. Confirmation of an unconfirmed record/basket requires an
unexpired session. A previously successful confirmation with the same key and
request replays its saved response even after expiry.

For an existing Cook session, `NO_RESULT` is raised after committing the valid
adjustment/skip, so a later request cannot silently forget a restriction. Other
errors roll back. Starting a new session with no eligible result saves nothing,
because the error response supplies no session ID. Shop adjustments that cannot
produce any eligible plan preserve the previous saved basket.

Cook confirmation requires every proposed batch to have either a final count,
a state outcome, or `not_used`. It rejects increasing counted stock through a
consumption event. State outcomes never manufacture a number.
Unknown counts and unresolved essential stock require a stock check before
selection. Optional unusable ingredients produce no proposed consumption.

Shop confirmation requires every saved basket line to say bought or not bought.
For counted purchases, an explicit actual pack count wins over the suggestion;
a null suggestion is never treated as one pack. Missing pack conversion is a
validation error even if the user supplies a pack count. State-tracked purchases
create an `enough` batch with no numeric count. The `bought` confirmation records
what the user actually purchased; `needs_check` does not automatically subtract
uncertain home stock or claim the check was completed.

A confirm where all lines are `not_used`/not bought still represents an explicit
confirmation. Role 2's `apply_stock_event` already supports an empty line list
and a recorded event with no inventory changes, including retry replay. An entirely
empty Shop basket has no purchase to confirm; the public request schema still
requires at least one line and is unchanged.

## Repository adapter responsibilities

Every repository instance uses a single SQLAlchemy transaction. All queries
and writes receive the authenticated household ID; record/session rows also
retain their creator's user ID. Reject foreign rows as `NOT_FOUND`.

| Port method | Role 5 adapter responsibility using Role 2's services/models |
|---|---|
| `preferences(household_id)` | Call Role 2 `get_preferences(s, household_id)`. |
| `inventory(household_id)` | Call Role 2 `get_inventory_snapshot(s, household_id)`, with freshness already computed. |
| `catalogue(household_id)` | Role 5 queries the seeded recipes and ingredient tables. Resolve ingredient UUIDs, review flags, household stars, complete allergen/diet metadata and purchase conversions. |
| `recent_recipe_ids(household_id, as_of=...)` | Read confirmed cook records and their matching, unreverted consumption events within the seven-day window. Refresh before each Cook ranking. |
| `remember(...)` | Update only the requested `last_cook_people`, `last_shop_people`, `last_shop_meals` fields; do not overwrite other household preferences. |
| Session / record / basket reads and saves | Role 5 queries Role 2's models. Lock existing rows before mutations; retain snapshots and history described below. |
| `learning` / `save_learning(..., user_id=...)` | Load ordered confirmed-meal evidence and current ratings. Serialize updates per household; save evidence, acting user and derived `taste_weights` together. |
| `confirmation` / `save_confirmation` | Reserve/check the household key, compare operation/target/request, and persist the exact successful response. |
| `apply_stock(...)` | Delegate to Role 2 `apply_stock_event(s, user, event_type, lines, key, ref_type, ref_id)` in the same transaction. Never write inventory directly. |

The adapter does not open a second independent transaction for stock or learning.
A failure after the stock event, including saving the response, must roll back
all effects. The workflow intentionally does not catch and suppress these failures.

### Locking and request retries

- Every workflow transaction first checks household membership and locks the
  household row with `FOR NO KEY UPDATE`, **including when no session or replay
  row exists yet**. This serializes Role 5 mutations while allowing foreign-key
  checks from manual inventory inserts. The existing stock-event unique key
  arbitrates races with manual writes; keys are shared across these operations.
- If the same household key already belongs to a different operation, target
  or request body, raise `CONFLICT`. If a stock event already exists for another
  workflow and there is no matching saved confirmation, do not apply a second
  event or create a successful response for the wrong operation.
- Lock cook records and baskets so a second confirmation with a different key
  sees the confirmed status and is rejected. Serialize selection on the session
  so concurrent Select requests cannot create multiple records.
- Session, record and basket rows are locked after the household lock. Shop
  adjustment and confirmation cannot race within a household. A replacement
  basket and abandonment of the old basket commit together.
- Role 2 must still check stock revisions inside `apply_stock_event`; checking
  them earlier in the service does not eliminate concurrent edits.
- Feedback edits serialize the record and household learning state. An HTTP
  retry must not append another feedback sample.

Start/adjust/next requests currently have no idempotency key in the public API.
This layer does not claim retry deduplication for those actions. Adding such a
contract would require Role 1 agreement. Confirmation retries are covered by the
existing key header.

## Stored snapshots and legacy data

Migration `6f2c8d471a90` adds nullable session, selection, confirmation and basket
snapshots, plus ordered learning and confirmation-replay tables. The initial
migration is unchanged. Each snapshot has the envelope
`{"schema_version": 1, "kind": "...", "payload": {...}}`; the payload contains
the complete corresponding port record. Missing fields, unsupported versions
and inconsistent identities are rejected rather than defaulted.

The complete row payload includes its recorded expiry, but the adapter replaces
it on reads with `sessions.expires_at`. The relational expiry is authoritative.
Immutable selection and planning snapshots remain separate from confirmed
responses and actual purchases.

Legacy rows have NULL snapshots and must be restarted. Existing nonempty taste
weights without ordered evidence cause `CONFLICT` when the workflow loads
learning; they are not silently reset. Such households need an explicit data
migration decision. New households start with empty learning state.

The protein/history additions use existing fields and tables. They do not change
the public API, Candidate schema or snapshot envelope version.

## Public wiring and deployment checks

`recommendation_workflow(user)` constructs a unit-of-work factory bound to the
authenticated caller. Existing public service signatures and API schemas are
unchanged:

| Existing service function | Workflow method |
|---|---|
| `cook.start_session` / `adjust` | `start_cook` / `adjust_cook` |
| `cook.next_suggestion` / `previous_suggestion` | `next_cook` / `previous_cook` |
| `cook.select` / `confirm` / `give_feedback` | `select_cook` / `confirm_cook` / `feedback` |
| `shop.start_session` / `adjust` / `confirm_basket` | `start_shop` / `adjust_shop` / `confirm_shop` |

Verified on AWS on 7 November 2026:

- Migration returned revision `6f2c8d471a90`, 42 ingredients, 48 recipes,
  20 variants and 383 recipe ingredient lines. No demo household was seeded.
- PR #26's API and frontend release is live. A new account completed onboarding,
  received real Cook/Shop suggestions and opened the cold-start recipe preview.
- A tofu purchase used its catalogue 300 g pack definition and persisted after
  reload. New egg stock linked to canonical egg and used `pcs`.
- Recipe selection, cooking/stock deduction, Maybe feedback and purchase/consumption
  undo were exercised. Test stock was cleaned up afterward.

Future backend releases should still update/invoke the migration function first,
verify its schema/seed response, and then update the API. Restart legacy sessions
with missing snapshots. See [deployment instructions](../infra/deployment.md).

Known remaining gaps are separate from the completed source wiring:

- Recipe preview now works before stock selection. Missing essentials still need
  adding or checking before cooking; preview does not bypass that guard.
- New inventory entries link only through unique exact canonical names or aliases.
  Unknown/ambiguous names remain free text, and old rows are not backfilled.
- Grams, pieces and packs require compatible metadata; no conversion is guessed.
- A 50-VU authenticated read test has run with zero client errors and observed
  API concurrency growth/recovery. It does not test independent-household
  recommendation transactions, stock writes or AI scaling; see the [recorded read-test result](../eval/load/results/2026-11-07-read-only-50-vus.md).
- The final freeze and 30 independent held-out cases remain pending. Unseen
  evaluation follows the [freeze protocol](../eval/reco_scenarios/README.md).
