# Cookish — Development Specification (v0.1 draft)



This document turns the preliminary report into something five people can build in five weeks. Part A is shared by everyone; Part B is one section per role. Anything marked **DECISION** is a default that the team should confirm or overrule in the kickoff meeting; anything marked **VERIFY** must be checked against the live AWS console or source before relying on it.

---

## Part A — Shared specification

### A1. What the course marks, and what that means for us

| Requirement from the project specification | Consequence |
|---|---|
| Working prototype with a web interface | The purchase → cook → update loop must work end to end in the demo |
| Compare cost of hosting on-premise vs cloud | Needs measured usage numbers from our deployment (Role 3) |
| Marked on usability, quality, technical achievement, evaluation | Fewer features, finished properly, each with a number behind it |
| System **and** user evaluation | Load test, correctness tests, image accuracy, and a small user study |
| Every member presents; peer assessment | Each role owns one demo/report segment (A10) |
| AI use allowed but must be declared (where, how, what was learnt) | Summarize AI usage in the final report or somewhere. |
| Final report ≤ 10 pages incl. everything; public repo URL | Keep final report clean; public GitHub repo from the start |

### A2. Scope

**Must have (demo-critical)**

1. Sign up / sign in; first-time preference setup (allergens, diets, cuisines, time, equipment).
2. Inventory with coarse quantities: manual add, edit, remove.
3. Grocery import (via photo/receipt/oral description) → reviewed draft → saved to inventory.
4. Cook: one suggestion at a time for *N* people (Remember last choice), tag adjustments (Quicker, Less oil, More protein…), "Not this", "Cook this", "previous one".
5. After cooking: confirm consumption with estimation ("Running low" / "Used up"), with undo; then rate the dish (Like / Maybe / Dislike).
6. Shop: basket for *N* people × *M* meals (Remember last choice), tag adjustments, confirm purchases → inventory.

Anything marked *optional* later in this document is outside this list and is built only once everything above works.

### A3. Architecture

```
                         ┌────────────────────┐
  Browser (React SPA) ── │  Amplify Hosting   │  static assets, HTTPS, CI from GitHub
        │                └────────────────────┘
        │  JWT (Cognito)
        ▼
  ┌─────────────────────────────────────────────────┐
  │ API Gateway (HTTP API) + Cognito JWT authorizer │
  └───────┬──────────────────────────┬──────────────┘
          │ /api/*                   │ /ai/*
          ▼                          ▼
  ┌──────────────────┐        ┌──────────────────┐
  │ api Lambda       │        │ ai Lambda        │──► AI(multimodal LLM or OCR...)
  │ FastAPI, in VPC  │        │ outside VPC      │
  └───────┬──────────┘        └──────────────────┘
          │
          ▼
  ┌──────────────────┐
  │ RDS Postgres     │
  └──────────────────┘

  CloudWatch: logs, metrics, dashboard, alarms · Secrets Manager: DB credentials · AWS Budgets: spend alarm
```

**Key design choices**

- **Two Lambdas, two network zones.** Only `api` talks to the database, so only `api` lives in the VPC. `ai` calls the model provider (To Be Defined) and stays outside the VPC. `api` never needs the public internet, so there is no NAT gateway (~US$32/month) and no VPC endpoint.
- **The model never writes to the database.** `ai` only returns a draft. The user reviews it, and only that confirmed request to `api` changes inventory. This implements the report's "the model cannot directly write inventory or relax a dietary restriction".
- **Interactive and AI paths scale separately.** `api` and `ai` are separate Lambdas with their own concurrency, so slow model calls cannot slow down Cook/Shop requests.

**DECISION — Region:** `ap-southeast-1` (Singapore). All using one AWS IAM account & one GitHub repo.

### A4. Technology choices

| Layer | Choice | Notes |
|---|---|---|
| Frontend | React + TypeScript + Vite, TanStack Query, Tailwind CSS | Mobile-first responsive layout |
| API | Python 3.12, FastAPI, Pydantic v2, Mangum (Lambda adapter) | One "lambdalith" for `/api/*` |
| ORM / migrations | SQLAlchemy 2 + Alembic | `NullPool` on Lambda |
| Database | RDS PostgreSQL 16, `db.t4g.micro`, single-AZ | Multi-AZ is discussed in the report, not paid for |
| Auth | Cognito user pool, email + password | Frontend uses `aws-amplify` Auth |
| Voice input | Browser Web Speech API → transcript → `/ai/parse-items` | No audio is uploaded or stored |
| Image input | Compressed in the browser (To be tested, 1MB or 6 MB or...), sent in the request body to `/ai/parse-image` | Not stored anywhere |
| Models | Bedrock / Openrouter / ...? | Candidates in B4; provider can change without touching `api` |
| IaC | AWS SAM (`infra/template.yaml`) | **DECISION** — CDK is fine if Role 3 prefers it |
| CI/CD | GitHub Actions with OIDC to AWS; Amplify auto-build for frontend | No long-lived AWS keys in GitHub |
| Load test | k6 | Scripts in `eval/load/` |

### A5. Repository layout

```
cookish/
├── frontend/                React app (Role 1)
├── backend/
│   ├── app/
│   │   ├── main.py          FastAPI app, router registration (Role 1)
│   │   ├── schemas/         Pydantic models = API contract (Role 1, reviewed by all)
│   │   ├── routers/         Thin HTTP handlers; start as stubs returning mock data
│   │   ├── services/
│   │   │   ├── inventory.py     (Role 2)
│   │   │   ├── stock_events.py  (Role 2)
│   │   │   ├── cook.py          (Role 5)
│   │   │   └── shop.py          (Role 5)
│   │   ├── reco/            Pure recommendation functions, no DB imports (Role 5)
│   │   └── db/              Models, session, repositories (Role 2)
│   ├── migrations/          Alembic (Role 2)
│   ├── seed/                ingredients.csv, recipes/*.yaml, seed.py (Roles 2 + 5)
│   └── tests/
├── ai/                      ai Lambda, prompts, schemas (Role 4)
├── infra/                   SAM template, scripts (Role 3)
├── eval/                    load/, reco_scenarios/, image_set/, user_study/
├── docs/                    openapi.json (generated), diagrams/
└── docker-compose.yml       Whole stack locally: frontend, backend, Postgres
```

**Rule:** routers contain no business logic. A router validates input, calls one service function, and returns its result. Stubs are replaced by swapping the body of the service function, so nobody edits another role's files.

### A6. Database — initial design

Conventions: `id uuid` primary keys (default `gen_random_uuid()`), `created_at timestamptz default now()`, snake_case, enums as Postgres `text` with `CHECK` constraints (easier to migrate than native enums). Every table holding user data has `household_id`, and every query on it filters by the caller's household.

**Three-valued rule (from the report):** known-zero, unknown and not-applicable stay distinct. `NULL` always means *unknown*. Never coerce `NULL` to `0`, and never invent gram quantities from a coarse state.

#### Identity

| Table | Columns |
|---|---|
| `users` | `id` (= Cognito `sub`), `email`, `display_name`, `created_at` |
| `households` | `id`, `name`, `created_at` |
| `household_members` | `household_id` FK, `user_id` FK, `role` (`owner`/`member`), PK (`household_id`, `user_id`) |
| `preferences` | `household_id` PK FK, `allergens text[]`, `diets text[]`, `disliked_ingredient_ids uuid[]`, `cuisines text[]`, `max_cook_minutes int`, `max_difficulty smallint`, `equipment text[]`, `household_size smallint`, `last_cook_people smallint`, `last_shop_people smallint`, `last_shop_meals smallint`, `taste_weights jsonb`, `updated_at` |

MVP: a household is created automatically at first login with one member. Inviting members is optional, but the schema already supports it.

`household_size` is asked once at setup and seeds the people count; after that Cook and Shop each remember their own last choice.

Preferences belong to the **household**, not the user; there is no separate personal profile: a meal is cooked for everyone, and inventory, sessions and baskets are already keyed by household. A user is only a login. With several members, `allergens` and `diets` hold the union of everyone's restrictions.

`allergens`, `diets` and `equipment` are **hard** constraints. `cuisines`, `max_cook_minutes` and `taste_weights` are **soft**.

#### Catalogue (global, read-only at runtime)

| Table | Columns |
|---|---|
| `ingredients` | `id`, `canonical_name` unique, `aliases text[]`, `category` (produce, meat, seafood, dairy, grain, pantry, condiment, frozen…), `countable bool`, `default_unit`, `allergen_tags text[]`, `diet_flags text[]`, `shelf_life_days_pantry int`, `shelf_life_days_fridge int`, `shelf_life_days_freezer int`, `default_storage`, `is_staple bool`, `purchase_unit` (e.g. "pack"), `purchase_unit_size numeric`, `purchase_unit_measure` (g, ml, pcs) |
| `recipes` | `id`, `title`, `base_recipe_id` FK nullable (variants point at their base), `variant_label`, `cuisine`, `total_minutes`, `active_minutes`, `difficulty smallint` (1–3), `servings smallint`, `equipment text[]`, `taste_tags text[]` (e.g. `light`, `spicy`, `high_protein`, `low_oil`), `diet_flags text[]`, `steps jsonb`, `source`, `license`, `reviewed bool` |
| `recipe_ingredients` | `recipe_id` FK, `ingredient_id` FK, `quantity numeric` nullable, `unit`, `coarse_amount` (e.g. "half a cabbage"), `essential bool`, `prep_note`, PK (`recipe_id`, `ingredient_id`) |

`is_staple` marks things like salt, oil and soy sauce that are assumed present and never block a recipe.

#### Inventory and stock events

| Table | Columns |
|---|---|
| `inventory_items` | `id`, `household_id`, `ingredient_id` FK nullable (free-text items allowed), `display_name`, `count numeric` nullable, `unit` nullable, `remaining_state` (`enough`/`low`/`out`/`unknown`), `storage` (`pantry`/`fridge`/`freezer`), `source` (`manual`/`receipt`/`photo`/`voice`/`shop_confirm`), `acquired_at date`, `label_date date` nullable, `label_date_kind` (`use_by`/`best_before`) nullable, `est_use_first_date date` nullable, `freshness_confirmed_at timestamptz` nullable, `last_confirmed_at timestamptz`, `revision int default 1`, `deleted_at timestamptz` nullable |
| `stock_events` | `id`, `household_id`, `user_id`, `type` (`purchase`/`consume`/`adjust`/`undo`), `idempotency_key text`, `ref_type` (`cook_session`/`basket`/`manual`), `ref_id uuid` nullable, `reverts_event_id` FK nullable, `reverted_by_event_id` FK nullable, `created_at`; **unique** (`household_id`, `idempotency_key`) |
| `stock_event_lines` | `id`, `event_id` FK, `inventory_item_id` FK, `before jsonb` nullable, `after jsonb` nullable |

- **One row is one batch.** Buying eggs twice creates two rows with their own dates; rows are never merged automatically. `GET /api/inventory` returns them grouped by ingredient. Availability is judged across all usable batches of an ingredient; consumption is taken from the batch with the earliest use-first date and spills into the next one.
- **Counts or states, by ingredient.** Ingredients with `countable = true` (eggs, tomatoes, packs of tofu) carry a `count`; the rest carry only a `remaining_state`. A user may still type an exact amount for anything ("500 g flour") and it is stored as given, but the system never derives a number from a state.
- `label_date` is a date printed on the package; `est_use_first_date` is our estimate. They are different columns on purpose and the UI must label them differently.
- Every inventory change goes through one function, `apply_stock_event(...)`, in a single transaction: insert event → write lines with before/after snapshots → update items and bump `revision`.
- **Idempotency:** a repeated `idempotency_key` returns the original event, with no second change.
- **Stale edits:** `PATCH` carries the client's `revision`; a mismatch returns `409`.
- **Undo:** creates an `undo` event restoring each line's `before` snapshot. If an item's `revision` has changed since the original event, that line is reported as a conflict instead of being silently overwritten.

#### Sessions, feedback, cooking

| Table | Columns |
|---|---|
| `sessions` | `id`, `household_id`, `user_id`, `mode` (`cook`/`shop`), `people smallint`, `constraints jsonb` (current merged request), `adjustments jsonb` (ordered history of tags/free text), `shown_recipe_ids uuid[]` (in display order), `position int` (index of the suggestion currently shown), `status` (`active`/`done`/`abandoned`), `created_at`, `expires_at` |
| `recipe_feedback` | `id`, `household_id`, `user_id` (who gave it), `recipe_id`, `session_id` nullable, `cook_record_id` FK nullable, `signal` (`like`/`maybe`/`dislike`/`cooked`/`skipped`/`starred`/`unstarred`), `created_at` |
| `cook_records` | `id`, `session_id`, `recipe_id`, `household_id`, `user_id`, `people smallint`, `status` (`selected`/`confirmed`/`abandoned`), `stock_event_id` FK nullable, `created_at` |

- `like` / `maybe` / `dislike` are recorded only **after cooking**, against a confirmed `cook_record`. Before cooking the only signals are `skipped` ("Not this") and `cooked` ("Cook this", once confirmed).
- "Previous one" moves `position` back through `shown_recipe_ids`; "Not this" appends a new recipe and moves it forward.

#### Shopping

| Table | Columns |
|---|---|
| `baskets` | `id`, `session_id`, `household_id`, `people smallint`, `meals smallint`, `status` (`suggested`/`confirmed`/`abandoned`), `stock_event_id` FK nullable, `created_at` |
| `basket_meals` | `basket_id` FK, `recipe_id` FK, `position smallint` |
| `basket_items` | `id`, `basket_id` FK, `ingredient_id` FK, `needed_qty numeric` nullable, `needed_unit`, `suggested_packs smallint`, `needs_check bool`, `reason text`, `actual_bought bool` nullable, `actual_packs smallint` nullable |

Suggested and actual quantities are separate columns, so that what was recommended can be compared with what was bought.

#### Assisted entry

There is no table for assisted entry. `/ai/parse-image` and `/ai/parse-items` return a draft synchronously; the reviewed items are saved through `POST /api/inventory/items` with `source` set to `receipt`, `photo`, `voice` or `manual`. Each `ai` call writes `model_id`, token counts and latency to a structured CloudWatch log, so that the cost model in the final report uses measured numbers.

#### Tenant isolation

Mandatory: every repository function takes `household_id` from the verified JWT, never from the request body, and a test suite proves user A cannot read or modify user B's rows on every endpoint. Optional: Postgres row-level security with `SET LOCAL app.household_id` as defence in depth.

### A7. API contract

Base path `/api` (served by `api` Lambda) and `/ai` (served by `ai` Lambda). All routes require a Cognito JWT. The source of truth is the Pydantic models in `backend/app/schemas/`; `docs/openapi.json` is generated from them and the frontend client is generated from that file.

| Method and path | Purpose | Service owner |
|---|---|---|
| `GET /api/me` | Profile, household and its preferences; creates user + household on first call | Role 2 |
| `PUT /api/household/preferences` | Save the household's preferences | Role 2 |
| `GET /api/ingredients?q=` | Catalogue search / autocomplete | Role 2 |
| `GET /api/inventory` | List items, with `est_use_first_date` | Role 2 |
| `POST /api/inventory/items` | Add one or many items (creates a `purchase` event) | Role 2 |
| `PATCH /api/inventory/items/{id}` | Edit item; requires `revision` | Role 2 |
| `DELETE /api/inventory/items/{id}` | Soft delete (an `adjust` event) | Role 2 |
| `GET /api/stock-events?limit=` | Recent changes, for the undo list | Role 2 |
| `POST /api/stock-events/{id}/undo` | Undo an event | Role 2 |
| `GET /api/use-first` | Items to use soon, ordered by urgency (optional) | Role 5 |
| `POST /api/cook/sessions` | Start a Cook session (people defaults to the last choice, then is saved); returns first suggestion | Role 5 |
| `POST /api/cook/sessions/{id}/adjust` | Apply a tag or structured patch; returns new suggestion | Role 5 |
| `POST /api/cook/sessions/{id}/next` | "Not this": records `skipped`, returns another suggestion | Role 5 |
| `POST /api/cook/sessions/{id}/previous` | "Previous one": returns the suggestion shown before | Role 5 |
| `POST /api/cook/sessions/{id}/select` | "Cook this"; returns proposed consumption | Role 5 |
| `POST /api/cook/records/{id}/confirm` | Confirm what was used → `consume` event | Role 5 calls Role 2's `apply_stock_event` |
| `POST /api/cook/records/{id}/feedback` | Like / Maybe / Dislike, after cooking | Role 5 |
| `GET /api/recipes/{id}` | Recipe detail | Role 5 |
| `PUT /api/recipes/{id}/star` | Star / unstar (shared by the household) | Role 5 |
| `POST /api/shop/sessions` | Start a Shop session (people and meals default to the last choice, then are saved); returns a basket | Role 5 |
| `POST /api/shop/sessions/{id}/adjust` | Apply tag; returns revised basket | Role 5 |
| `POST /api/shop/baskets/{id}/confirm` | Confirm actual purchases → `purchase` event | Role 5 calls Role 2 |
| `POST /ai/parse-image` | Compressed receipt or grocery photo → draft items | Role 4 |
| `POST /ai/parse-items` | Text (typed, or a voice transcript) → draft items | Role 4 |
| `POST /ai/interpret` | Free text → validated constraint patch (optional) | Role 4 |

**Conventions**

- Mutating requests carry an `Idempotency-Key` header (a UUID generated by the client per user action).
- Errors: `{"error": {"code": "STALE_REVISION", "message": "...", "details": {...}}}` with codes `VALIDATION`, `NOT_FOUND`, `FORBIDDEN`, `STALE_REVISION`, `CONFLICT`, `NO_RESULT`, `UPSTREAM_UNAVAILABLE`.
- `NO_RESULT` from Cook/Shop includes `relaxable`: the list of soft conditions the user may choose to relax. Hard constraints are never listed.
- Times are ISO 8601 UTC; dates are `YYYY-MM-DD`.

**Shared shapes (abridged)**

```jsonc
// Suggestion — returned by every Cook endpoint
{
  "session_id": "…",
  "recipe": { "id": "…", "title": "…", "total_minutes": 25, "difficulty": 1, "taste_tags": ["light"] },
  "ingredients": [
    { "ingredient_id": "…", "name": "cabbage", "amount": "half", "essential": true,
      "status": "have" }          // have | low | missing | unknown | check | staple
  ],
  "needs_check": [                 // essential ingredients whose stock is unknown
    { "item": { "id": "…", "display_name": "rice", "revision": 3, … } }   // the batch to update
  ],
  "freshness_check": [             // batches the user should inspect before cooking
    { "inventory_item_id": "…", "name": "chicken thigh", "reason": "past estimated use-first date" }
  ],
  "has_previous": true,            // whether "Previous one" is available
  "available_nudges": ["less_oil"], // only nudges that produce a suitable different recipe now
  "people": 2,                     // ingredient amounts are already scaled to this
  "applied_constraints": { "max_minutes": 30, "tags": ["quicker"] }
}

// DraftItem — produced by /ai/parse-image and /ai/parse-items, reviewed by the user
{
  "raw_text": "FP CABBAGE RND 1PC",
  "ingredient_id": "…",            // null if no confident catalogue match
  "display_name": "Cabbage",
  "count": 1, "unit": "pcs",       // null = unknown
  "storage": "fridge",
  "confidence": 0.86
}
```

### A8. Environments and conventions

- One AWS account, one region, **one deployed environment**: a single stack named `cookish`. Resources are named `cookish-<thing>` and tagged `project=cookish`. Locally, `docker compose up` starts the frontend, the backend and Postgres together, and the part you are editing can run directly on your machine instead (`pnpm dev`, `uv run uvicorn`). Each person's local database is their own and is not shared: everyone gets the same starting data from the migrations and seed files in the repository. the deployed stack is what the user study, the load test and the demo use.
- Nobody creates resources by clicking in the console except to experiment; anything that survives goes into `infra/template.yaml`.
- Git: trunk-based. `main` is protected and auto-deploys to the stack. Short-lived branches, pull requests with one reviewer, CI must pass.
- Secrets live in Secrets Manager or SSM Parameter Store, never in the repo. `.env.example` documents the variables.
- Every Lambda logs structured JSON with `request_id`, `household_id`, `route`, `latency_ms`.
- An AWS Budgets alarm at US$20 and US$40 notifies the whole group.

### A9. Non-code ownership

| Deliverable | Owner |
|---|---|
| User study (protocol, sessions, results) | Role 1 |
| Report and slide editing, 10-page budget, AI-use declaration | Role 2 |
| On-premise vs cloud cost comparison; load test; Code Explanation section | Role 3 |
| Assisted-entry (image and voice) accuracy and cost evaluation | Role 4 |
| Recommendation correctness evaluation; business case and pricing | Role 5 |

### A10. Evaluation plan (reduced from the preliminary report)

| Question | Method | Target | Owner |
|---|---|---|---|
| Are recommendations feasible? | 100 scripted Cook/Shop scenarios, each with up to 3 refinements | 0 prohibited ingredients; all hard constraints preserved; basket contents correct | Role 5 |
| Are stock updates reliable? | Automated tests: retries, duplicate keys, concurrent edits, undo, cross-account access | 0 double changes; 0 cross-account reads | Role 2 |
| Is assisted entry useful? | 50 team-owned receipt/grocery images and 20 spoken descriptions, with hand labels | Precision ≥ 90%; report recall, latency, cost per request | Role 4 |
| Is the service responsive? | k6, 20 concurrent sessions for 30 minutes | p95 < 2 s for tag adjustments; < 1% errors | Role 3 |
| Is it easier to use? | 6–8 participants, one 30-minute session, Cookish vs a static-filter view of the same catalogue, counterbalanced | ≥ 20% lower median decision time; ≥ 80% unassisted completion; ease ≥ 4/5 | Role 1 |
| What does it cost? | Measured tokens, Lambda duration and storage → monthly cost vs households; on-premise TCO for the same load | Break-even chart | Role 3 |

### A12. Deviations from the preliminary report

The final report must state these and give the reason. Role 2 keeps this list current.

| Preliminary report | This specification | Reason |
|---|---|---|
| API and worker on ECS Fargate | Two Lambda functions | No idle cost, no cluster to operate, scales per request |
| Background worker, SQS queue, private S3 image bucket, 7-day image deletion | Synchronous call; images are not stored | Measured latency is short enough (cite Role 4's numbers); storing nothing is the stronger privacy position |
| React app on S3 + CloudFront | Amplify Hosting | Same underlying services with built-in CI from GitHub |
| EventBridge scheduled use-first check and opt-in reminders | No scheduled jobs; use-first list is optional | Out of scope for the time available |
| Database row-level policies | Household filtering in the application layer, proven by tests; row-level security optional | Simpler with a single API role |
| Each card shows why the recipe was recommended | No reason shown | Judged unnecessary; keeps the card minimal |
| Like / Maybe / Dislike on a suggestion | Rating asked only after the meal is cooked; "Not this" before cooking | A rating of a dish nobody has eaten is a weak signal |
| Two-week pilot with 12–15 participants; trials in competitor apps | 6–8 participants, one session each; competitors compared in writing only | Five weeks of development time |
| Duplicate-receipt detection | Not built | Out of scope |
| Free-text refinement with an 8 s latency target | Optional (`/ai/interpret`) | Tag adjustments cover the core loop |

---

## Part B — Role briefs

Role numbers follow the team's agreed split. Each brief lists what to build, suggested approach and references, what the role depends on, and what "done" means.

### B1. Role 1 — Frontend and API contract (Su Yubo)

**Build**

1. **Contract first (by M0).** Pydantic schemas for every route in A7; FastAPI routers that return realistic mock data; generated `docs/openapi.json`; a typed frontend client generated with `openapi-typescript` (or `orval` for TanStack Query hooks). CI fails if the committed OpenAPI file is out of date.
2. **Repository skeleton.** Layout from A5, `docker-compose.yml`, linting (ruff, eslint), pytest and vitest wired into CI, `README` with a five-minute local start.
3. **Screens.**
   - *Onboarding:* three short steps — allergens/diets, cuisines, time and equipment.
   - *Kitchen (inventory):* grouped by storage; countable items show their count with +/− buttons, the rest show a state chip that cycles on tap (Enough → Running low → Out); batches of the same ingredient are grouped under one row that expands; add via manual search, photo, voice or typed text. An optional "use soon" section sits on top.
   - *Import review:* editable list of draft items with confidence shown; nothing is saved until the user confirms, which posts the items to `POST /api/inventory/items`.
   - *Cook:* a small people stepper prefilled with the last choice (changing it sends an `adjust` with the new count); one large card — title, time, ingredient list with have/missing/unknown markers; buttons "Not this", "Cook this" and "Previous one" (disabled when `has_previous` is false); a row of adjustment tags; a focused "do you still have eggs?" prompt when `needs_check` is non-empty, and a "check the date and how it was stored" prompt for each `freshness_check` entry with answers "It's fine" (a `PATCH` that sets `freshness_confirmed_at`) and "Throw away" (a `PATCH` to `out`). Every freshness date is labelled as an estimate or as a label date, and the card carries a short note that estimates and checks do not guarantee food safety.
   - *After cooking:* per-ingredient "Still enough" / "Running low" / "Used up" / "Didn't use" (countable items show the proposed new count instead) with an undo toast, then one Like / Maybe / Dislike question about the dish. Rating is skippable and is never asked before the meal is confirmed as cooked.
   - *Shop:* people and meals inputs prefilled with the last choice; basket grouped by category, with "Check at home" on items flagged `needs_check`; example meals the basket covers; tags; "confirm purchases" checklist.
   - *Activity:* recent stock events with undo.
4. **Baseline view for the user study:** a plain filterable recipe list over the same catalogue (cuisine, time, diet checkboxes). It is the comparison condition, so keep it honest but simple.

**Approach and references**

- Auth with `aws-amplify` (`Amplify.configure` + `fetchAuthSession` to attach the JWT); wrap in one `useAuth` hook so the provider can be swapped if Cognito is unavailable.
- Photo entry: downscale in the browser before sending (canvas or `browser-image-compression`); the target size comes from Role 4's week-1 test (A4), so keep it a single constant. Show a progress state while `/ai/parse-image` runs, time out at 25 s, and offer "Retry" and "Enter manually".
- Voice entry: a microphone button using the browser **Web Speech API** (`SpeechRecognition`); show the live transcript, let the user edit it, then send it to `/ai/parse-items` and reuse the import review screen. Chrome and Safari support it; where it is missing, hide the button and keep the typed-text box.
- Optimistic updates for inventory chips with rollback on `409`.
- Generate one `Idempotency-Key` per user action and reuse it on retry.
- Component primitives: shadcn/ui or Radix. Keep the visual design restrained; usability is marked, decoration is not.
- Instrument timing in the client (time from page open to "Cook this", number of taps); the user study needs these numbers.

**User study** — protocol, consent sheet, task script, SUS-style ease question, and a short interview. Three tasks: choose and refine a meal; build and confirm a basket; recover after a simulated three-day gap in recording. Store results in `eval/user_study/`.

**Depends on:** nobody for M0. **Blocks:** everyone until M0 ships.

**Done when:** all must-have screens work against the real backend on a phone-sized viewport, and the study data is collected.

### B2. Role 2 — Database and inventory services (SEEVON)

**Build**

1. **RDS.** PostgreSQL 16 on `db.t4g.micro` in private subnets (the VPC itself is Role 3's); credentials in Secrets Manager; automated backups on. Provide a documented way to reach it for migrations (SSM port forwarding through a tiny bastion, or a one-off migration Lambda — the Lambda is tidier).
2. **Schema.** SQLAlchemy models and Alembic migrations for everything in A6. Indexes on `inventory_items(household_id) WHERE deleted_at IS NULL`, `stock_events(household_id, created_at DESC)`, `recipe_ingredients(ingredient_id)`, and a GIN index on `ingredients.aliases`.
3. **Seeding.** `seed.py` loads `seed/ingredients.csv` and `seed/recipes/*.yaml` idempotently. The same `ingredients.csv` is bundled into Role 4's `ai` Lambda, so keep its IDs stable (assign UUIDs in the CSV, do not generate them at load time). Role 5 writes the recipe content; you own the loader and the ingredient table's integrity.
4. **Services.** `GET /me` bootstrap, preferences, ingredient search, inventory CRUD, `apply_stock_event`, undo, event listing — exactly as specified in A6.
5. **A small internal API for other roles**, documented in `backend/app/db/README.md`:
   - `get_inventory_snapshot(s, household_id)` → what Role 5's algorithms read.
   - `apply_stock_event(s, user, type, lines, idempotency_key, ref_type, ref_id)` → what Role 5 calls to change stock.
   - The agreed signatures are in [backend/app/db/README.md](../backend/app/db/README.md).
6. **Reliability tests.** Duplicate idempotency keys; two concurrent `PATCH`es on one item; undo after a later edit; cross-household access attempts on every route.

**Approach and references**

- Lambda and Postgres connections: create the engine at module import with `NullPool` (or `pool_size=1`) so warm invocations reuse one connection. At our scale RDS Proxy is unnecessary; mention it in the report as the next step and state the `max_connections` ceiling of the instance.
- Concurrency: `SELECT … FOR UPDATE` on the affected items inside the event transaction, plus the `revision` check.
- Idempotency: rely on the unique constraint and catch the violation, rather than check-then-insert.
- Ingredient search: `pg_trgm` similarity over `canonical_name` and `aliases` is enough; no vector database.
- Ingredient seed data: start from the union of ingredients used by Role 5's recipes (expect 150–250 rows), not from a giant external list.
- Shelf-life columns: USDA **FoodKeeper** dataset (public domain, downloadable as JSON) gives pantry/fridge/freezer durations by product. **VERIFY** the current download location.

**Report and slides editor.** Own the outline, the page budget per section, consistent terminology, and the merged AI-use declaration.

**Depends on:** Role 1's schemas; Role 3's VPC. **Blocks:** Role 5 needs `apply_stock_event` and `get_inventory_snapshot` by about 20 Oct — publish the function signatures early even if the bodies are not finished.

**Done when:** the reliability test suite passes in CI against a real Postgres, and the seeded database on the deployed stack is usable by everyone.

### B3. Role 3 — Cloud platform, delivery and cost (NICOLE)

**Build**

1. **Day 1: verify the account.** Can we create IAM roles? Are Cognito, Bedrock, Amplify, API Gateway and RDS available in the region? Record the answer in `infra/README.md`. Fallbacks: Learner Lab `LabRole` for all Lambdas; Supabase Auth instead of Cognito; S3 + CloudFront instead of Amplify; a model provider's API directly instead of Bedrock; the single-EC2 Compose deployment as last resort.
2. **Network.** VPC with two private subnets and security groups (`api` Lambda → RDS on 5432 only). No NAT gateway and no VPC endpoints; the `ai` Lambda is deployed outside the VPC.
3. **API.** API Gateway HTTP API; Cognito JWT authorizer; routes `/api/{proxy+}` → `api` Lambda and `/ai/{proxy+}` → `ai` Lambda; CORS restricted to the Amplify domain; throttling limits.
4. **Lambda packaging.** FastAPI + Mangum as a zip built by `sam build` (switch to a container image if dependencies exceed the zip limit). Start with 512 MB memory; measure cold starts and tune. Give the `ai` Lambda a 29 s timeout (API Gateway cuts off at 30 s) and read the model credentials from Secrets Manager.
5. **Auth.** Cognito user pool and app client (SRP flow, email verification); pass pool ID and client ID to the frontend as build-time environment variables.
6. **Frontend hosting.** Amplify Hosting connected to the GitHub repo, build spec for `frontend/`, SPA rewrite rule (all non-file paths → `/index.html`), environment variables for the API URL and Cognito IDs.
7. **CI/CD.** GitHub Actions: lint + test on pull requests; on merge to `main`, `sam deploy` to the single stack using an OIDC role.
8. **Observability.** CloudWatch dashboard (requests, p50/p95 latency, errors, Lambda duration and concurrency per function, `ai` latency and timeout count, RDS CPU and connections); alarms on 5xx rate; AWS Budgets alerts.

**Load test.** k6 script simulating a session: sign in → inventory → cook session → 3 adjustments → select → confirm. Ramp to 20 concurrent users, hold 30 minutes. Report p50/p95/p99 per route, error rate, cold-start share, and the cost of the run from Cost Explorer. If time allows, repeat against the single-EC2 Compose deployment for a "one box vs managed services" comparison.

**On-premise vs cloud cost comparison** (required by the project specification; a paper analysis, not a second deployment).

- *Cloud side:* fixed monthly costs (RDS) plus per-household variable costs derived from measurements — Lambda GB-seconds and requests, API Gateway requests, model tokens (from the `ai` Lambda's CloudWatch logs, via Logs Insights), data transfer. Use the AWS Pricing Calculator and save the estimate link.
- *On-premise side:* size hardware for the same peak load with N+1 redundancy; include servers amortised over 3–5 years, storage, networking, rack or colocation space, power and cooling, internet bandwidth, backups, software, and administrator labour.
- *Output:* monthly cost vs active households (100, 1 000, 10 000) for both, the break-even point, and a short discussion of what is not captured (elasticity, time to market, on-premise GPU needs for local models).

**Code Explanation section** of the report: repo map, how to run locally, how to deploy, public URL.

**Depends on:** Role 1's skeleton. **Blocks:** everyone needs M1.

**Done when:** a merge to `main` reaches the deployed stack without manual steps, the dashboard shows live traffic, and the cost model is filled with measured values.

### B4. Role 4 — AI-assisted input (COLIN)

**Build**

1. **Week 1: measure latency and choose the model.** Compare the candidate providers in A4 and two or three image sizes. Run 10 real receipts (include the longest you can find) and 5 grocery photos through the candidate model and record the time per call. This decides whether the synchronous design in A3 stands: it does if p95 stays under about 10 s. Above that, raise it with the team, since the fallback is a queue and a background worker.
2. **`/ai/parse-image`.** Receives a compressed image (base64 in JSON, with `kind` = `receipt` or `photo`), calls the model, validates the output and returns `DraftItem[]`. The accepted size is fixed by the week-1 test; the ceiling is Lambda's 6 MB request limit, which base64 encoding reduces to roughly 4 MB of image. The image is never written to disk or S3.
3. **`/ai/parse-items`.** Text → `DraftItem[]`; used for typed lists and voice transcripts ("I bought two packs of tofu, some kangkong and a dozen eggs"). Must cope with spoken quantities and transcription errors.
4. **`/ai/interpret` (optional).** Free text such as "something lighter, no frying" → a constraint patch validated against Role 5's schema. It may only set soft fields; attempts to change allergens or diets are rejected in code, not by prompt.
5. **Degradation.** Set a model-call timeout of about 20 s. Timeouts and model errors return `UPSTREAM_UNAVAILABLE`; the frontend then offers retry or manual entry. Demonstrate this in the evaluation by disabling the model.

**Model options for receipt and grocery-photo recognition**

| Option | How it works | Trade-off |
|---|---|---|
| **A. Multimodal LLM (recommended)**, through Bedrock, OpenRouter or the provider's own API | Send the image plus the catalogue names; ask for structured output through a tool/JSON schema | One call, handles messy receipts and photos alike, no training. Cost per image is the highest of the three but still around a cent. |
| B. Amazon Textract `AnalyzeExpense` + small text LLM | Textract extracts receipt line items; a cheap text model maps them to catalogue ingredients | Strong on receipts, useless for food photos; two services to wire up |
| C. Open-source OCR + text LLM | PaddleOCR or Tesseract in a container Lambda, then a text model | Lowest per-call cost; larger package, slower cold start, weaker on crumpled receipts |

Recommendation: build A, and if time allows evaluate two model sizes on the same 50 images — for example a small and a mid-sized model from the same family. An accuracy-vs-cost-vs-latency table is strong evaluation material. **VERIFY** current model IDs and prices with the chosen provider; if it is Bedrock, also check regional availability and request model access on day 1 because approval can take time.

**Open-source references worth reading (not necessarily using)**

- *Receipts:* the CORD and SROIE datasets and the Donut model (OCR-free document parsing) show what structured receipt extraction looks like; PaddleOCR for multilingual OCR.
- *Food photos:* YOLO-World and Grounding DINO for open-vocabulary detection; Food-101 for classification. These need a GPU or heavy containers, which is a good argument for the managed-model route in the report.
- *Ingredient text parsing:* `ingredient-parser` (strangetom, Python) parses "2 large eggs" into quantity/unit/name; `rapidfuzz` for fuzzy matching against catalogue aliases.
- *Product names:* Open Food Facts for mapping branded product names to generic foods.
- *Voice:* transcription happens in the browser with the Web Speech API (Role 1 builds the microphone button), so the backend only ever receives text. Amazon Transcribe or Whisper are server-side alternatives if browser accuracy on local food names turns out to be too poor; either way the transcript goes to `/ai/parse-items`.

**Approach**

- Use the provider's structured-output or tool-calling feature (Bedrock Converse, or an OpenAI-compatible API such as OpenRouter) with a schema of `DraftItem[]`; keep the provider call behind one small function so it can be swapped; validate again with Pydantic; one retry on invalid output.
- Matching: give the model the catalogue as `id | canonical_name` lines and require it to return an `ingredient_id` or `null`. Post-check that every returned ID exists. Non-food lines (bags, discounts, totals) must be dropped.
- Never let the model infer freshness from a photo; the report explicitly rules this out. Quantity is `null` when not visible.
- Treat text inside images as data: the system prompt states that instructions found on a receipt are to be ignored, and the schema leaves no field through which they could act.
- Local singlish/Malay/Chinese product names on Singapore receipts ("kangkong", "tau kwa", "ikan bilis") should be in `ingredients.aliases`; collect misses during evaluation and feed them back to Role 2.
- Log `model_id`, tokens and latency on every call as one structured CloudWatch log line, so that Role 3 can cost both paths.
- Load the bundled `ingredients.csv` once at module import, not per request.

**Evaluation.** 50 team-owned images (about 30 receipts, 20 grocery photos) and 20 spoken descriptions (recorded transcripts) with hand-labelled ground truth in `eval/image_set/labels.json`; a script computes precision, recall, time to result, and cost per image; measure median correction time in the review screen with Role 1.

**Depends on:** Role 3's `ai` Lambda route and model credentials; Role 2's `ingredients.csv`. **Blocks:** nothing critical — manual entry keeps the loop alive.

**Done when:** a phone photo of a real receipt and a spoken description each become a reviewed inventory update on the deployed stack, and the accuracy table exists.

### B5. Role 5 — Recommendation algorithms and recipe catalogue (WENLONG)

**Build**

1. **Recipe catalogue.** 40–60 reviewed recipes (base + variants such as "less oil" or "vegetarian"), in `seed/recipes/*.yaml`, each with ingredients mapped to catalogue names, essential flags, time, difficulty, equipment, taste tags and diet flags. Lean towards everyday Singapore home cooking so that the user study feels real.
2. **`reco/` library — pure functions, no database imports**, so that the 100 scenarios run in milliseconds:
   - `filter_recipes(recipes, hard_constraints)`
   - `score_recipe(recipe, inventory, prefs, session)` → score, with the per-term breakdown for tests and debugging
   - `suggest(…)`, `adjust(session, tag)` ("Previous one" needs no algorithm: the service replays an entry of `shown_recipe_ids`)
   - `build_basket(recipes, inventory, people, meals, prefs)`
3. **Service layer** `services/cook.py`, `services/shop.py` wiring those functions to sessions, feedback and Role 2's inventory snapshot.
4. **Use-first list** for `GET /api/use-first` (optional). The use-first date itself is computed by Role 2 when inventory is read (below, and [backend/app/db/README.md](../backend/app/db/README.md)); Role 5 turns it into urgency.

**Cook algorithm**

*Step 1 — hard filter.* Remove a recipe if any ingredient carries a household allergen, if it violates a diet flag, if required equipment is missing, or if it exceeds a time limit the user set as strict. This step is never relaxed automatically.

*Step 2 — availability.* Classify each recipe ingredient as `have`, `low`, `missing`, `unknown`, `check` or `staple` from the inventory snapshot (`check` comes from the freshness gate below). An item not confirmed for a long time (suggest > 14 days for perishables) is treated as `unknown`, not `have`. In Cook mode, drop recipes with missing essential ingredients unless nothing else remains.

*People.* Scale recipe amounts by `people / servings` for display and for the proposed consumption after "Cook this". Where an item has a `count` (three eggs), compare it with the scaled need and mark it `low` if short. Where it has only a state, do not invent a comparison: `enough` counts as `have` and `low` as `low`, whatever the people count. `people` is an accepted field of the `adjust` patch, defaults to `preferences.last_cook_people`, and is written back when a session starts or the count changes.

*Step 3 — score.*

```
score = w_cov  · coverage            share of non-staple ingredients on hand
      + w_exp  · expiry_urgency      rises as a usable batch nears its use-first date; zero once past it
      + w_pref · preference          dot(taste_weights, recipe tags) + cuisine match + star bonus
      − w_eff  · effort              normalised time and difficulty against the user's limits
      − w_rep  · repetition          recently cooked or just shown
      − w_unk  · unknown_essentials  essentials whose stock is uncertain
```

Starting weights are hand-set; keep them in one config file and report them. The card does not show why a recipe was suggested, so no explanation text is generated.

*Step 4 — adjustments.* Each tag is a deterministic patch to session constraints (`quicker` → `max_minutes = current − 10`; `less_oil` → require tag `low_oil`; `more_protein` → boost `high_protein`). Patches accumulate, so earlier choices are remembered. When re-ranking after an adjustment, add a **similarity bonus** towards the previously shown recipe (Jaccard similarity over ingredients and tags) so that only the requested dimension changes; prefer a stored variant of the same base recipe when one satisfies the patch.

The suggested nudge buttons come from `Suggestion.available_nudges`, calculated by trying those same patches against the current catalogue and household snapshot. Show an option only if it returns a different recipe satisfying the requested change; hide requests already satisfied by the current dish. This keeps the adjustment rules unchanged while avoiding impossible options such as Easier on a difficulty-1 dish. If a later tag request has no result, reject it without saving its failed restrictions so the current suggestion remains usable.

Explicit relaxation and expired-session recovery use a new session with the achieved absolute time/difficulty limits. Saved Quicker/Easier tags are not applied a second time. A household-owned `previous_session_id` preserves skipped dishes and strict limits during recovery; Reset clears adjustments and skips. Saving household preferences refreshes Cook and Buy, with the interface explaining that the shopping list and ticks will reset.

*Step 5 — learning from feedback.* Keep `taste_weights` as a small map from feature (taste tag, cuisine, main-protein category) to weight. Ratings arrive only after a meal has been cooked: on Like add +η to the recipe's features, on Dislike subtract η, on Maybe (or no rating) do nothing, and clip to a fixed range. "Not this" changes no weights — people skip for many reasons — and only keeps that recipe out of the rest of the session. Cooking a recipe without rating it adds a small +η/4. This is simple, explainable, and enough to test the first hypothesis. Optional: a per-household logistic regression or a Thompson-sampling bandit over the same features.

*Freshness gate (applied in step 2, before scoring).* The report promises that uncertain ingredients are checked or excluded, never promoted. For each batch:

| Batch condition | Treatment |
|---|---|
| Before its use-first date | Usable; urgency grows as the date approaches |
| Past a `use_by` label date | Excluded. Not counted as stock; listed in `freshness_check` so the user can discard it |
| Past a `best_before` label date or past our estimated date, or a perishable with no date at all | `check`: not counted as stock until the user answers. "It's fine" sets `freshness_confirmed_at` and makes it usable for 24 hours; "Throw away" sets it to `out` |

A recipe whose essential ingredient is only available in `check` batches is still shown, with that ingredient in `freshness_check`; if the user throws it away the service immediately returns an alternative. A past-date batch never earns an urgency bonus.

*Unknown essentials.* If the top recipe has an essential ingredient with `unknown` stock, return it in `needs_check` so that the UI asks one focused question, as the report promises.

**Shop algorithm (bounded search, no claim of optimality)**

0. Inputs: `people` and `meals` default to `preferences.last_shop_*` and are written back when a session starts.
1. Candidates: the top *K* ≈ 20 recipes after hard filtering and preference scoring, ignoring availability.
2. Choose *M* meals by beam search (width ≈ 10). The combination score rewards preference, ingredients shared across meals and already confirmed at home, and variety (different main proteins or cuisines); it penalises leftover surplus after pack rounding.
3. Aggregate ingredient needs scaled by `people / servings`.
4. Decide what goes on the list, by tracking mode:
   - *Counted ingredients:* need minus the confirmed count across usable batches, rounded up to purchase units.
   - *State-tracked ingredients:* included when the state is `low` or `out`; left off when it is `enough` and recently confirmed.
   - *Uncertain stock* (`unknown`, stale confirmation, or batches waiting on a freshness check): never silently removed. The item stays on the list with `needs_check = true`, shown as "Check at home".
5. There are no prices, no totals and no budget. The report states that Cookish does not offer budget management.
6. Tags: `more_vegetables`, `longer_lasting` (prefer ingredients with long shelf life), `cover_more_meals`.

Requested recipe IDs must remain in the plan. If a requested recipe fails a hard gate or needs a non-buyable essential such as cooked rice, return an explanation instead of substituting another dish. Basket adjustments preserve ticked ingredients across regenerated item IDs and require an actual-quantity review where counted needs change. `ShopAdjust.replace_tags=true` replaces the keyword list, including an empty list; ordinary nudge requests remain additive.

**Use-first estimate** (Role 2 computes `use_first` when inventory is read; Role 5 computes `days_left` and `urgency` from it when scoring)

```
if label_date is set:            use_first = label_date
else:                            use_first = acquired_at + shelf_life_days[storage]
days_left = use_first − today
urgency   = clamp(1 − days_left / window, 0, 1)   if days_left ≥ 0     window ≈ 3–5 days by category
          = 0                                     if days_left < 0     → freshness gate applies
```

Shelf-life numbers come from the FoodKeeper data that Role 2 loads. They are estimates, are always labelled as such, and do not establish food safety.

**Recipe content sources**

Use only original or appropriately licensed content: the repository is public, so check licences before copying anything.

- Safest: write recipes ourselves or draft them with an LLM and have a human review every one (declare this in the AI-use statement). Ingredient lists and basic steps are generally not protected, but copied prose and photos are.
- TheMealDB has a free API and can serve as a structural reference. **VERIFY** its terms before using its text.
- RecipeNLG and Recipe1M are research datasets with restrictive licences; useful for studying data shape, not for shipping content.

**Evaluation.** 100 scenarios in `eval/reco_scenarios/*.yaml`, each defining preferences, an inventory, a request, up to three adjustments, and assertions (no prohibited ingredient; hard constraints preserved after every adjustment; basket covers the chosen meals; pack rounding correct for counted ingredients; state-tracked ingredients included or excluded according to their state). Add property-based tests with `hypothesis`: for random inventories and preferences, an allergen never appears in any output. Keep 30 scenarios unseen during development and report results on those separately.

**Business case and pricing** for the final report: update the motivation and freemium model from the preliminary report, using Role 3's measured cost per household.

**Depends on:** Role 2's `get_inventory_snapshot` and `apply_stock_event`; Role 1's schemas. Can start immediately on `reco/` and the catalogue with fixture data.

**Done when:** all 100 scenarios pass and Cook and Shop work on the deployed stack against real inventory.

---

## Open items for the kickoff meeting

1. Which AWS account are we using, and is it a restricted Learner Lab account?
2. Confirm region, SAM vs CDK, and the two-Lambda synchronous design in A3.
3. Assign the four remaining names to Roles 2–5.
4. Confirm the deviations from the preliminary report listed in A12.
5. Agree a weekly sync time and the TA presentation slot.
