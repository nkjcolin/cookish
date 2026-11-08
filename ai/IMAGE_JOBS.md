# Background image processing

Receipt and grocery uploads use short HTTP requests and a separate worker. The existing
/ai/parse-image, text, interpretation and audio routes remain available.
No PostgreSQL schema, inventory, recipe or migration changes are required.

## Request flow

1. The browser compresses the image, then sends POST /ai/image-jobs with the existing
   ParseImageRequest body and a UUID Idempotency-Key header.
2. The API validates it, records a job, saves its image, queues the job ID, and returns
   HTTP 202 with an ImageJobResponse. It does not call the model.
3. SQS invokes app.job_worker.handler in cookish-ai-worker. The worker loads the
   image and uses the existing receipt/photo prompt, model client and post-processing.
4. GET /ai/image-jobs/{job_id} returns queued, processing, completed or failed.
   A completed job includes the existing DraftResult, plus token/cost usage.
5. The browser polls every two seconds and opens ingredient review on completion.
   Nothing reaches inventory before the user's existing review/confirmation step.

The API Lambda still has its 27-second request cap. The worker bypasses the HTTP
middleware and has a separate 110-second application budget inside a 120-second Lambda,
with a 90-second provider HTTP timeout. Its budget also respects Lambda's remaining time.
Background processing does not speed up inference or guarantee every model call succeeds.

## Minimal local acceptance test

From ai/:

~~~sh
uv sync --frozen
uv run python scripts/test_image_jobs.py
~~~

This makes an actual 45-second fake-model call in a separate worker process. API calls
include Lambda-style context, retain the 27-second HTTP cap, and must each finish in
under five seconds. The test checks that polling works after 27 seconds, then receives
the completed draft. It uses temporary files and no school credentials, AWS resources
or production database. It is an ASGI/process test, not proof of deployed AWS behaviour.

The unit tests also check SDK adapters with in-process Moto mocks. No LocalStack,
SAM emulation stack or other complete local AWS simulation is needed.

## Run the frontend and local workers

For Docker, use the overlay from the repository root:

~~~sh
docker compose -f docker-compose.yml -f ai/compose.jobs.yaml up --build
~~~

This adds the separate local worker and defaults to fake inference. The original root
Compose file alone does not start a worker. For real school calls, explicitly select the
provider from ai/.env:

~~~sh
docker compose --env-file ai/.env \
  -f docker-compose.yml -f ai/compose.jobs.yaml up --build
~~~

The overlay injects ai/.env into the AI containers when present, but only the explicit
--env-file option (or exported AI_PROVIDER) selects its provider instead of the fake default.

Alternatively, run the services directly:

Use two terminals from ai/. Without --env-file .env, the fake provider is the default.

~~~sh
# Terminal 1: HTTP API, port 8001.
AI_JOB_BACKEND=local uv run --env-file .env uvicorn app.main:app --reload --port 8001

# Terminal 2: separate worker. The environment overrides a shorter timeout in .env.
AI_JOB_BACKEND=local SOCLAAS_TIMEOUT_SECONDS=90 \
  AI_WORKER_TIMEOUT_SECONDS=110 \
  uv run --env-file .env python -m app.job_worker
~~~

For real school calls, .env needs the existing AI_PROVIDER=soclaas, base URL,
model and API credential settings. The API does not need a provider call to accept a job.
Both processes default to the same ai/output/jobs/ SQLite/file store, ignored by Git.
Set AI_JOB_LOCAL_DIR identically in both processes if choosing another location.
--once processes the current pending jobs once and then exits.

From frontend/:

~~~sh
VITE_AI_PROXY_TARGET=http://localhost:8001 pnpm dev
~~~

The frontend must point /ai at this service, rather than the backend's contract-only
stand-ins. A pending job ID/kind is kept in session storage so returning to Add Ingredients
in the same tab resumes polling. Images and extraction results are not stored there.

The browser also keeps a bounded, tab-local photo preview in memory for the review
screen's enlarged preview. The router passes only its job ID, never photo bytes.
Confirming the draft releases the preview; reloading the page clears browser-memory
previews without preventing job-status recovery or ingredient review.

## Failure handling and retention

- API Gateway's verified Cognito sub owns the job. HTTP handlers never accept an owner
  from request JSON or a client-controlled header. Other users receive the same 404 as
  a nonexistent job. Local development uses one fixed owner; it is not an auth test.
- The same owner/key/image yields the same job. Reusing a key for different content fails
  with 409. A repeated submission repairs an interrupted upload/queue acknowledgement.
- Conditional leases prevent concurrent deliveries from committing twice. Stale workers
  cannot overwrite a newer attempt or a terminal result. Exactly-once model billing is
  not guaranteed if a worker dies after calling the provider but before saving its result.
- Model failures/deadlines allow at most three worker attempts. SQS's base visibility is
  720 seconds (six times the Lambda timeout); handled retryable failures shorten their
  visibility to 30 seconds. Unhandled delivery failures are redriven to a failed-job queue
  after five receives. Queue records contain job IDs, never image bytes.
- Unfinished jobs become failed when read after 15 minutes. Jobs/results expire after
  24 hours; status reads enforce expiry immediately even if DynamoDB TTL cleanup is late.
- Images are deleted after a committed completion/failure. S3's one-day lifecycle rule
  provides eventual cleanup for abandoned uploads or failed deletion attempts, rather
  than a promise that every object disappears at precisely 24 hours.
- Worker attempt logs omit image contents, prompts, credentials and extraction text.
  Job usage combines observed attempts; totals remain unknown when an attempt's usage
  is unavailable. Known token/cost subtotals are retained separately.
- Local cleanup runs in the worker loop. Stop both processes before deleting the local
  output/jobs/ directory if starting afresh.

## AWS rollout (not performed by implementing this feature)

infra/template.yaml adds private encrypted image storage, a pay-per-request job table,
encrypted SQS queues, the worker and its execution permissions. Worker concurrency is
limited to two; the shared account must have enough Lambda concurrency available.
Both AI functions remain outside the VPC and use the existing school API secret.

Before merging to main:

1. Check the shared-account permissions and available concurrency.
2. Take a manual PostgreSQL snapshot and review a CloudFormation change set. Require no
   RDS removal/replacement, credential rotation or unrelated network changes. The existing
   database resource has not been changed by this feature.
3. Confirm Amplify's independent auto-build is off so the workflow can release the new
   frontend after the API/resources are ready.
4. Ensure all CI checks pass. The current workflow runs backend migrations/seeding before
   deploying the stack, even for an AI-only change. This feature adds no migration.

After deploying, verify one real weekly grocery job, status ownership, worker logs,
terminal failure behaviour and existing inventory. A successful local test cannot verify
the account's real IAM/SCP permissions, SQS trigger, provider connectivity or Amplify build.
The existing workflow requests an Amplify build but does not wait for it to finish.

Do not manually upload worker/API ZIPs: deployment from main manages both handlers.
To roll back the frontend, restore the previous compatible frontend release while keeping
the new resources for outstanding jobs. Do not delete the image bucket while jobs run.
