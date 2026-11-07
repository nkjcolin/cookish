# Role 3 — Cloud platform, delivery and cost

You put Cookish on AWS and keep it there: the network, the database server, the Lambdas, API Gateway, sign-in, hosting, deployment from CI, monitoring, and what it all costs. Read [docs/init.md](../docs/init.md) first for the conventions everyone follows.

The design is in [SPEC.md](../docs/SPEC.md): **A3** for the architecture, **A4** for the technology choices, **B3** for your brief, including the load test and the on-premise cost comparison.

## What you own

| Path | Contents |
|---|---|
| `infra/` | The SAM template (`template.yaml`), its settings, packaging and deployment instructions |
| `.github/workflows/` | CI (exists) and deployment |
| `amplify.yml` | Amplify's build settings for `frontend/`, at the repository root |
| `eval/load/` | k6 load-test scripts |

## What already exists

The shared Cookish deployment is running in Singapore (`ap-southeast-1`).
The frontend is [Cookish](https://main.d146krzza1ana.amplifyapp.com/cook).
The deployed HTTP API is `https://cit4onmvhf.execute-api.ap-southeast-1.amazonaws.com`.

On 7 November 2026, PR #25 was merged as `2223e1f`. The tested source (`86ac258`)
was packaged for Python 3.12 / ARM64 and uploaded to `cookish-migrate`, then
`cookish-api`. Both console updates succeeded and reported the same package hash.
The migration returned revision `6f2c8d471a90`, with 42 ingredients, 48 recipes,
20 variants and 383 recipe ingredient lines. Existing handlers and configuration
were preserved. This release includes PR #24's persistent Cook/Shop integration.

The public gateway rejects unauthenticated API requests, including health checks,
and its CORS preflight permits the Amplify origin and required request headers.
These checks do not establish that authenticated Cook/Shop or AI flows work;
record their results separately. The AI function was not updated in this rollout.

| Verification | Result |
|---|---|
| PR #25 CI | Backend 575 tests passed; frontend and AI jobs passed |
| Backend code upload | Both migration and API succeeded |
| Migration and catalogue seed | Expected revision and all counts returned |
| Backend deployment automation | Still manual; CI currently only checks code |
| Load/elasticity evidence | Not collected yet |

The deployed entry points are:

| What | Where | Entry point |
|---|---|---|
| `api` Lambda | `backend/` | `app.lambda_handler.handler` |
| `ai` Lambda | `ai/` | `app.lambda_handler.handler` |
| `migrate` Lambda | `backend/` | `app.migrate.handler` |
| Frontend | `frontend/` | `pnpm build` produces `dist/` |

- `backend/` and `ai/` are separate Python 3.12 projects, each with its own `pyproject.toml` and `uv.lock`.
- The Dockerfiles in `backend/`, `ai/` and `frontend/` are for `docker compose` only, not for Lambda.
- `.github/workflows/ci.yml` lints and tests all three on every pull request. The backend job includes PostgreSQL and requires its database tests to run.

## Infrastructure design and checks

| Resource | Notes |
|---|---|
| VPC with two private subnets | Private subnets in two different Availability Zones. No NAT gateway. A Secrets Manager interface VPC endpoint is required if `api` and `migrate` retrieve `DB_SECRET_ARN` at runtime. |
| RDS PostgreSQL 16, `db.t4g.micro`, single-AZ | Credentials in Secrets Manager; security group allows only the `api` and `migrate` Lambdas on port 5432 |
| `api` Lambda | In the VPC; 512 MB to start |
| `ai` Lambda | **Outside** the VPC, so it can reach the model provider. The template sets a 120-second Lambda timeout; verify the request deadline stays within the HTTP API integration limit |
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
| `ai` | `AI_PROVIDER` | `soclaas` in the current template; `fake` is the local fallback |
| `ai` | `INGREDIENTS_CSV` | Path of the bundled `ingredients.csv` inside the package |

The template passes `SOCLAAS_API_KEY_SECRET_ARN` to the AI function and grants it read access to that secret. Keep provider keys in Secrets Manager. Verify live configuration and a real provider request separately.

### Migrations (Role 2)

RDS is in private subnets, so neither GitHub Actions nor a laptop can reach it. The `migrate` Lambda already runs inside the VPC. For a backend release, update its code first, invoke it with `{}`, and require the expected schema revision and catalogue counts before updating the API. It applies the migrations and seeds the production catalogue without a demo household. Do not start a new API release against an older schema.

## Things to plan for

- **Packaging.** `sam build` for Python reads `requirements.txt`, but the projects use uv. Generate it during the build, for example `uv export --no-dev --no-hashes > requirements.txt`, or package each Lambda as a container image.
- **The `ai` Lambda needs a file from `backend/`.** Copy `backend/seed/ingredients.csv` into the `ai` package during the build, and point `INGREDIENTS_CSV` at it.
- **Native dependencies.** Both backend functions use ARM64, Python 3.12 (Amazon Linux 2023). Package matching Linux wheels, never Windows virtual-environment files. See [deployment.md](deployment.md) for the reproducible backend ZIP build and rollout checks.
- **No long-lived AWS keys in GitHub.** Deploy with a GitHub OIDC role.
- **Secrets Manager networking.** `api` and `migrate` run in private subnets and read `DB_SECRET_ARN` at runtime. Without a NAT gateway, the VPC therefore needs an interface endpoint for Secrets Manager (`com.amazonaws.ap-southeast-1.secretsmanager`). Include its fixed cost in the cloud cost model.

## Remaining work

1. Complete authenticated browser smoke tests on a dedicated test household, including stock confirmation, replay and feedback. Record actual results and any product gaps.
2. Add deployment automation after checking the existing stack and the permissions available for GitHub OIDC. Packaging is separate from a verified automatic rollout.
3. Verify the live CloudWatch dashboard, alarms and budget alert. Add concurrency and database metrics needed to assess load; a JSON dashboard file alone is not evidence of a deployed dashboard.
4. Run the bounded load test in [eval/load](../eval/load/) beyond 20 users. Correlate the run with Lambda concurrency and errors, API latency and database load; user count alone does not prove scale-out.
5. Fill in the cloud versus on-premise comparison using measured inputs, including ARM64 Lambda pricing and the Secrets Manager endpoint.

**Done when** a merge to `main` reaches the deployed stack without manual steps, the dashboard shows live traffic, and the cost model is filled in with measured values.

## Account check

Wenlong's NUS SSO account can access the existing shared account and has now
successfully updated both backend functions and invoked the migration. A zero
count under “My Leases” in Innovation Sandbox does not imply no account access.
Use NUS MyApps → AWSNLZ → the assigned shared account; do not request a duplicate lease.
Permissions not exercised below remain unverified.

| Question | Answer |
|---|---|
| Account type | NUS shared Innovation Sandbox account |
| Can we create IAM roles? | Not tested during this rollout |
| Cognito, Amplify, API Gateway, RDS in `ap-southeast-1` | Existing deployment; database migration and catalogue seed succeeded |
| Bedrock, and which models | Not tested; the current template uses SOCLaaS |
