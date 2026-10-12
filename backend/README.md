# backend

FastAPI service behind the `api` Lambda. Set up in the next step.

| Path | Owner | Contents |
|---|---|---|
| `app/schemas/` | Role 1, reviewed by all | Pydantic models — the API contract |
| `app/routers/` | Role 1 | Thin HTTP handlers; no business logic |
| `app/services/` | Roles 2 and 5 | Business logic called by the routers |
| `app/reco/` | Role 5 | Pure recommendation functions, no database imports |
| `app/db/` | Role 2 | Models, session, repositories |
| `migrations/` | Role 2 | Alembic migrations |
| `seed/` | Roles 2 and 5 | `ingredients.csv`, `recipes/*.yaml`, loader |
| `tests/` | everyone | pytest |
