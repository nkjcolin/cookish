# Cookish — project setup and what comes next

Read this first, then the README for your role. The design decisions behind the project are in [SPEC.md](SPEC.md).

## Where to start

| Role | Works on | Read |
|---|---|---|
| 1 — Frontend and API contract | `frontend/`, `backend/app/schemas/`, `backend/app/routers/` | [frontend/README.md](../frontend/README.md) |
| 2 — Database and inventory | `backend/app/db/`, `backend/migrations/`, `backend/seed/`, inventory services | [backend/app/db/README.md](../backend/app/db/README.md) |
| 3 — Cloud platform, delivery and cost | `infra/`, `.github/workflows/` | [infra/README.md](../infra/README.md) |
| 4 — AI-assisted input | `ai/` | [ai/README.md](../ai/README.md) |
| 5 — Recommendation and recipes | `backend/app/reco/`, `backend/seed/recipes/`, Cook and Shop services | [backend/app/reco/README.md](../backend/app/reco/README.md) |

Each role README says what you own, what already exists, what you may change and what you must keep, what other roles expect from you, and your tasks in order. Where two roles meet, the agreement is written in the README of the role that provides it, and the other README links to it.

---

## What exists now

Every screen works on real data, locally and on AWS. What remains is evaluation and the report (stage 4 below), and the gaps each role's README lists.

| Part | State |
|---|---|
| API contract | Complete: 25 endpoints, defined in `backend/app/schemas/` and exported to [openapi.json](openapi.json) |
| Frontend | Complete against the contract: every screen of the Figma design, plus a kitchen-history screen |
| Backend | Every endpoint is real: PostgreSQL inventory and stock events, Cook and Shop recommendations with stored sessions, ratings and learning |
| AI service | The school's SoClaaS model on AWS; an offline fake locally (`AI_PROVIDER=fake`) |
| Infrastructure | Deployed in `ap-southeast-1` with SAM and Amplify; see [infra/README.md](../infra/README.md) |
| Evaluation | In progress in `eval/` |
| CI | Lints and tests backend, ai and frontend; on `main` it then migrates and deploys |

## Run it

```bash
docker compose up
```

| Service | Address |
|---|---|
| Web app (open it at phone width) | http://localhost:5173 |
| API and interactive docs | http://localhost:8000/api/docs |
| AI service docs | http://localhost:8001/ai/docs |
| Postgres | `postgres://cookish:cookish@localhost:5432/cookish` |

Source folders are mounted, so edits reload without rebuilding. To run one part on your machine instead, see its README; `backend/` and `ai/` need [uv](https://docs.astral.sh/uv/), `frontend/` needs Node 22+ and pnpm.

## How the pieces fit

```
Browser ── Amplify Hosting (static frontend)
   │ Cognito ID token
   ▼
API Gateway ──/api/*──► api Lambda (backend/, in the VPC) ──► RDS Postgres
            └─/ai/*───► ai Lambda (ai/, outside the VPC) ──► model provider
                        migrate Lambda (backend/, in the VPC), run after each deployment
```

Locally, `docker compose up` plays the same parts: `backend` on port 8000, `ai` on 8001, Postgres on 5432, and Vite forwards `/api` and `/ai` to them.

Both Lambdas are ordinary FastAPI apps. On AWS, `app/lambda_handler.py` in each folder converts the Lambda event into a normal request with Mangum; nothing else in the code knows it runs on Lambda.

---

## Conventions everyone follows

### The backend's layers

```
routers/   thin HTTP handlers            Role 1 — do not edit
   │  calls exactly one function in
services/  business logic                Roles 2 and 5
```

- **Keep every service function's name, parameters and return type.** The routers and the frontend depend on them, and so do other roles' services.
- `backend/tests/test_contract.py` calls every endpoint and must keep passing.

### Changing the API contract

The contract will change, and that is fine, but each change alters the frontend's generated types:

1. Agree the change with Role 1.
2. Edit `backend/app/schemas/`, then run `uv run python scripts/export_openapi.py` in `backend/`.
3. Run `pnpm gen:api` in `frontend/` and fix what the type checker reports. If an `/ai` endpoint changed, copy the change into `ai/app/schemas.py`.
4. Commit everything together. CI fails if `docs/openapi.json`, the generated types or the `ai` copy are out of date.

### Changing an agreement between roles

The signatures and file formats in the role READMEs are fixed so that everyone can work in parallel. To change one, agree it with the roles it affects, and update the README that describes it in the same pull request as the code.

### Errors

Raise `ApiError(ErrorCode.X, "message", {details})` from `app/errors.py`; never build an error response by hand. The frontend receives one shape for every failure: `{"error": {"code", "message", "details"}}`. The codes and their HTTP statuses are listed in [backend/README.md](../backend/README.md#errors).

### Changing inventory safely

- Every request that changes inventory carries an `Idempotency-Key` header, a UUID the frontend creates once per user action. A repeated key changes nothing a second time.
- Every edit of an item carries the `revision` the user last saw. If it has changed since, the answer is `STALE_REVISION`.
- Every change becomes a stock event that can be undone.

### Who is calling

`backend/app/auth.py` gives every endpoint a `CurrentUser` with `user_id`, `household_id` and `email`.

- On AWS, the frontend sends the Cognito **ID token** (`Authorization: Bearer …`), API Gateway verifies it, and `auth.py` reads `sub` and `email` from the claims it passes on. `users.id` is the Cognito `sub`.
- Locally there is no API Gateway, and every request is one fixed development user.
- Either way, `auth.py` calls `identity.get_or_create_user`, so a user and a household of one are created on whichever request comes first.
- `household_id` always comes from here, never from a request body.

### Database transactions

A service function opens one transaction and passes the session on as the first argument, `s`, to everything it calls. It commits when the block ends and rolls back if anything inside raises:

```python
from app.db.session import transaction

with transaction() as s:
    record = ...                              # Role 5's tables
    change = apply_stock_event(s, user, ...)  # Role 2's inventory
```

Nothing connects until the first query, so code that never queries needs no database.

### Dates and times

Use `app.clock.today()` and `app.clock.now()`, never `date.today()` or `datetime.now()`. All dates are Singapore dates; Lambda runs in UTC, where it is still yesterday until 8 a.m. in Singapore.

### Environment variables

| Where | Variable | Meaning |
|---|---|---|
| backend | `DATABASE_URL` | Connection string; set by `docker-compose.yml` locally |
| backend | `DB_SECRET_ARN` | On AWS, instead of `DATABASE_URL`: the Secrets Manager secret with the database credentials |
| ai | `AI_PROVIDER` | Which model client to use; `fake` until a model is chosen |
| ai | `INGREDIENTS_CSV` | Path to the ingredient catalogue bundled with the `ai` Lambda |
| frontend | `VITE_API_URL` | The API Gateway URL; unset locally |
| frontend | `VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_CLIENT_ID` | From the Cognito user pool |
| frontend (dev) | `VITE_PROXY_TARGET`, `VITE_AI_PROXY_TARGET` | Where Vite forwards `/api` and `/ai` locally |

Never commit a value that is a secret. The repository is public.

### What is still fixed locally

- Without a Cognito token, every request is made as one development user (`app/auth.py`).
- When the backend runs on its own, without the ai service, `/ai/*` is answered by `app/services/ai_stub.py`, which always returns the same three items. `docker compose up` runs the real ai service instead, with its offline fake model.

### Decisions that differ from the preliminary report

- **Stock has four states**: `enough`, `low`, `out`, `unknown`. Countable ingredients carry a count instead.
- **Ratings happen only after cooking.** Before cooking there is "Not tonight" and "Cook this".
- **There are no prices and no budget.**
- **Images are never stored.** The browser compresses a photo and sends it in the request.
- **Suggestions carry no reason text.**
- **One deployed environment**, no separate production.

---

## What comes next

The work falls into four stages. Stages 1 to 3 are done; they are kept here as a record.

**1. Real data, locally.**
Role 5 writes the recipes, and from them Role 2 writes the ingredient catalogue, the tables and the seed loader. When this is done, `docker compose up` starts with a real catalogue and a demo kitchen, and the inventory endpoints read and write Postgres.

**2. A walking skeleton on AWS.**
Role 3 deploys the stack: network, database, the three Lambdas, API Gateway with Cognito, Amplify Hosting, and deployment from CI. Role 1 adds sign-in. When this is done, a merge to `main` reaches a public URL where a user can sign in and edit their kitchen.

**3. Real logic.**
Role 5 replaces the Cook and Shop stubs with the recommendation code. Role 4 replaces the fake model with a real one. When this is done, every screen on the deployed stack works on real data.

**4. Evaluation and the report.**
The load test and cost comparison (Role 3), the recommendation scenarios (Role 5), the image test set (Role 4), the user study (Role 1), the reliability tests (Role 2), and the final report.

Who waits for whom:

| Waiting | For | What |
|---|---|---|
| Role 2 | Role 5 | The recipes, to know which ingredients the catalogue needs |
| Role 4 | Role 2 | `ingredients.csv`, to match what the model reads |
| Role 5 | Role 2 | Real bodies for `apply_stock_event` and `get_inventory_snapshot`; the stubs work until then |
| Role 1 | Role 3 | The Cognito user pool, to add sign-in |
| everyone | Role 3 | The AWS account check: which services we can use |

## Open questions

| Question | Affects | Until then |
|---|---|---|
| Which AWS account, and what does it allow? | everyone | Develop against `docker compose up` |
| Which model provider? | Role 4 | The `ai` service uses a fake model |
| How does the `ai` Lambda get its model credentials? | Roles 3, 4 | Not needed while the model is fake |

## Working agreements

- `main` is protected. Branch as `<name>/<topic>`, open a pull request, one reviewer, checks green.
- The repository is public: no credentials, account details or course materials.
- Declare AI use; the final report needs where, how and what was learnt.
