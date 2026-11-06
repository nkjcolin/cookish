# Role 2: decisions about the database, catalogue and inventory

Updated 4 November 2026. Read this if you call Role 2's functions, edit anything in
`backend/seed/`, or write about the database in the report. Anything below marked
**needs agreement** is a proposal, not a decision: reply in the pull request or the group chat.
Agreed signatures and file formats change only by agreement (`docs/init.md`).

## Status

Update the last column as pull requests merge.

| Piece | Where | State |
|---|---|---|
| Tables and migrations (16 tables) | `backend/app/db/models.py`, `backend/migrations/` | merged |
| Migrate and seed on container start | `backend/Dockerfile` | merged |
| Ingredient catalogue and seed loader | `backend/seed/ingredients.csv`, `seed.py` | merged |
| Demo household (local only) | `backend/seed/demo.py` | merged |
| Identity service | `backend/app/services/identity.py` | pull request |
| Tests on a throwaway database, Postgres in CI | `backend/tests/conftest.py`, `tests/db/`, `.github/workflows/ci.yml` | pull request |
| Inventory reads and freshness | `services/inventory.py`, `stock_events.py`, `freshness.py` | pull request |
| Write path: add, edit, remove, undo, activity list, `apply_stock_event` | `services/stock_events.py`, `inventory.py`, `tests/db/test_stock_events_db.py` | pull request |
| Ingredient search | `services/catalogue.py`, `tests/db/test_catalogue_db.py` | pull request |
| AWS: migrate Lambda, database secret | `app/migrate.py`, `app/db/session.py`, `tests/db/test_migrate_db.py`, `tests/test_session_url.py` | merged; matches Role 3's template; **not yet run on AWS** |
| Reliability and tenancy tests (SPEC A10, A6) | `tests/db/test_reliability_db.py`, `tests/db/test_tenancy_api_db.py` | pull request |

## How freshness works

Cookish does **not** work out an expiry date. It works out a **use-first date**, which is our
estimate of when to use a batch by, and it never says an estimate means food is unsafe.
Only a date printed on the package can make a batch "expired".

**Where the use-first date comes from** (`app/services/freshness.py`):

1. If the user entered the printed date (`label_date`, with `label_date_kind` = `use_by` or
   `best_before`), that is the use-first date.
2. Otherwise it is the purchase date (`acquired_at`) plus the ingredient's shelf life for where
   the batch is stored. The shelf life is the `shelf_life_days_pantry`, `_fridge` or `_freezer`
   column of `ingredients.csv`.
3. If there is neither, the batch has no use-first date.

Example: tomatoes bought on 1 Nov and kept in the fridge (7 days) get 8 Nov. They show
"use soon" from 5 Nov and "check" from 9 Nov.

**The status of a batch** (`freshness_status`), checked in this order:

| Status | When | What Cook and Shop do |
|---|---|---|
| `ok` | The batch is out of stock, or its date is more than 3 days away, or it has no date and is not a perishable | Counted as stock |
| `use_soon` | The date is today or within 3 days | Counted; Role 5 turns the date into urgency |
| `check` | Past a best-before date or past our estimate; or a perishable with no date at all; and not confirmed in the last 24 hours | Not counted until the user answers "It's fine" or throws it away |
| `expired` | Past a **use-by** label date. "It's fine" does not rescue it | Not stock |

- **Perishable** means the ingredient's category is produce, meat, seafood, dairy or egg. A
  free-text item has no category, so it is never flagged just for lacking a date.
- **"It's fine"** sets `freshness_confirmed_at`, which makes a past-date batch usable for 24 hours.
- An estimate only ever leads to a question (`check`). It never discards food by itself.
- Role 5 reads `est_use_first_date` and `freshness_status` as given and does not recompute them.

**Limits to be honest about in the report**

- Shelf-life numbers in `ingredients.csv` were checked against the USDA FoodKeeper data (version
  in the file `FoodKeeper-Data_1.xls`, Product sheet, "date of purchase" columns). Where
  FoodKeeper gives a range we use the **low end** (weeks = 7 days, months = 30, years = 365), so
  the app errs on the side of "use it soon". Most ingredients matched a FoodKeeper product directly, and
  about half of them changed (mostly shorter fridge times, e.g. egg 28 to 21 days, chicken 2 to 1
  day). FoodKeeper has no entry for chilli paste, water spinach or water (kept at the earlier
  estimate). Soba, turmeric and chye sim use the nearest product (dry pasta, ground spices,
  greens). Some numbers are still our own: pack sizes, cut pumpkin (5 days)
  and the pantry value for tomato. They are estimates, not food-safety advice.
- One shelf life per ingredient and storage place. It does not know whether a package was
  opened, bought frozen or cooked, or how fresh it was in the shop.
- The estimate counts from the day the batch was bought or added. Adding items late makes it
  optimistic.
- Photos cannot certify freshness, so nothing is inferred from images. At the moment the printed
  date can only be typed in (the API accepts it when adding or editing an item).
  Reading it from a package photo is not built.

## Stock events (the write path)

Every inventory change, from the Kitchen screen or from Cook and Shop, goes through
`apply_stock_event`. It runs in the caller's transaction, so a failure anywhere rolls the whole
change back.

- **One event, one set of lines.** The event records who, when and why (`ref_type`, `ref_id`).
  Each line holds a `before` and `after` snapshot of every changeable field, so undo can restore
  all of them. A snapshot also stores the revision the item had afterwards.
- **Retries are safe.** A repeated `Idempotency-Key` returns the original change and writes
  nothing. The database's unique constraint on (household, key) settles two requests arriving at
  once, not a look-up first. A retry returns the items as they are **now**, not as they were then.
- **Reusing a key for a different operation is a `CONFLICT`.** It is compared on event type,
  `ref_type`, `ref_id` and which items the lines touch.
- **Edits cannot overwrite each other.** The items are locked (`SELECT ... FOR UPDATE`) and each
  line's `revision` is compared inside the lock. A mismatch raises `STALE_REVISION` before
  anything is written. A system change may pass `revision=None` to skip the check.
- **Another household's item is `NOT_FOUND`**, the same as one that does not exist.
- **An empty list of lines is allowed.** It records an event that changed nothing, so a retry of
  "cooked, nothing used" is still protected by its key.
- **Undo** restores each line's `before` snapshot (a removal is brought back, an add is removed).
  A line whose item has been changed since is reported as a conflict and left alone, and the
  other lines are still undone. An undo cannot be undone, and an event is undone once. An undo
  is itself a change, so the item's revision goes up.
- **Removing an item is a soft delete** (`deleted_at`), which is what makes undo possible.

Small decisions made while building it (tell me if the team disagrees):

- For a countable ingredient, setting the count to 0 sets the state to `out`, and a positive count
  on an `out` item sets it back to `enough`, unless the edit sets the state itself. Otherwise an
  item with 0 left would still count as stock.
- A new item takes its name from the catalogue with a capital letter ("Egg"), its unit from the
  ingredient when a count is given, and its storage from the ingredient (a free-text item
  defaults to pantry).
- An edit sent as `null` clears the field to unknown. For `remaining_state`, null means `unknown`.
  `storage` and `display_name` cannot be null.
- If an undo restores only some lines, the original event is marked as undone and cannot be
  undone again, so the lines left in conflict stay as they are.

## AWS: reaching the database

Two small pieces, both tested against a real Postgres but **not yet run on AWS**.

**The database login (`app/db/session.py`).** The app looks for the database in this order:
`DATABASE_URL` (docker-compose and the tests), then `DB_SECRET_ARN`, then the local database. With
`DB_SECRET_ARN` it reads that Secrets Manager secret once per Lambda instance and builds the URL.
The secret must be JSON with `username`, `password` and `host`. `port` (default 5432) and `dbname`
(default `DB_NAME`, else `cookish`) are optional, and these are the field names RDS uses in the
secrets it creates itself. Connections use `sslmode=require` (RDS for PostgreSQL 15 and later
refuses unencrypted ones); `DB_SSLMODE` overrides it. `boto3` comes with the Lambda Python runtime,
so it is not a project dependency and is imported only when the secret is read.

**The migration step (`app/migrate.py`).** `app.migrate.handler` runs `alembic upgrade head` and
then `seed.seed` (ingredients and recipes), and returns the revision and the seed counts. It never
seeds the demo household. It is safe to run again, and a database lock makes two runs at the same
moment take turns. It needs to run inside the same network as the database, once per deploy, and
its package must contain the `migrations/` and `seed/` folders at the top, next to `app/`.

**Role 3's template (`infra/template.yaml`), read against this code.** Role 3 creates the database
and the secret, and the template matches what the code expects, so no code change was needed:

- The secret is generated in the template (`username`, `password`), and a
  `SecretTargetAttachment` adds `host`, `port` and `dbname` once the database exists. These are the
  field names the code reads.
- The password route is a Secrets Manager interface VPC endpoint in both private subnets, with no
  NAT gateway. This resolves the conflict with SPEC A3's "no VPC endpoint"; Role 3's README says to
  include its fixed cost in the cost model (SPEC A12 deviation).
- The migrate Lambda uses `app.migrate.handler` from the backend code, in the VPC, with 512 MB and
  a 120-second timeout, and the same security group as the `api` Lambda.
- The database is PostgreSQL 16 named `cookish`; the master user can create `pg_trgm`.

**Still open with Role 3.** None of this has run on AWS yet; the first deploy is the first real test.

1. The template sets `BackupRetentionPeriod: 0`, so there are no automatic backups. A deleted stack
   or a database fault would lose all data. A small retention period costs nothing at this size.
2. `sam build` reads `requirements.txt` but the backend uses uv, and the package must keep
   `migrations/` and `seed/` at the top next to `app/`. Check the built package contains them.
3. `aws lambda invoke` succeeds even when the function fails. The deploy job must check for
   `FunctionError` in the response, or a failed migration looks like a good deploy.

## Ingredient search

`GET /api/ingredients?q=` searches the canonical name and every alias, using `pg_trgm`. Results are
ranked: what was typed is the whole name or alias, then a name or alias that starts with it, then
one that contains it, then one that is close to it (a typo). At the same level a match on the real
name beats a match on an alias, and a shorter name beats a longer one. Each ingredient appears
once. Typing nothing lists the catalogue alphabetically. The `%` and `_` characters mean
themselves. Aliases are the only way the search knows local names ("kangkong", "tau kwa"), so a
miss found by Role 4's receipts is fixed by adding an alias to `ingredients.csv`.

## Ingredient catalogue (`backend/seed/ingredients.csv`)

42 ingredients from Role 5's request list, each with a fixed UUID. Never change a UUID: stock,
ratings and Role 4's matching point at it.

| Topic | Decision | Needs agreement |
|---|---|---|
| Halal | Chicken thigh has no `halal` flag, because it depends on how the product was slaughtered. Halal users see no chicken recipes. Egg and seafood are flagged halal | team |
| Coconut milk | Not tagged `tree_nut` | team |
| Soba | Tagged `gluten` (most soba contains wheat) | team |
| Diet flags and allergens | A recipe is suitable for a diet only if **every** ingredient is, optional ones included. A recipe has an allergen if **any** ingredient does. Recipe files do not contain them; the loader works them out | no |
| Staples | Salt, black pepper, canola oil, sesame oil, soy sauce, water. They never block a recipe or appear on a shopping list. Cumin, turmeric and chilli paste are not staples | Role 5 |
| Water | A staple with no purchase unit and no shelf life | Role 5 (their proposal) |
| Tracked by count | Egg, tomato, carrot, cucumber, lemon, onion, potato, firm tofu (as packs). Everything else is tracked by state | team |
| Buyable | An empty `purchase_unit` means "not bought" (water, cooked rice). There is no separate flag, although Role 5's Shop code expects one | **Role 5** |
| Grams versus counts | Unchanged from Role 5's handoff: 300 g of tomato cannot be compared with a count of tomatoes. Until a conversion is agreed, such cases use the "check at home" flow | Role 5 |
| Pack sizes | Provisional. The canned chickpea size (240 g) is the drained weight. Water spinach is a 300 g bunch (the README example said 1 pcs) so recipe grams can convert | Role 5 |

## Data model

- **One inventory row is one batch.** Buying eggs twice makes two rows; they are never merged.
- Closed lists (states, sources, storage, ...) are text columns with a CHECK, built from
  `app/schemas/common.py`, so the API and the database cannot disagree.
- `recipes.allergens` exists although SPEC A6 does not list it, because the loader fills it.
- `stock_events.idempotency_key` is a UUID (SPEC A6 said text). It is unique per household and
  **shared** by manual edits and by Cook and Shop confirmations.
- The sessions table is the model `PlanSession` (to avoid a clash with SQLAlchemy's `Session`).
- `stock_event_lines.before` and `after` hold every changeable field, not only the three the API
  shows, because undo has to restore all of them.
- `inventory_items.est_use_first_date` is not used. The date is computed when items are read.
- Removing an item sets `deleted_at` (a soft delete), so undo can bring it back.
- A free-text item (no ingredient) is reported as category `other`, tracked by state.
  **Needs agreement with Role 1.**
- `taste_weights` is stored on `preferences` but is not in the public API.
  **Needs agreement with Role 5** on internal read and write access.

## Identity and preferences

- A user's first request creates the user and a household of one. The household is named after
  the email (`dev@cookish.test` gives "Dev's kitchen"). A per-user lock stops simultaneous first
  requests from creating several households.
- A user with several households gets the one they own first.
- No preferences row means "not onboarded": `GET /api/me` returns `preferences: null` and the
  frontend shows onboarding. `get_preferences` raises `NOT_FOUND` in that case.
- Saving preferences replaces the household's choices. The **first** save sets the remembered Cook
  and Shop people counts to `household_size`. **Later saves never touch** those counts or
  `taste_weights`: Cook and Shop own them.
- An unknown disliked-ingredient ID is rejected as `VALIDATION`.

## Local development and tests

- When the backend container starts it runs the migration, then `seed.seed` (catalogue and
  recipes), then `seed.demo`, then the server. If a step fails, the server does not start.
- `seed.seed` checks every file first and reports all problems together. If there is any problem,
  nothing is written. It is safe to run again and never deletes.
- The demo household exists in the development container only. It is created once and never
  overwritten, so your edits survive a restart. `docker compose down -v` gives a fresh one.
  On AWS nobody signs in as the demo user, so the migrate Lambda must run `seed.seed` and **not**
  `seed.demo`.
- Tests never touch the development database. Each run builds a throwaway database with the real
  migrations and drops it afterwards. (A contract test saves preferences, which once overwrote the
  demo household.)
- Tests in `backend/tests/db/` need Postgres (`docker compose up -d db`). Without it they are
  skipped. CI has a Postgres service and sets `REQUIRE_DB=1`, so there they must run.
- **Never edit a merged migration.** Change the tables with a new migration.

## Open questions

| Who | Question |
|---|---|
| Role 1 | Free-text items as category `other`, state-tracked. Kitchen groups are alphabetical by name: should "use first" groups come first? Is there a field for the printed date when adding or editing an item? Batches are grouped under one row (SPEC B1 says the row expands). The collapsed row can mislead: "Egg, 8 pcs, ~2 days" reads as if all 8 eggs are about to go off, when only an older batch may be. Can the collapsed row say how many are old ("2 expire in ~2 days")? The batches are already in the API response, so this is a screen change, unless the schema needs a field. |
| Role 3 | `ci.yml` now has a Postgres service for the backend job. The AWS migration step and secret handling match your template (see "AWS: reaching the database"); three points are still open there: backups, packaging and checking the migrate result. |
| Role 4 | The draft item from `/ai/parse-image` has no date field, so a printed date cannot be read from a package photo. Do we want that? The report says photos cannot certify freshness; reading a printed date is a different thing and the wording should say so |
| Role 5 | The explicit "buyable" flag (above). The 3-day "use soon" window versus your urgency window. Internal access to `taste_weights` and to update only the `last_*` fields. Where to store your snapshots, evidence and confirmation keys (this needs a new migration, which Role 2 writes). Empty line lists in `apply_stock_event`. Reusing a key for a different operation raising `CONFLICT` |

## For the final report (SPEC A12, deviations from the preliminary report)

- Stock is tracked as counts for countable ingredients and four states otherwise
  (`enough`, `low`, `out`, `unknown`), not as approximate amounts.
- There are no prices and no budget.
- Freshness is an estimated use-first date from the purchase date and typical shelf life, or the
  printed date when entered. Estimates lead to a check and never declare food unsafe.
- The API runs on Lambda, not Fargate, and the Dockerfile is for local development only.
