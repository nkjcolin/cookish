# Backend Lambda packaging and rollout

## Automatic deployment

The `deploy` job in [ci.yml](../.github/workflows/ci.yml) runs after the backend,
AI and frontend checks pass for a push to `main`. It uses an ARM64 runner and the
GitHub `aws` environment. Its OIDC subject is the repository's `environment:aws`
subject, including the immutable repository-ID form; it is not a branch-subject
role. The existing environment variables are:

| Variable | Value |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::534444203105:role/github-actions-deploy-cookish` |
| `SAM_STACK_NAME` | `cookish` |
| `AMPLIFY_APP_ID` | `d146krzza1ana` |

The job exports the frozen dependencies and runs `sam build`. It updates `cookish-migrate`, waits for that update,
and invokes migrations/seeding. A Lambda `FunctionError` stops deployment. After
that, `sam deploy` updates the existing stack, including API, AI and infrastructure.
Finally it requests an Amplify build when `AMPLIFY_APP_ID` is configured. Starting
that build is not evidence that the frontend build finished successfully.

[Main CI run 42348319904, attempt 2](https://github.com/nkjcolin/cookish/actions/runs/42348319904)
succeeded for commit `13c833f` on 7 November 2026. Backend tests passed 606 cases;
frontend tests passed 38. Its deployment returned revision `6f2c8d471a90` and
seed counts 42 ingredients, 48 recipes, 20 variants and 383 ingredient lines,
then reported a successful `cookish` stack update and requested the frontend build.

Deployments are serialized without cancelling an active job. To retry, inspect
the current main commit's **CI** run and rerun its failed jobs after resolving the
failure. Rerunning an old push can redeploy that older commit: the workflow does
not have a latest-main-SHA guard. It also does not currently save code backups,
assert the exact migration counts, compare ZIP hashes or protect updates with
Lambda `RevisionId`. Those are manual checks below, not completed automation.
Review SAM changes before merging infrastructure edits; this job can change the
stack configuration as well as code. No second deployment pipeline is installed.

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

During an earlier manual rollout on 7 November 2026, the ARM64 package built from `86ac258` was deployed to both
functions. Its SHA256 was
`75eb15c14487e51e937006719742d6a060903f8d0310ce4310a3bdb902359bcc`.
The migration completed at `6f2c8d471a90` with 42 ingredients and 48 recipes. That
package predates this script; new ZIP hashes differ because archive metadata and
the embedded build manifest are now generated consistently by the script.

References: [Lambda Python ZIP packages](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html),
[Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html),
[Amazon Linux 2023 glibc](https://docs.aws.amazon.com/linux/al2023/ug/glibc-gcc-and-binutils.html).
