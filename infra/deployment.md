# Backend Lambda packaging and rollout

## Automatic backend deployment

[Deploy backend](../.github/workflows/deploy-backend.yml) deploys the current
`main` commit after its CI run succeeds. It checks that the backend, AI and
frontend jobs all passed, then builds the exact tested commit for Python 3.12
and ARM64. Older commits are skipped. Deployments run one at a time; a newer
commit does not cancel a migration already in progress.

The workflow reuses the existing GitHub OIDC provider and role in account
`534444203105`. Repository variable `COOKISH_BACKEND_DEPLOY_ROLE_ARN` is set to
`arn:aws:iam::534444203105:role/github-actions-deploy-cookish`. Its trust allows
only `nkjcolin/cookish` on `main`, with audience `sts.amazonaws.com`. No stored
AWS access keys are needed. The workflow further limits its temporary session
to reading, updating code and invoking `cookish-api` and `cookish-migrate` in
Singapore. It does not change their configuration or deploy the AI/frontend.

Before changing AWS, the job saves both existing ZIPs, verifies their hashes and
records configuration hashes without saving environment values. Each update
uses the observed Lambda `RevisionId`, so an intervening code or configuration
change causes it to stop. It updates and invokes migrate first, requiring the
exact schema revision and all four catalogue counts from the tested source.
Only then does it update the API and invoke `/api/health`. Both deployed ZIP
hashes and unchanged configuration are checked. The health probe checks Lambda
runtime and routing; authenticated browser/Cognito/CORS checks remain separate.

Open **GitHub Actions → Deploy backend** to inspect the result. Each run keeps
three artifact groups for 14 days: the new package/manifest, the previous code
ZIPs, and verified migration/deployment results. A successful workflow result,
including `deployment.json`, is the evidence that the release completed.

To retry after investigating a failure, choose **Run workflow → main**. This
still requires passing CI for the current main commit; it cannot deploy an
arbitrary ref or bypass checks. Removing the role-ARN repository variable
disables future deployment jobs. Rollback is deliberate: use a verified previous
ZIP and the function's current revision, and assess schema compatibility first.
Restoring code does not undo a completed database migration.

## Build a package locally

Use Python 3.12, Git and [uv](https://docs.astral.sh/uv/getting-started/installation/).
From the repository root:

```sh
python infra/build_backend_lambda.py --source-ref HEAD --architecture arm64
```

On Windows, `backend/.venv/Scripts/python.exe` can replace `python`. If uv is not
on PATH, pass `--uv` followed by its executable path. Use `--architecture x86_64`
only for a function configured with that architecture.

The script reads committed files and the lockfile from the selected Git ref;
uncommitted edits are excluded. It exports production requirements with hashes,
downloads matching Linux wheels, and packages the API, migrations, ingredient
catalogue and recipe files. It does not include the demo household seed. Both
architectures target manylinux 2.28, which fits Python 3.12's Amazon Linux 2023
runtime (glibc 2.34). The locked psycopg ARM64 wheel requires at least glibc 2.27.

Outputs go to ignored `.aws-sam/backend-release/`: a ZIP, a JSON manifest with the
commit, dependency versions and SHA256, and the exported requirements. Choose
another directory under `.aws-sam/` or `private/` with `--output-dir` for another
build of the same commit. Existing release files are never overwritten. The
builder checks Python syntax, ELF architecture and ZIP integrity; it cannot run
Linux native extensions on a Windows host. Boto3 continues to come from Lambda's
runtime, as expected by `app/db/session.py`.

## Manual rollout order

1. Confirm the target account, region, runtime and architecture. Save the current
   function code and configuration for rollback. Preserve each function's handler,
   IAM role, environment variables, VPC settings and layers.
2. Update `cookish-migrate` with the matching ZIP, then invoke its existing
   `app.migrate.handler` with `{}`. Check that the returned revision matches the
   manifest's `migration_head`, and that ingredient and recipe counts match.
3. Only after migration succeeds, update `cookish-api` with the matching ZIP. Keep
   its `app.lambda_handler.handler` entry point. Check authenticated Cook and Shop
   requests and CloudWatch errors.

The migration seeds catalogue records by their fixed IDs and does not create a
demo household. Schema changes still need their own rollback assessment; restoring
the previous ZIP does not undo a migration. This builder does not sign in to AWS,
upload code, or change cloud configuration.

On 7 November 2026, the ARM64 package built from `86ac258` was deployed to both
functions. Its SHA256 was
`75eb15c14487e51e937006719742d6a060903f8d0310ce4310a3bdb902359bcc`.
The migration completed at `6f2c8d471a90` with 42 ingredients and 48 recipes. That
package predates this script; new ZIP hashes differ because archive metadata and
the embedded build manifest are now generated consistently by the script.

References: [Lambda Python ZIP packages](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html),
[Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html),
[Amazon Linux 2023 glibc](https://docs.aws.amazon.com/linux/al2023/ug/glibc-gcc-and-binutils.html).
