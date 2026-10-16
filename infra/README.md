# Role 3 — Cloud platform, delivery and cost

You put Cookish on AWS and keep it there: the network, the database server, the Lambdas, API Gateway, sign-in, hosting, deployment from CI, monitoring, and what it all costs. Read [docs/init.md](../docs/init.md) first for the conventions everyone follows.

The design is in [SPEC.md](../docs/SPEC.md): **A3** for the architecture, **A4** for the technology choices, **B3** for your brief, including the load test and the on-premise cost comparison.

## What you own

| Path | Contents |
|---|---|
| `infra/` | The SAM template (`template.yaml`), its settings, build and deployment scripts (empty) |
| `.github/workflows/` | CI (exists) and deployment |
| `amplify.yml` | Amplify's build settings for `frontend/`, at the repository root |
| `eval/load/` | k6 load-test scripts |

## What already exists

Nothing is deployed. What you will deploy is ready:

| What | Where | Entry point |
|---|---|---|
| `api` Lambda | `backend/` | `app.lambda_handler.handler` |
| `ai` Lambda | `ai/` | `app.lambda_handler.handler` |
| `migrate` Lambda | `backend/` | `app.migrate.handler` (Role 2 writes it) |
| Frontend | `frontend/` | `pnpm build` produces `dist/` |

- `backend/` and `ai/` are separate Python 3.12 projects, each with its own `pyproject.toml` and `uv.lock`.
- The Dockerfiles in `backend/`, `ai/` and `frontend/` are for `docker compose` only, not for Lambda.
- `.github/workflows/ci.yml` lints and tests all three on every pull request. It has not run yet.

## The stack to build

| Resource | Notes |
|---|---|
| VPC with two private subnets | No NAT gateway and no VPC endpoints: nothing in the VPC needs the internet |
| RDS PostgreSQL 16, `db.t4g.micro`, single-AZ | Credentials in Secrets Manager; security group allows only the `api` and `migrate` Lambdas on port 5432 |
| `api` Lambda | In the VPC; 512 MB to start |
| `ai` Lambda | **Outside** the VPC, so it can reach the model provider; 29-second timeout, because API Gateway stops at 30 |
| `migrate` Lambda | In the VPC; invoked once after every deployment |
| HTTP API | `/api/{proxy+}` to `api`, `/ai/{proxy+}` to `ai`; Cognito JWT authorizer on both; CORS from the Amplify domain only; throttling |
| Cognito user pool and app client | Email and password, email verification |
| Amplify Hosting | Connected to the repository, builds `frontend/`, rewrites every non-file path to `/index.html` |
| CloudWatch | Dashboard and alarms (SPEC B3, Observability) |
| AWS Budgets | An alert that reaches the whole group |

## What other roles expect from you

### Sign-in (Roles 1 and 2)

The frontend sends the Cognito **ID token** as `Authorization: Bearer …`. Configure the HTTP API's JWT authorizer to accept it: issuer is the user pool, audience is the app client ID. API Gateway passes the verified claims to the Lambda, where `backend/app/auth.py` reads `sub` and `email`. Give Role 1 the user pool ID and the app client ID.

### The frontend's address (Role 1)

Amplify and API Gateway have different domains. The frontend is built with `VITE_API_URL` set to the API Gateway URL, and calls it directly, so the HTTP API must allow CORS from the Amplify domain, including the `Authorization` and `Idempotency-Key` headers. Set these in Amplify's build environment:

| Variable | Value |
|---|---|
| `VITE_API_URL` | The HTTP API's URL |
| `VITE_COGNITO_USER_POOL_ID` | The user pool ID |
| `VITE_COGNITO_CLIENT_ID` | The app client ID |

### Lambda configuration (Roles 2 and 4)

| Lambda | Variable | Value |
|---|---|---|
| `api`, `migrate` | `DB_SECRET_ARN` | The Secrets Manager secret holding the database credentials. Grant read access to it |
| `ai` | `AI_PROVIDER` | `fake` until Role 4 chooses a model |
| `ai` | `INGREDIENTS_CSV` | Path of the bundled `ingredients.csv` inside the package |

How the `ai` Lambda gets its model credentials is not decided yet; it is not needed while the model is fake.

### Migrations (Role 2)

RDS is in private subnets, so neither GitHub Actions nor a laptop can reach it. Deploy the `migrate` Lambda in the VPC with the backend's code, and have the deployment job invoke it once after every `sam deploy`. It applies the migrations and loads the seed data.

## Things to plan for

- **Packaging.** `sam build` for Python reads `requirements.txt`, but the projects use uv. Generate it during the build, for example `uv export --no-dev --no-hashes > requirements.txt`, or package each Lambda as a container image.
- **The `ai` Lambda needs a file from `backend/`.** Copy `backend/seed/ingredients.csv` into the `ai` package during the build, and point `INGREDIENTS_CSV` at it.
- **Native dependencies.** The backend uses `psycopg[binary]`; build on Linux (`sam build --use-container`) so the right wheels are packaged.
- **No long-lived AWS keys in GitHub.** Deploy with a GitHub OIDC role.

## Tasks, in order

1. **Check the AWS account.** Can it create IAM roles? Are Cognito, Amplify, API Gateway, RDS and Bedrock available in `ap-southeast-1`? Write the answers below and tell the group: every other choice depends on them. If it is a restricted Learner Lab account, SPEC B3 lists the fallbacks.
2. The SAM template for the walking skeleton: VPC, RDS, the three Lambdas, the HTTP API with the Cognito authorizer.
3. Cognito user pool and app client; give the IDs to Role 1.
4. Amplify Hosting for `frontend/`, with the rewrite rule and environment variables above.
5. A deployment job in `.github/workflows/` on merge to `main`: build, `sam deploy` with OIDC, then invoke `migrate`. Add a Postgres service to CI for Role 2's tests.
6. CloudWatch dashboard and alarms; AWS Budgets alert.
7. Later: the k6 load test in `eval/load/`, and the on-premise versus cloud cost comparison.

**Done when** a merge to `main` reaches the deployed stack without manual steps, the dashboard shows live traffic, and the cost model is filled in with measured values.

## Account check

*To fill in after task 1.*

| Question | Answer |
|---|---|
| Account type | |
| Can we create IAM roles? | |
| Cognito, Amplify, API Gateway, RDS in `ap-southeast-1` | |
| Bedrock, and which models | |
