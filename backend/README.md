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

## Layout

| Path | Owner | Contents |
|---|---|---|
| `app/main.py` | Role 1 | App factory and router registration |
| `app/errors.py` | Role 1 | The one error format every endpoint returns |
| `app/lambda_handler.py` | Role 3 | Lambda entry point (`app.lambda_handler.handler`) |
| `app/schemas/` | Role 1, reviewed by all | Pydantic models — the API contract |
| `app/routers/` | Role 1 | Thin HTTP handlers; no business logic |
| `app/services/` | Roles 2 and 5 | Business logic called by the routers |
| `app/reco/` | Role 5 | Pure recommendation functions, no database imports |
| `app/db/` | Role 2 | Models, session, repositories |
| `migrations/` | Role 2 | Alembic migrations |
| `seed/` | Roles 2 and 5 | `ingredients.csv`, `recipes/*.yaml`, loader |
| `tests/` | everyone | pytest |

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
