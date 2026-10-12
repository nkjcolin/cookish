# Cookish

A cloud service that helps people decide what to buy and what to cook. CS5224 Cloud Computing group project, Group 11.

Cookish keeps a low-maintenance record of what is in your kitchen and answers two questions: *what should I cook?* and *what should I buy?*

## Status

Project skeleton. The development specification is in [docs/SPEC.md](docs/SPEC.md); read Part A, then the brief for your role in Part B.

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

Setup instructions are added as each part is created.
