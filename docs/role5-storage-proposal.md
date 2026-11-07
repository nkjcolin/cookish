# Role 5 database integration: storage implementation

Originally proposed on 5 November 2026 against `main` at `a360567`. On 7 November,
Wenlong authorized the necessary storage changes alongside the Role 5 integration.
The additions below are now implemented in the shared models and new migration
[`6f2c8d471a90`](../backend/migrations/versions/6f2c8d471a90_recommendation_storage.py),
following initial revision `d0ae2870ce7e`. The initial migration is unchanged.
This is no longer a request waiting for Role 2 implementation. Role 2 remains
the normal owner of database models/migrations; Role 5 owns recommendation
queries, serialization and service wiring. Public API schemas are unchanged.

**Apply the migration before deploying the new backend.** PostgreSQL CI at
`f313566` passed all 549 backend tests, including migration preservation and the
20 new workflow tests. AWS deployment checks remain pending. These results cover
the merged integration, before the later protein/history additions.

## Available now

`SqlRecommendationInputs` in
[`recommendation_inputs.py`](../backend/app/services/recommendation_inputs.py)
loads reviewed recipes, ingredient metadata, purchase definitions and household
stars from the existing tables. It delegates preferences and inventory reads to
Role 2, using the caller's SQLAlchemy transaction. It is now used by
[`SqlRecommendationRepository`](../backend/app/services/recommendation_sql.py),
the complete persistence adapter for `RecommendationRepository`.

The 42 ingredient rows and 48 approved recipes feed the pure engines. Public
Cook/Shop session, selection, confirmation and rating functions now call the SQL
workflow rather than mocks. Recipe detail/star and use-first retain their
existing database services and public signatures.

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

## Implemented storage additions

The **new migration** adds fields corresponding to the internal records in
[`recommendation_repository.py`](../backend/app/services/recommendation_repository.py).
Existing relational columns remain the searchable identity/status fields.

| Table | Addition | Why |
|---|---|---|
| `sessions` | `recommendation_state JSONB NULL` | Versioned Cook/Shop state; saved suggestion history; selected-record/current-basket link. Existing `constraints` and `shown_recipe_ids` alone cannot reproduce Previous or all accumulated engine state. |
| `cook_records` | `selection_snapshot JSONB NULL` | Immutable Candidate and proposed consumption with original batch IDs, revisions, units and quantities; includes the selected public CookRecord response. |
| `cook_records` | `confirmation_snapshot JSONB NULL` | Successful confirmed CookRecord view, kept separately from the immutable selection. Later ratings update the projected response, not the original selection. |
| `baskets` | `planning_snapshot JSONB NULL` | Original Basket response and ingredient/purchase metadata for its saved item IDs. Later catalogue edits must not alter a purchase conversion the user already saw. Actual purchases continue in `basket_items`. |
| new `recommendation_learning` | `household_id UUID PRIMARY KEY REFERENCES households`, `state JSONB NOT NULL`, `updated_by UUID REFERENCES users NOT NULL`, `updated_at TIMESTAMPTZ NOT NULL` | One ordered evidence collection per household: one entry per confirmed cook record with recipe ID, frozen features and current rating. Keep first-confirmation order across changed ratings. The clipped `preferences.taste_weights` map cannot reconstruct this. |
| new `recommendation_confirmations` | `(household_id UUID, idempotency_key UUID)` composite primary key; `operation TEXT NOT NULL`; `target_id UUID NOT NULL`; `request_json TEXT NOT NULL`; `response_snapshot JSONB NOT NULL`; `stock_event_id UUID REFERENCES stock_events NOT NULL`; `created_at TIMESTAMPTZ NOT NULL` | Replay the exact successful response and compare the normalized request, not just the stock event's target IDs. Constrain operation to `cook` / `shop`; reference the household. |

[`recommendation_snapshots.py`](../backend/app/services/recommendation_snapshots.py)
uses the envelope `{"schema_version": 1, "kind": "...", "payload": {...}}`.
The payload is the complete typed port record, with UUIDs, enums and timestamps
encoded as JSON values. The codec rejects missing or unexpected fields,
unsupported versions, invalid types and inconsistent identities. Sets use
stable ordering; history and meal-evidence order are preserved.

`recommendation_state` contains the complete CookSessionRow or ShopSessionRow,
including engine state, history and current links. The payload includes its
recorded expiry, but repository reads override that value with the owning
`sessions.expires_at`; the relational column remains authoritative. The adapter
also checks snapshot identities and relevant relational fields before use.

The learning envelope has `kind: "learning"`; its payload contains
`household_id`, `meals` and `config`. Each meal contains `record_id`, `recipe_id`,
frozen `features` and current `rating`. The adapter saves evidence, acting user,
audit entries in `recipe_feedback` and derived `preferences.taste_weights` in
one transaction. Retries and rating edits do not create additional meal evidence.

New confirmations now include protein features derived from the explicit catalogue
mapping. Existing cuisine/tag-only evidence remains frozen when ratings change;
no protein weights are backfilled. The snapshot version and fields are unchanged.

Recent-cooked history needs no additional storage. The repository joins confirmed
`cook_records` to matching, same-household consumption events and uses their
`created_at` within the last seven elapsed days, inclusive. It excludes undone and
future events and refreshes the result before every Cook ranking. Each recipe
gets one repetition penalty, regardless of the number of meals in the window;
selection and feedback dates do not extend it.

Nullable snapshots allow existing rows through migration without inventing
history. The adapter rejects legacy sessions/records/baskets missing required
snapshots with `CONFLICT` and a restart-session message. It does not reconstruct
old responses from today's inventory or recipe. Existing nonempty taste weights
without evidence block workflow learning loads, including new recommendations,
until an explicit migration decision is made. The migration does not reset them.

## Implemented transaction and lock rules

1. Use the caller's transaction for all repository methods and
   `apply_stock_event`. Commit the event, target status, learning and replay
   response together, or roll them all back.
2. Serialize Role 5 mutations with `FOR NO KEY UPDATE` on the authenticated
   household row **before** session/record/basket/learning locks. Check household
   membership when constructing the repository. This gives a lock even
   before a learning or replay row exists, and a consistent order for feedback,
   selection, adjustment and confirmation. Different households remain parallel.
3. The replay table is not a separate key namespace. Before confirmation,
   compare any existing stock event and saved confirmation. Manual edits do not
   take Role 5's household lock, so after `apply_stock_event` returns, require
   a matching operation/target and reject a stock event not owned by this
   confirmation. Role 2's unique `(household_id, idempotency_key)` still arbitrates
   races with manual writes. The adapter tracks the newly inserted stock event
   and rejects a competing operation's replay. Never accept a saved confirmation
   for a different validated request body.
4. Different keys must not confirm the same target twice. A confirmed status
   under lock rejects another key. Expired sessions cannot confirm for the first
   time; a previously successful matching replay remains available after expiry.
5. Do not prune replay/evidence/snapshot rows during the project's evaluation.
   A retention policy and any future cleanup need a separate agreement.

Role 2 already supports empty stock-event line lists, revision checks and
conflicting operation keys in the merged write path; no signature change is
requested. Role 5 updates only its `last_*` fields and learned weights,
preserving user preferences. Selection and confirmation must re-read inventory;
the input reader alone is not a concurrency guarantee.

## Migration, verification and remaining work

The SQL repository, snapshot codecs and public endpoint wiring are implemented.
Before releasing the backend, deploy the updated migration Lambda and invoke
the existing `app.migrate.handler`, which applies Alembic revisions and seeds
the production ingredient/recipe catalogue. Verify revision `6f2c8d471a90` and
seed success first. Users must restart old sessions. Recipe detail/star queries
retain their existing household locking and timestamp/ID ordering.

The local non-database suite passed 391 tests. Offline migration upgrade and
downgrade SQL render successfully. The new migration preservation test exercises
legacy rows and weights in a disposable PostgreSQL database. It was skipped
locally because PostgreSQL is unavailable, then ran successfully in
[CI at `f313566`](https://github.com/nkjcolin/cookish/actions/runs/42342203535),
alongside all 20 new SQL workflow tests (549 backend tests total). The subsequent
protein/history changes require a separate CI run.

Database verification must cover concurrent same/different-key confirmation, stock-event
key races with manual writes, stale inventory revisions, selection retries,
rating replacement after weight clipping, cross-household access, historical
snapshot stability after recipe/pack edits and rollback after an injected
post-stock-event failure. These checks complement the input-reader,
recipe/star/use-first and pure workflow tests. No AWS migration or deployment
has been performed by this implementation task.

The remaining product dependencies are ingredient-ID matching for AI imports,
compatible inventory/recipe units, and the frontend's route from an empty-stock
suggestion to adding ingredients or shopping. The held-out runner is prepared,
but the final freeze, 30 independent unseen scenarios and deployed Cook/Shop
checks remain separate evaluation work.
