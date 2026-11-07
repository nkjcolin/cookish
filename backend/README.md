# backend

FastAPI service behind the `api` Lambda.

## Run it

Requires [uv](https://docs.astral.sh/uv/). uv installs the pinned Python version (3.12) for you.

```bash
uv sync                                   # install dependencies into .venv
uv run uvicorn app.main:app --reload      # http://localhost:8000/api/docs
uv run pytest                             # tests
uv run ruff check . && uv run ruff format --check .
```

## The contract file

`docs/openapi.json` is generated from `app/schemas/` and `app/routers/`. The frontend's
typed client is generated from it, so it is committed and must stay current: the test
suite fails when it is not.

```bash
uv run python scripts/export_openapi.py
```

## Layout

| Path | Owner | Contents |
|---|---|---|
| `app/main.py` | Role 1 | App factory and router registration |
| `app/errors.py` | Role 1 | The one error format every endpoint returns |
| `app/auth.py` | Role 1 | Who is calling: Cognito claims on AWS, a fixed development user locally |
| `app/clock.py` | Role 1 | Today's date in Singapore; use it instead of `date.today()` |
| `app/mock.py` | Role 1 | The development user's ID, the demo seed and `ai_stub.py`'s sample items; no endpoint serves it on AWS |
| `app/lambda_handler.py` | Role 3 | Lambda entry point (`app.lambda_handler.handler`) |
| `app/schemas/` | Role 1, reviewed by all | Pydantic models — the API contract |
| `app/routers/` | Role 1 | Thin HTTP handlers; no business logic |
| `app/services/` | Roles 2 and 5 | Business logic called by the routers |
| `app/reco/` | Role 5 | Pure recommendation functions, no database imports |
| `app/db/` | Role 2 | `session.py` (`transaction()`), models, repositories |
| `migrations/` | Role 2 | Alembic migrations |
| `seed/` | Roles 2 and 5 | `ingredients.csv`, `recipes/*.yaml`, loader |
| `tests/` | everyone | pytest |

## Changing a service

Every endpoint is backed by real logic in `app/services/`: `identity.py`, `catalogue.py`,
`inventory.py` and `stock_events.py` (Role 2); `cook.py` and `shop.py` (Role 5).

1. Keep each function's name, parameters and return type: the routers and the frontend
   depend on them.
2. Do not edit `app/routers/` or `app/schemas/`. If the contract has to change, raise it
   with Role 1 first, because it changes the generated frontend types.
3. `tests/test_contract.py` calls every endpoint. It must still pass.

`app/services/ai_stub.py` is only a local stand-in for the `ai` service, used when the
backend runs without it; on AWS and in `docker compose`, `/ai/*` goes to the real one.

Requests that change inventory must carry an `Idempotency-Key` header (a UUID). The
caller's identity comes from `app/auth.py`; locally it is always one development user.

The conventions every service follows (transactions, dates, who is calling) are in
[docs/init.md](../docs/init.md). What each role owns, and the functions roles call across
each other, are in the role READMEs: [app/db/README.md](app/db/README.md) for Role 2 and
[app/reco/README.md](app/reco/README.md) for Role 5.

## Errors

Raise `ApiError` from a service; never build an error response by hand.

```python
from app.errors import ApiError, ErrorCode

raise ApiError(ErrorCode.STALE_REVISION, "Item was changed elsewhere", {"revision": 4})
```

Every failure — including validation errors, unknown routes and unexpected exceptions — reaches the client as:

```json
{"error": {"code": "STALE_REVISION", "message": "Item was changed elsewhere", "details": {"revision": 4}}}
```

| Code | HTTP status |
|---|---|
| `VALIDATION` | 422 |
| `UNAUTHENTICATED` | 401 |
| `FORBIDDEN` | 403 |
| `NOT_FOUND` | 404 |
| `STALE_REVISION`, `CONFLICT` | 409 |
| `NO_RESULT` | 404 |
| `UPSTREAM_UNAVAILABLE` | 503 |
| `INTERNAL` | 500 |
