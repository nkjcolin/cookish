# Cookish

A cloud service that helps people decide what to buy and what to cook. CS5224 Cloud Computing group project, Group 11.

Cookish keeps a low-maintenance record of what is in your kitchen and answers two questions: *what should I cook?* and *what should I buy?*

## Status

The contract, the stubs and the whole frontend are in place; the backend still returns sample data. **Start with [docs/init.md](docs/init.md)**: it says where the project stands and what each role does next. The design decisions are in [docs/SPEC.md](docs/SPEC.md).

## Repository layout

| Path | Contents | Owner |
|---|---|---|
| `frontend/` | React web app | Role 1 |
| `backend/` | FastAPI service: API contract, inventory, Cook and Shop | Roles 1, 2, 5 |
| `ai/` | Receipt, photo and text parsing | Role 4 |
| `infra/` | AWS SAM template and deployment | Role 3 |
| `eval/` | Load tests, recommendation scenarios, image test set, user study | all |
| `docs/` | Specification, generated OpenAPI file, diagrams | all |

## Working agreements

- `main` is protected. Work on a short-lived branch and open a pull request; one reviewer, checks must pass.
- This repository is public. Never commit credentials, account details, participant data or course materials.
- AI assistance is allowed and must be declared in the final report.

## Run it locally

With Docker, one command starts everything:

```bash
docker compose up
```

| Service | Address |
|---|---|
| Web app | http://localhost:5173 |
| API and interactive docs | http://localhost:8000/api/docs |
| Postgres | `postgres://cookish:cookish@localhost:5432/cookish` |

Edits to `frontend/` and `backend/` reload automatically. To work on one part, run it directly on your machine and keep the rest in Docker; see [frontend/README.md](frontend/README.md) and [backend/README.md](backend/README.md).

Your local database is yours alone. `docker compose down -v` wipes it and the next start gives you a clean one.

Every endpoint currently returns fixed sample data. The API contract is [docs/openapi.json](docs/openapi.json); how to replace a stub with real logic is described in [backend/README.md](backend/README.md).
