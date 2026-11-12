# Cookish

A cloud service that helps people decide what to buy and what to cook. CS5224 Cloud Computing group project, Group 11.

Cookish keeps a low-maintenance record of what is in your kitchen and answers two questions: *what should I cook?* and *what should I buy?*

## Status

Every screen runs on real data and is deployed at <https://main.d146krzza1ana.amplifyapp.com>; every push to `main` that passes CI deploys automatically ([infra/README.md](infra/README.md)). **Start with [docs/init.md](docs/init.md)**: it says where the project stands, the conventions everyone follows and what comes next, and points each role to the README in the folder they work in. The design decisions are in [docs/SPEC.md](docs/SPEC.md).

## Repository layout

| Path | Purpose and important files |
|---|---|
| `frontend/` | React pages and typed API client. src/pages/ holds Cook, Buy, Kitchen and review flows; src/api/schema.d.ts is generated from OpenAPI.|
| `backend/app` | main.py registers FastAPI routers; auth.py resolves the caller; services/ holds inventory and workflow logic; db/models.py and db/session.py define persistence.|
| `backend/app/reco` | Pure Cook and Shop algorithms, inventory assessment, scoring configuration and replaceable preference learning. |
| `ai/` | Separate FastAPI AI app; app/main.py, model_client.py, receipts.py, photos.py, prompts/ and runtime.py handle parsing, validation and deadlines. |
| `eval/ and docs/` | Recommendation fixtures and results, reproducible cost model, specification, handoffs and generated docs/openapi.json.|
| `infra/ and .github/` | GitHub Actions uses OpenID Connect (OIDC) to assume a restricted AWS IAM deployment role without storing long-lived AWS access keys. The workflow builds the SAM application, runs the migration step and deploys the application stack using sam deploy. |

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
| AI service docs | http://localhost:8001/ai/docs |
| Postgres | `postgres://cookish:cookish@localhost:5432/cookish` |

Edits to `frontend/`, `backend/` and `ai/` reload automatically. To work on one part, run it directly on your machine and keep the rest in Docker; see [frontend/README.md](frontend/README.md), [backend/README.md](backend/README.md) and [ai/README.md](ai/README.md).

Your local database is yours alone. `docker compose down -v` wipes it and the next start gives you a clean one.

The API contract is [docs/openapi.json](docs/openapi.json). Locally every request is made as one fixed development user, so no sign-in is needed.
