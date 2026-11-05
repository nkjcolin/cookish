# Role 5 service integration handoff

The pure engines now have a service orchestration layer:

- [`RecommendationWorkflow`](../backend/app/services/recommendation_workflow.py)
  implements Cook/Shop sessions, history, selection, confirmation and ratings.
- [`RecommendationRepository`](../backend/app/services/recommendation_repository.py)
  defines the internal persistence port and saved records.
- [`test_recommendation_workflow.py`](../backend/tests/test_recommendation_workflow.py)
  exercises these flows with a transactional test double.

**Current draft status (5 November 2026):** Cook/Shop endpoints use
[`SqlRecommendationRepository`](../backend/app/services/recommendation_sql.py).
It reuses Role 2's catalogue, preferences, inventory and stock-event services in
one transaction. The new migration `e51c9a8d7201` adds snapshots, ordered learning
and confirmation response storage; the original migration is unchanged.

The [storage design](role5-storage-proposal.md) describes the migration for Role
2 review, mapping choices and locking. Deployment is not performed by this PR.
The pure workflow tests use a test double; the additional SQL tests under
`backend/tests/db/test_recommendation_sql_db.py` use real PostgreSQL.

## What is implemented

| Flow | Implemented behavior |
|---|---|
| Start Cook | Load household preferences, inventory, catalogue and learned weights; suggest; save history and remembered people in one transaction. |
| Adjust / Not this | Apply accumulated adjustments or exclusions, then rerank using current household data. Valid restrictions/skips persist even when no recipe fits; no history entry is invented. Skips do not train taste weights. |
| Previous | Move through saved suggestions without rescoring. Restore displayed portions, retain accumulated constraints, and recheck current hard constraints. Historical suggestions that no longer meet soft adjustments cannot be selected. |
| Select | Recheck current hard/session constraints and essential stock; save a recipe snapshot and proposed batch consumption. Counted consumption follows earliest use-first date and spills into later batches. Repeated selection returns the existing record. |
| Confirm Cook | Validate exactly the saved proposed batch IDs, revisions, tracking modes, units and freshness. Apply corrected final counts/states through the stock-event port. Save confirmed record, provisional learning and retry response together. |
| Feedback | Require a confirmed record in the household. Replace its learning evidence using the saved recipe features; retain who submitted the update. Ratings remain available after session expiry. |
| Start / adjust Shop | Plan and save a basket with stable item IDs and purchase metadata. Each adjustment creates a fresh basket and marks the old one abandoned atomically. |
| Confirm Shop | Validate the saved basket's line IDs and actual purchases. Convert counted packs using the saved pack definition; create new batches without merging old stock. Save resolved actual pack counts and a retry response. |

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
confirmation. The stock-event port must support an empty line list and an event
with no inventory changes, or the roles must agree a different response policy.
The existing internal signature accepts a list with no minimum. An entirely
empty Shop basket has no purchase to confirm; the public request schema still
requires at least one line and is unchanged.

## Repository adapter responsibilities

Every repository instance must use a single SQLAlchemy transaction. All queries
and writes receive the authenticated household ID; record/session rows also
retain their creator's user ID. Reject foreign rows as `NOT_FOUND`.

| Port method | Role 2 / Role 5 implementation |
|---|---|
| `preferences(household_id)` | Call Role 2 `get_preferences(s, household_id)`. |
| `inventory(household_id)` | Call Role 2 `get_inventory_snapshot(s, household_id)`, with freshness already computed. |
| `catalogue(household_id)` | Role 5 queries the seeded recipes and ingredient tables. Resolve ingredient UUIDs, review flags, household stars, complete allergen/diet metadata and purchase conversions. |
| `remember(...)` | Update only the requested `last_cook_people`, `last_shop_people`, `last_shop_meals` fields; do not overwrite other household preferences. |
| Session / record / basket reads and saves | Role 5 queries Role 2's models. Lock existing rows before mutations; retain snapshots and history described below. |
| `learning` / `save_learning(..., user_id=...)` | Load ordered confirmed-meal evidence and current ratings. Serialize updates per household; save evidence, acting user and derived `taste_weights` together. |
| `confirmation` / `save_confirmation` | Reserve/check the household key, compare operation/target/request, and persist the exact successful response. |
| `apply_stock(...)` | Delegate to Role 2 `apply_stock_event(s, user, event_type, lines, key, ref_type, ref_id)` in the same transaction. Never write inventory directly. |

The adapter must not call a second independent transaction for stock or learning.
A failure after the stock event, including saving the response, must roll back
all effects. The workflow intentionally does not catch and suppress these failures.

### Locking and request retries

- Lock the household/key combination before confirmation work, **including when
  no row exists yet**. A read followed by an unprotected insert is insufficient.
  Coordinate this with Role 2's existing unique stock-event key; keys are shared
  with manual inventory operations, not private to Cook and Shop.
- If the same household key already belongs to a different operation, target
  or request body, raise `CONFLICT`. If a stock event already exists for another
  workflow and there is no matching saved confirmation, do not apply a second
  event or create a successful response for the wrong operation.
- Lock cook records and baskets so a second confirmation with a different key
  sees the confirmed status and is rejected. Serialize selection on the session
  so concurrent Select requests cannot create multiple records.
- Shop adjustment locks session then current basket. Shop confirmation locks
  only the basket, avoiding an inverse session/basket lock order. A replacement
  basket and abandonment of the old basket commit together.
- Role 2 must still check stock revisions inside `apply_stock_event`; checking
  them earlier in the service does not eliminate concurrent edits.
- Feedback edits serialize the record and household learning state. An HTTP
  retry must not append another feedback sample.

Start/adjust/next requests currently have no idempotency key in the public API.
This layer does not claim retry deduplication for those actions. Adding such a
contract would require Role 1 agreement. Confirmation retries are covered by the
existing key header.

## Snapshot storage implemented in this draft

The internal dataclasses are serialized into versioned JSON snapshots by the SQL adapter. The new migration remains subject to Role 2 review. The storage design covers:

1. Saved suggestion responses and the current history position, accumulated
   engine state, selected-record link and fixed expiry.
2. A selected record's recipe/feature snapshot and proposed batch snapshots.
   Keeping only a recipe ID is insufficient when recipe content later changes.
3. The basket's purchase conversion snapshot, all saved item IDs, and resolved
   actual bought/pack values. The port retains these separately from suggestions.
4. First-confirmation order and current rating per cooking record, with the
   acting user for feedback audit. The clipped weight map alone cannot support
   correct rating replacements.
5. Household-scoped confirmation keys, normalized request content and exact
   response snapshots. An idempotent stock event alone does not prevent duplicate
   feedback or a second basket/record update.

Use existing JSON fields/relations where suitable; Role 2 owns any additional
columns, constraints and migrations. No invented ingredient IDs or fixture
allergen/pack metadata should be used in production.

## Wiring and review checklist

1. Implemented: the SQL port uses Role 2's models and the new snapshot migration, pending Role 2 review.
2. The installed unit-of-work factory is:

   ```python
   from contextlib import contextmanager
   from app.db.session import transaction

   @contextmanager
   def recommendation_uow():
       with transaction() as session:
           yield SqlRecommendationRepository(session)
   ```

3. The public services construct `RecommendationWorkflow(recommendation_uow)`
   and keep every existing signature, delegating as follows:

   | Existing service function | Workflow method |
   |---|---|
   | `cook.start_session` / `adjust` | `start_cook` / `adjust_cook` |
   | `cook.next_suggestion` / `previous_suggestion` | `next_cook` / `previous_cook` |
   | `cook.select` / `confirm` / `give_feedback` | `select_cook` / `confirm_cook` / `feedback` |
   | `shop.start_session` / `adjust` / `confirm_basket` | `start_shop` / `adjust_shop` / `confirm_shop` |

4. Recipe details, persisted stars and use-first reads are implemented. A
   recent-cooked repetition window still needs agreement; the workflow supplies
   learned weights but does not infer a time window from undated evidence.
5. PostgreSQL CI covers concurrent confirmation/selection, stale revisions,
   simultaneous feedback edits, household isolation, manual stock-key races,
   failure rollback, exact replay and snapshots surviving catalogue changes.
   It also compares the migrated schema with the declared models.

Validation at implementation commit `73e4186`: backend, frontend and AI CI pass.
Backend CI requires PostgreSQL (`REQUIRE_DB=1`), so database tests cannot silently
skip. Local checks passed 301 tests excluding database, HTTP contract and auth
suites; local PostgreSQL is unavailable. All 70 development scenarios and 85
steps pass. Those scenarios are offline engine evidence, not deployed results.

The migration remains in draft for Role 2 review. Still required: deployed
frontend/backend checks, the 30 independent held-out scenarios, measured cloud
costs and elasticity evidence. No production migration or deployment was run.
