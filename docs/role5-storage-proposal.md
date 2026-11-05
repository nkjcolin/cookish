# Role 5 database integration: next migration proposal

Originally prepared 5 November 2026 against `main` at `a360567`; status notes
updated after PR #21 merged at `a6d06a5`. **Proposed for Role 2 to
review and implement; no migration or shared API change is included.** Role 2
owns the database models and migrations. Role 5 owns the recommendation queries,
serialization and endpoint wiring.

## Available now

`SqlRecommendationInputs` in
[`recommendation_inputs.py`](../backend/app/services/recommendation_inputs.py)
loads reviewed recipes, ingredient metadata, purchase definitions and household
stars from the existing tables. It delegates preferences and inventory reads to
Role 2, using the caller's SQLAlchemy transaction. It is a component of the future
repository, not a complete implementation of `RecommendationRepository`.

The 42 ingredient rows and 48 approved recipes can now feed the pure engines.
Cook/Shop session endpoints still use mocks until the remaining repository is
implemented and tested. Recipe detail/star and use-first endpoints already use
the existing database services; they do not require the proposed storage below.

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
  stable fallback, not proof of event chronology. The implemented star writer in
  `services/recipe_details.py` serializes household updates and advances each
  changed star event's timestamp beyond the prior event. Repeating the current
  state creates no additional event.
- Recipe ingredient display order is stable UUID order: the current relation
  has no source-position field. Instructions retain their stored order.
- `active_minutes` must be present because the public Recipe schema requires it.
  All 48 delivered recipes supply it. A future incomplete recipe fails loading
  with its ID rather than getting a fabricated time. Missing or invalid safety
  and purchase metadata also fails validation.

## Storage additions requested from Role 2

Use a **new migration**, leaving the merged initial migration unchanged. These
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

## Transaction and lock rules to confirm

1. Use the caller's transaction for all repository methods and
   `apply_stock_event`. Commit the event, target status, learning and replay
   response together, or roll them all back.
2. For the first implementation, serialize Role 5 mutations on the household
   row **before** session/record/basket/learning locks. This gives a lock even
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

## Next implementation and verification

After agreement and migration: complete the SQL repository, implement versioned
snapshot codecs, then install `RecommendationWorkflow` behind the existing
Cook/Shop functions. Recipe detail/star queries are already implemented against
the existing tables in `services/recipe_details.py`; preserve their household
locking and timestamp/ID ordering when integrating the full repository.

Database tests must cover concurrent same/different-key confirmation, stock-event
key races with manual writes, stale inventory revisions, selection retries,
rating replacement after weight clipping, cross-household access, historical
snapshot stability after recipe/pack edits and rollback after an injected
post-stock-event failure. These are additional to the current input-reader
tests, recipe/star/use-first database tests and pure workflow tests. The held-out
runner is prepared, but the final freeze, 30 independent unseen scenarios and
deployed Cook/Shop checks stay separate final evaluation work.
