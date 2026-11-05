# Role 5 database integration: next migration proposal

Prepared 5 November 2026 against `main` at `a360567`. **Implemented in draft PR #21 for Role 2 review.** The new migration `e51c9a8d7201` adds the fields below without changing the original migration or public API. Role 2 retains ownership of database design and migration review. No production migration has been run.

## Available now

`SqlRecommendationInputs` in
[`recommendation_inputs.py`](../backend/app/services/recommendation_inputs.py)
loads reviewed recipes, ingredient metadata, purchase definitions and household
stars from the existing tables. It delegates preferences and inventory reads to
Role 2, using the caller's SQLAlchemy transaction. It is reused by `SqlRecommendationRepository`, which now implements the full persistence port.

The 42 ingredient rows and 48 approved recipes can now feed the pure engines.
Cook/Shop endpoints now delegate to the workflow and SQL repository. Sessions, feedback, stars and confirmations persist; invented IDs no longer return successful mock results. The request/response schemas are unchanged. Apply the new migration before running this revision.

Mapping choices in this reader:

- An absent purchase unit means not buyable, as Role 2's catalogue specifies.
  This excludes water and cooked rice from purchases; it does not make cooked
  rice automatically available at home.
- The reader uses stored staple flags and keeps all ingredient lines, including
  optional ingredients, for dietary checks. It uses current ingredient allergen
  and diet metadata, not potentially stale recipe aggregates.
- Countability does not imply a grams-to-pieces conversion. Stored pack measures
  pass through unchanged; incompatible requirements retain the engine's check
  flow. No new pack sizes, shelf lives or ingredient IDs are invented.
- Shelf life is the estimate for the ingredient's default storage. Perishable
  categories come from Role 2's freshness module. Inventory dates/statuses are
  passed through from `get_inventory_snapshot`; this reader does not recompute
  freshness. Kitchen's three-day badge and the engine's urgency score remain
  separate existing behaviors.
- Stars use the latest `starred`/`unstarred` feedback event for the household;
  other signals do not affect stars. Equal timestamps use UUID order only as a
  stable fallback, not proof of event chronology. The implemented star writer serializes household updates and gives each changed star a timestamp strictly later than the previous star event. Repeating the current star value writes nothing.
- Recipe ingredient display order is stable UUID order: the current relation
  has no source-position field. Instructions retain their stored order.
- `active_minutes` must be present because the public Recipe schema requires it.
  All 48 delivered recipes supply it. A future incomplete recipe fails loading
  with its ID rather than getting a fabricated time. Missing or invalid safety
  and purchase metadata also fails validation.

## Storage additions prepared for Role 2 review

The **new migration** leaves the merged initial migration unchanged. These
fields correspond directly to the existing internal records in
[`recommendation_repository.py`](../backend/app/services/recommendation_repository.py).
Keep existing relational columns as the searchable identity/status fields.

| Table | Proposed addition | Why |
|---|---|---|
| `sessions` | `recommendation_state JSONB NULL` | Versioned Cook/Shop state; saved suggestion history; selected-record/current-basket link. Existing `constraints` and `shown_recipe_ids` alone cannot reproduce Previous or all accumulated engine state. |
| `cook_records` | `selection_snapshot JSONB NULL` | Immutable Candidate and proposed consumption with original batch IDs, revisions, units and quantities; includes the selected public CookRecord response. |
| `cook_records` | `confirmation_snapshot JSONB NULL` | Successful confirmed CookRecord view, kept separately from the immutable selection. Later ratings update the projected response, not the original selection. |
| `baskets` | `planning_snapshot JSONB NULL` | Original Basket response and ingredient/purchase metadata for its saved item IDs. Later catalogue edits must not alter a purchase conversion the user already saw. Actual purchases continue in `basket_items`. |
| new `recommendation_learning` | `household_id UUID PRIMARY KEY REFERENCES households`, `state JSONB NOT NULL`, `updated_by UUID REFERENCES users NOT NULL`, `updated_at TIMESTAMPTZ NOT NULL` | One ordered evidence collection per household: one entry per confirmed cook record with recipe ID, frozen features and current rating. Keep first-confirmation order across changed ratings. The clipped `preferences.taste_weights` map cannot reconstruct this. |
| new `recommendation_confirmations` | `(household_id UUID, idempotency_key UUID)` composite primary key; `operation TEXT NOT NULL`; `target_id UUID NOT NULL`; `request_json TEXT NOT NULL`; `response_snapshot JSONB NOT NULL`; `stock_event_id UUID REFERENCES stock_events NOT NULL`; `created_at TIMESTAMPTZ NOT NULL` | Replay the exact successful response and compare the normalized request, not just the stock event's target IDs. Constrain operation to `cook` / `shop`; reference the household. |

All JSON snapshots should carry `schema_version: 1`; Role 5 will encode/decode
UUIDs, enums and timestamps explicitly, validate required fields and reject
unknown versions. `recommendation_state` stores the complete CookSession or
ShopSession state, plus the history/current links in the corresponding port
record. Normal `sessions.position`, status, people and expiry remain consistent
with that state. Store the expiry in `sessions.expires_at`, not a second mutable
source of truth in each snapshot.

The learning state is `{"schema_version": 1, "meals": [...]}`, preserving the
MealEvidence array order and the learning configuration used to derive weights.
Each entry contains `record_id`, `recipe_id`, `features` and `rating`. Keep
feedback audit entries in `recipe_feedback`; do not treat retries or rating
edits as additional meals. Save evidence, audit actor and derived weights in
one transaction. A future larger-scale schema can normalize these entries;
the project catalogue/workload does not yet require that complexity.

Nullable snapshots allow existing rows through migration without inventing
history. Legacy sessions/records/baskets missing required snapshots must be
rejected by the new adapter, with a clear restart-session response; do not
retroactively reconstruct them from today's inventory or recipe. Existing
nonempty taste weights without evidence need an explicit migration/reset
decision before learning writes are enabled; never silently erase them.

## Implemented transaction and lock rules

1. Use the caller's transaction for all repository methods and
   `apply_stock_event`. Commit the event, target status, learning and replay
   response together, or roll them all back.
2. The implementation serializes Role 5 mutations with a `FOR NO KEY UPDATE` lock on the household row **before** session/record/basket/learning locks. This allows the foreign-key `KEY SHARE` locks needed by concurrent manual stock-event inserts, avoiding a deadlock during a shared-key race. This gives a lock even
   before a learning or replay row exists, and a consistent order for feedback,
   selection, adjustment and confirmation. Different households remain parallel.
3. The replay table is not a separate key namespace. Before confirmation,
   compare any existing stock event and saved confirmation. Manual edits do not
   take Role 5's household lock, so after `apply_stock_event` returns, require
   a matching operation/target and reject a stock event not owned by this
   confirmation. Role 2's unique `(household_id, idempotency_key)` still arbitrates
   races with manual writes. Never accept a replay for a different request body.
4. Different keys must not confirm the same target twice. A confirmed status
   under lock rejects another key. Expired sessions cannot confirm for the first
   time; a previously successful matching replay remains available after expiry.
5. Do not prune replay/evidence/snapshot rows during the project's evaluation.
   A retention policy and any future cleanup need a separate agreement.

Role 2 already supports empty stock-event line lists, revision checks and
conflicting operation keys in the merged write path; no signature change is
requested. Role 5 will update only its `last_*` fields and learned weights,
preserving user preferences. Selection and confirmation must re-read inventory;
the input reader alone is not a concurrency guarantee.

## Verification and next steps

Implemented: SQL repository, versioned snapshot codecs, endpoint wiring, recipe detail/star queries and real use-first reads. Role 2 should review the schema and migration in the draft before merge. Deployment and the remaining held-out evaluation are still separate tasks.

PostgreSQL CI passed at implementation commit `73e4186`. Tests exercise concurrent
same/different-key confirmation, stock-event key races with manual writes, stale
inventory revisions, selection retries, simultaneous rating replacement,
cross-household access, snapshot stability after recipe/pack edits and rollback
after an injected post-stock-event failure. The migrated schema matches the
models. Pure learning tests cover replacement after weight clipping; codec tests
preserve evidence order and configuration across JSON storage.

The remaining 30 held-out scenarios, deployed Cook/Shop checks, cloud cost and
elasticity measurements remain separate evaluation work. Local database tests
need PostgreSQL; CI requires it rather than allowing skips.
