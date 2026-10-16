# Role 2 — Database and inventory

You own the database and everything that changes the kitchen: the tables, the seed data, the inventory and stock-event services, and the internal functions Role 5 calls to read and change stock. Read [docs/init.md](../../../docs/init.md) first for the conventions everyone follows.

The design is in [SPEC.md](../../../docs/SPEC.md): **A6** for every table and the inventory rules, **B2** for your brief.

## What you own

| Path | Contents |
|---|---|
| `backend/app/db/` | `session.py` (exists), your models and queries |
| `backend/migrations/` | Alembic migrations for every table |
| `backend/seed/ingredients.csv`, `backend/seed/seed.py` | The ingredient catalogue and the loader for it and the recipes |
| `backend/app/migrate.py` | Entry point of the `migrate` Lambda (to write) |
| `backend/app/services/identity.py` | `get_me`, `save_preferences`, `get_or_create_user`, `get_preferences` |
| `backend/app/services/catalogue.py` | `search_ingredients` |
| `backend/app/services/inventory.py` | `list_inventory`, `add_items`, `update_item`, `delete_item` |
| `backend/app/services/stock_events.py` | `list_events`, `undo_event`, `apply_stock_event`, `get_inventory_snapshot` |
| `backend/tests/` | Your tests, including the reliability tests in SPEC A10 |

You are also the editor of the final report and slides.

## What already exists

- **Every function above, as a stub** marked `STUB`, returning sample data from `app/mock.py`. The endpoints, the frontend and Role 5's code already call them.
- **`session.py`**: `engine()` reads `DATABASE_URL` and is created once per process; `transaction()` is the context manager every service uses. SQLAlchemy 2 and the `psycopg` driver are installed. Alembic is not yet.
- **`app/auth.py`** calls your `get_or_create_user` on every request, with the Cognito `sub` on AWS or a fixed development user locally.
- **`app/clock.py`** for today's date in Singapore.
- **Postgres 16** in `docker compose up`, empty, with `DATABASE_URL` set for the backend container.
- **The file formats** for `ingredients.csv` and the recipe files, agreed with Roles 4 and 5, in [seed/README.md](../../seed/README.md).

## What you may change, and what you must keep

**Yours to decide:** everything inside the function bodies; models, queries and repositories; the internals of `session.py` (pool settings, reading `DB_SECRET_ARN`); migrations; how `seed.py` works; indexes.

**Keep, because others depend on them:**

- The name, parameters and return type of every service function. Routers (Role 1) call the public ones; Role 5 calls `apply_stock_event`, `get_inventory_snapshot` and `get_preferences`.
- The format of `ingredients.csv`. Role 4's `ai` Lambda reads it, and Role 5's recipes refer to it.
- The `InventoryItem` shape: it comes from the API contract (`app/schemas/inventory.py`), owned by Role 1.

Changing any of these is fine by agreement; see "Changing an agreement" in `docs/init.md`.

## What other roles expect from you

### Role 5: changing stock

`apply_stock_event` in `services/stock_events.py` is the only way inventory changes, for you and for Role 5:

```python
@dataclass(frozen=True)
class NewBatch:                 # a purchase, or an item added by hand
    item: InventoryItemCreate
    source: ItemSource

@dataclass(frozen=True)
class ChangeBatch:              # change or remove an existing batch
    item_id: UUID
    revision: int | None        # the revision the user saw; None for system changes
    changes: dict[str, Any]     # keys from CHANGEABLE_FIELDS only
    remove: bool = False

def apply_stock_event(
    s: Session, user: CurrentUser, event_type: StockEventType,
    lines: list[NewBatch | ChangeBatch], idempotency_key: UUID,
    ref_type: StockRefType = StockRefType.MANUAL, ref_id: UUID | None = None,
) -> InventoryChange
```

It must, inside the caller's transaction `s`:

- Write one `stock_events` row and one `stock_event_lines` row per line, with `before` and `after` snapshots; update the items and bump their `revision`.
- Raise `STALE_REVISION` when a `ChangeBatch.revision` does not match. `None` skips the check.
- Return the original change, and change nothing, when `idempotency_key` has been used before by this household. Rely on the unique constraint, not a check-then-insert.
- Raise `NOT_FOUND` for an item outside `user.household_id`.
- Treat `None` in `changes` as "unknown", never as zero.

`CHANGEABLE_FIELDS` lists the keys `changes` may hold: `count`, `unit`, `remaining_state`, `storage`, `label_date`, `label_date_kind`, `display_name`, `freshness_confirmed_at`.

Your own endpoints use it too: `add_items` is a `purchase` of `NewBatch` lines, `update_item` an `adjust` with one `ChangeBatch`, `delete_item` an `adjust` with `remove=True`.

### Role 5: reading the kitchen

```python
# services/stock_events.py
def get_inventory_snapshot(s: Session, household_id: UUID) -> list[InventoryItem]

# services/identity.py
def get_preferences(s: Session, household_id: UUID) -> Preferences
```

The snapshot is every batch not removed, in the API's `InventoryItem` shape. `get_preferences` raises `NOT_FOUND` before onboarding is complete.

### Everyone: use-first dates and freshness

You compute `est_use_first_date` and `freshness_status` whenever items are read, using the "Use-first estimate" and "Freshness gate" rules in SPEC B5 and `clock.today()`:

- `est_use_first_date` is the label date if there is one, otherwise the purchase date plus the ingredient's shelf life for that storage.
- `freshness_status` is `ok`, `use_soon` (close to the date), `check` (past a best-before or estimated date, or a perishable with no date, and not confirmed within the last 24 hours) or `expired` (past a use-by date).

The frontend shows both as given, and Role 5 uses them without recomputing: an `expired` batch is not stock, a `check` batch is asked about, and the date becomes urgency in the score.

### Role 5: tables

You write the models and migrations for **every** table in SPEC A6, so that there is one migration history. Role 5 writes the queries on its own tables (`sessions`, `cook_records`, `recipe_feedback`, `baskets`, `basket_meals`, `basket_items`) and asks you for any change to them.

### Roles 4 and 5: the catalogue

`ingredients.csv` follows [seed/README.md](../../seed/README.md), with a fixed UUID written in each row. Take the ingredient list from Role 5's recipes. Role 4 bundles the same file into the `ai` Lambda and reads `id`, `canonical_name` and `aliases`.

Diets and allergens are set per ingredient. When `seed.py` loads a recipe, it computes the recipe's `diet_flags` as the intersection of its ingredients' flags and its allergens as their union; recipe files do not contain them. It stops with an error when a recipe names an ingredient that is not in the CSV.

### Role 3: running on AWS

- **Credentials.** On AWS the backend gets `DB_SECRET_ARN` instead of `DATABASE_URL`. Make `session.py` read the secret once per process and build the URL from it.
- **Migrations.** RDS is in private subnets, so neither CI nor a laptop can reach it. Write `app/migrate.py` with a `handler(event, context)` that runs the Alembic migrations and then `seed.py`. Role 3 deploys it as a third Lambda inside the VPC and invokes it after every deployment.

## Tasks, in order

1. Add Alembic. Write the models and the first migration for every table in SPEC A6, with the indexes in SPEC B2.
2. Make the backend container migrate and seed on start, so that `docker compose up` gives everyone the same data.
3. Write `ingredients.csv` from Role 5's recipes, and `seed.py`.
4. Seed a demo household matching the kitchen in `app/mock.py`, so that the frontend looks the same when a stub is replaced.
5. Replace the stubs. Start with `get_or_create_user`, `get_me` and `list_inventory`, then the write path through `apply_stock_event`: idempotency, revision check, snapshots, undo.
6. Compute `est_use_first_date` and `freshness_status` on read.
7. Write `app/migrate.py` and the `DB_SECRET_ARN` path in `session.py`, with Role 3.
8. Reliability tests from SPEC A10: repeated idempotency keys, two concurrent edits of one item, undo after a later edit, cross-household access on every route. CI needs a Postgres service for these; add it to `.github/workflows/ci.yml` with Role 3.

**Done when** the reliability tests pass in CI against a real Postgres, and the seeded database on the deployed stack is usable by everyone.

## Tips

- Concurrency: `SELECT … FOR UPDATE` on the affected items inside the event transaction, plus the `revision` check.
- Ingredient search: `pg_trgm` similarity over `canonical_name` and `aliases` is enough.
- Shelf-life days: the USDA FoodKeeper data gives pantry, fridge and freezer durations by product.
