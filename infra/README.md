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
PR #26 (`b5b78fc`, tested source `c55ff3b`) was subsequently merged and deployed
to the API and Amplify frontend. Live checks passed for onboarding, the
empty-kitchen recipe preview, canonical egg inventory, a 300 g tofu purchase,
reload persistence, cooking/stock deduction, Maybe feedback and undo. Test stock
was cleaned up afterward. Typed AI parsing was exercised; the AI function itself
was not updated in this rollout.

| Verification | Result |
|---|---|
| PR #26 CI | Backend 606 tests and frontend 38 tests passed; AI job passed |
| Backend code upload | Both migration and API succeeded |
| Migration and catalogue seed | Expected revision and all counts returned |
| Deployment automation | Existing `deploy` job in CI passed on main `13c833f`; see [recorded result and limits](deployment.md) |
| Live core flow | Recipe preview, purchase persistence, stock deduction, feedback and undo verified |
| Monitoring | [cookish-ops](monitoring.md) has 12 widgets; both error alarms have enabled SNS actions and a confirmed email subscription. Actual alarm delivery remains untested |
| Load evidence | 50-VU authenticated read test completed: 10,200 workload GETs, zero client errors; API concurrency rose from 1 to 6 and returned to 1. This does not test independent-household transactions or AI |

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
| CloudWatch | Live dashboard and two error alarms verified; enabled actions target `cookish-api-alerts`, whose email subscription is confirmed |
| AWS Budgets | Both $20/$40 monthly budgets cover the whole account and alert on actual cost >100%. Approved recipient added to both, existing recipient retained; new recipient verification is blocked by missing `notifications-contacts` permissions |

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

## Automatic deployment

Every push to `main` whose CI checks pass runs the `deploy` job in [ci.yml](../.github/workflows/ci.yml), in the rollout order of [deployment.md](deployment.md): `sam build`; give `cookish-migrate` the new code and invoke it (migrations and seed); only then `sam deploy`, which updates the API, the AI function and the rest of the stack; finally, if configured, start the Amplify build. A failed migration stops the job before the API changes, with the Lambda's log in the job output.

### One-time setup

1. **Create the deploy role.** CloudFormation console, `ap-southeast-1` → Create stack → upload [github-deploy-role.yaml](github-deploy-role.yaml). Name it e.g. `github-deploy`. Set `AppStackName` to the name of the stack `template.yaml` is already deployed as: `cookish`. If IAM → Identity providers already lists `token.actions.githubusercontent.com`, paste its ARN into `ExistingOidcProviderArn`. Tick the IAM acknowledgement and create. Copy the `DeployRoleArn` output.
2. **Tell GitHub.** Repository → Settings → Environments → `aws` → **Environment variables** (not secrets, and not repository variables: the job runs in the `aws` environment):

   | Variable | Value |
   |---|---|
   | `AWS_DEPLOY_ROLE_ARN` | The `DeployRoleArn` output |
   | `SAM_STACK_NAME` | `cookish` |
   | `AMPLIFY_APP_ID` | Optional: `d146krzza1ana` |

3. **Optional: order the frontend after the API.** Amplify builds on its own the moment `main` changes, even when tests fail, and can go live before the API it calls. To prevent that, turn off Amplify → the app → `main` → *Auto build*, and set `AMPLIFY_APP_ID`: the deploy job then starts the Amplify build after the database is migrated.

The role can only be taken by jobs in this repository's `aws` environment. To keep other branches out, limit that environment's *Deployment branches* to `main`. GitHub names the repository by its numeric IDs in OIDC tokens when immutable subjects are on, so the template trusts both forms. The ARNs are not secret.

To change the role later: CloudFormation → the `github-deploy` stack → Update → *Replace existing template* → upload the new file, keeping the parameters.

### Deploying by hand

Follow [deployment.md](deployment.md). Code uploaded by hand is replaced by the next automatic deploy from `main`.

## Things to plan for

- **Packaging.** `sam build` for Python reads `requirements.txt`, but the projects use uv. Generate it during the build, for example `uv export --no-dev --no-hashes > requirements.txt`, or package each Lambda as a container image.
- **The `ai` Lambda needs a file from `backend/`.** Copy `backend/seed/ingredients.csv` into the `ai` package during the build, and point `INGREDIENTS_CSV` at it.
- **Native dependencies.** Both backend functions use ARM64, Python 3.12 (Amazon Linux 2023). Package matching Linux wheels, never Windows virtual-environment files. See [deployment.md](deployment.md) for the reproducible backend ZIP build and rollout checks.
- **No long-lived AWS keys in GitHub.** Deploy with a GitHub OIDC role.
- **Secrets Manager networking.** `api` and `migrate` run in private subnets and read `DB_SECRET_ARN` at runtime. Without a NAT gateway, the VPC therefore needs an interface endpoint for Secrets Manager (`com.amazonaws.ap-southeast-1.secretsmanager`). Include its fixed cost in the cloud cost model.

## Remaining work

1. Extend the verified core browser flow with any remaining replay and failure-path checks. General grams-to-pieces conversion, independent held-out evaluation and AI outage behavior remain separate gaps.
2. Keep checking the current main CI deployment and final Amplify build result; [deployment.md](deployment.md) distinguishes the successful SAM run from manual backup, hash and revision safeguards that are not automated.
3. Verify actual alarm notification delivery. The school role was denied permission to send the new budget recipient's verification email; a school account administrator must resolve or complete verification (see [monitoring](monitoring.md)). Both account-wide budget alerts are configured, but budget delivery is untested. Both error alarms already target a confirmed SNS email subscription.
4. Preserve the [completed 50-VU read-test evidence](../eval/load/results/2026-11-07-read-only-50-vus.md) and its workload limits. Independent-household recommendation/write load and the longer soak test remain; see [eval/load](../eval/load/).
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
