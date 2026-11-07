# Cook/Shop load preparation

`sessions.js` exercises the deployed, JWT-authenticated HTTP API. It has not been
run against AWS, and this folder contains no measured elasticity result.

The default is a 20-second, one-user smoke test. The `elasticity` profile goes
beyond the specification's original 20 users: 5 baseline VUs, 25 intermediate
VUs, then 50 peak VUs, followed by recovery. A virtual user (VU) runs requests
sequentially, with a pause between workflows. Fifty VUs or fifty saved sessions
does **not** mean fifty concurrent Lambda invocations. CloudWatch must show the
actual change in concurrent executions before the report can claim scale-out.

## Read-only test with one signed-in household

`read_only_smoke` and `read_only_elasticity` need only one existing test account.
Every VU reads `/api/inventory` and the same canonical recipe details. The latter
uses the fixed catalogue ID for **Tomato and egg rice bowls**
(`645a8d38-bfae-47f2-b00e-3ca6828a964e`), verified during preflight. Override
`READ_RECIPE_ID` with another seeded UUID if needed. These profiles enforce GET
requests only: they do not create Cook/Shop sessions or submit any writes.

Use an account that has already signed in and completed onboarding. Cookish's
authentication layer can bootstrap a household on an account's first-ever API
call, even for GET requests. The read-only test is intended for the already
established household, not account creation. Its inventory can be empty.

The read-only elasticity schedule is also **5 → 25 → 50 → 5 VUs**, over 400
seconds. It can demonstrate Lambda concurrency increasing for authenticated
reads, when supported by CloudWatch evidence. It **does not demonstrate
multi-household transaction scalability, Cook/Shop ranking latency, inventory
write performance or sign-in throughput**. All VUs deliberately use one user's
token and the same recipe; report that workload explicitly.

Install k6 using the official instructions below. From the repo root, pass a
fresh Cognito ID token through the temporary process environment. A sign-in
helper can populate `COOKISH_ID_TOKEN` directly, avoiding a token file. For
manual entry, the following prompt hides the token and keeps it out of command
history:

```powershell
$env:BASE_URL = 'https://YOUR_HTTP_API_ID.execute-api.ap-southeast-1.amazonaws.com'
$secureIdToken = Read-Host 'Fresh Cognito ID token for the existing test account' -AsSecureString
$env:COOKISH_ID_TOKEN = [System.Net.NetworkCredential]::new('', $secureIdToken).Password
try {
  $env:PROFILE = 'read_only_smoke'
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $env:RESULT_PREFIX = "private/load-$stamp-read-smoke"
  k6 run eval/load/sessions.js
  if ($LASTEXITCODE -ne 0) { throw 'Read smoke failed; do not increase load.' }

  $env:PROFILE = 'read_only_elasticity'
  $env:PEAK_VUS = '50'
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $env:RESULT_PREFIX = "private/load-$stamp-read-elasticity"
  k6 run --out "json=$env:RESULT_PREFIX-points.json" eval/load/sessions.js
  Write-Output "k6 exit: $LASTEXITCODE"
} finally {
  Remove-Item Env:COOKISH_ID_TOKEN -ErrorAction SilentlyContinue
  $secureIdToken.Dispose()
}
```

The ignored `private/` output directory must exist. Inspect Lambda/RDS capacity
and watch CloudWatch during the ramp, as described below. There is a 2-second
p95 target for each read route, a 6,000-loop default cap, bounded duration and
immediate abort on request errors. Each loop makes two GETs; preflight makes two
more. No stock change or model call is needed to run this profile.

## Workload and fixtures

The original `smoke`, `elasticity` and `contention` profiles exercise the
recommendation workflow. Each VU creates one Cook session and one Shop session,
then reuses them. A loop
reads inventory, applies a `less_oil` tag, changes portions and restores them,
reads recipe details, and adjusts the Shop plan. The tag request has its own p95
target of 2 seconds. Percentiles for each route and each stable phase are saved.

There are no AI calls, inventory additions, purchases, Cook confirmations, stars,
ratings or deletes. The run still writes sessions, suggestions, baskets and
remembered portion settings. Use designated test households. Shop adjustments
can create additional basket records; account for these in cleanup planning.
No automatic cleanup is performed.

This is a bounded recommendation-path test. It does not replace the SPEC B3
full sign-in/select/confirm load scenario or the original 30-minute soak test.
Authentication uses tokens obtained beforehand; token acquisition latency is
excluded. Confirmation correctness is covered separately by integration tests
and a controlled end-to-end smoke test.

Prepare one independently onboarded test account and household for every peak
VU for `elasticity`. Their preferences must allow a seeded `less_oil` recipe and a Shop plan.
Use fresh Cognito **ID tokens** for the existing application client. Setup calls
`GET /api/me`, verifies onboarding, checks token lifetime, and rejects duplicate
households for `elasticity`. Tokens are still verified by API Gateway.

Store them only in an ignored file such as `private/load-tokens.json`:

```json
[
  { "id_token": "FIRST_TEST_ACCOUNT_ID_TOKEN" },
  { "id_token": "SECOND_TEST_ACCOUNT_ID_TOKEN" }
]
```

Do not commit tokens or put them in command-line arguments. The script never
logs them. Do not use k6 HTTP debugging or a cloud runner with these credentials.
`COOKISH_ID_TOKEN` takes precedence over `TOKENS_FILE`; remove it before the
independent-household `elasticity` run, which requires multiple accounts.
Run a smoke test for each fixture if its preferences differ. A 404 `NO_RESULT`
is a failed fixture for this workload, not a successful low-latency request.

## Run from PowerShell

Install k6 from the [official installation instructions](https://grafana.com/docs/k6/latest/set-up/install-k6/).
No Python package or Docker is required. From the repository root:

```powershell
$env:BASE_URL = 'https://YOUR_HTTP_API_ID.execute-api.ap-southeast-1.amazonaws.com'
$env:TOKENS_FILE = '../../private/load-tokens.json'
# open() resolves this path relative to eval/load/sessions.js.
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:RESULT_PREFIX = "private/load-$stamp-smoke"
$env:PROFILE = 'smoke'
k6 run eval/load/sessions.js
if ($LASTEXITCODE -ne 0) { throw 'Smoke failed; inspect the result before increasing load.' }
```

The `private/` directory must already exist. Output paths are relative to the
shell working directory. Use a new prefix for each run so earlier evidence is
preserved. After the smoke succeeds, inspect the live Lambda concurrency limits
and RDS connection capacity, then run the bounded increase:

```powershell
$env:PROFILE = 'elasticity'
$env:PEAK_VUS = '50'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$env:RESULT_PREFIX = "private/load-$stamp-elasticity"
k6 run --out "json=$env:RESULT_PREFIX-points.json" eval/load/sessions.js
$loadExit = $LASTEXITCODE
Write-Output "k6 exit: $loadExit"
```

Keep the terminal preflight UTC timestamp, final summary and time-series points.
Do not add `--vus`, `--duration`, `--iterations`, distributed execution or external
scenario overrides; those change the script's bounds and account mapping.
Press Ctrl+C to stop manually if CloudWatch shows distress.

| Setting | Default | Allowed |
|---|---:|---|
| `PROFILE` | `smoke` | `smoke`, `elasticity`, `contention`, `read_only_smoke`, `read_only_elasticity` |
| `PEAK_VUS` | 50 | 21–100; smoke always uses 1 |
| `BASELINE_VUS` | 5 | 1–20 and below peak |
| `HOLD_SECONDS` | 120 | 30–600 at peak |
| `THINK_SECONDS` | 2 | 0.25–10 between workflows |
| `REQUEST_TIMEOUT_SECONDS` | 10 | 1–30 |
| `MAX_ITERATIONS` | 5,000; reads 6,000 | 1–10,000 total loop starts |
| `P95_MS` | 2,000 | 100–30,000; tag latency for workflows, each route for reads |

The default elasticity schedule lasts 400 seconds, plus up to 180 seconds of
setup and 15 seconds to finish in-flight work. The largest allowed schedule is
880 seconds, before setup/grace. Each recommendation loop makes six requests,
plus two initial session requests per VU. Read-only loops make two GETs.
The iteration cap bounds started loops; crossing the
cap aborts the run as incomplete. Stop-on-error aborts the entire test on its
first unexpected HTTP status or malformed JSON. The p95 threshold can abort
after 30 seconds. Other in-flight requests may finish after an abort.

`contention` deliberately maps all VUs to the first account. Cook/Shop hold a
household-level database lock, so this profile measures household serialization,
not independent-user scalability. Keep its results separate. Fifty tokens for
users in one household would have the same limitation, which is why the
elasticity preflight checks household IDs as well as user IDs.

## Evidence needed for the report

Record the deployed commit, UTC start/end, region, Lambda memory/architecture,
reserved concurrency, RDS instance/connection limit, dataset and household count,
profile/settings, k6 version and generator location. Check that the generator
itself has spare CPU/network capacity. Do not include tokens or household IDs in
the public report.

For the same UTC window, export CloudWatch data for baseline, intermediate, peak
and recovery. Use 60-second periods and include a few minutes before/after.
Metric references: [Lambda](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics-types.html),
[HTTP API](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-metrics.html),
[RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-metrics.html).

| AWS metric | Statistic | What it establishes |
|---|---|---|
| `AWS/Lambda`, `ConcurrentExecutions`, `FunctionName=cookish-api` | Maximum | Actual concurrent invocations; compare baseline, peak and recovery |
| Lambda `Invocations`, `Errors`, `Throttles` | Sum | Served demand and service failures |
| Lambda `Duration` | p50, p95, p99 | Server execution time; compare with client route latency |
| HTTP API `Count`, `4xx`, `5xx` | Sum | Gateway traffic and failures |
| HTTP API `Latency`, `IntegrationLatency` | p95 | Gateway overhead and backend response time |
| RDS `DatabaseConnections`, `CPUUtilization` | Maximum | Database pressure during the ramp |
| RDS `FreeableMemory` | Minimum | Memory headroom |

Use the correct API ID and DB instance identifier for their metric dimensions.
Inspect Lambda logs for initialization reports if reporting cold-start share;
client latency cannot reliably identify cold starts. Warm environments may stay
allocated after traffic falls: falling `ConcurrentExecutions` shows reduced
active work, not immediate destruction of all warm environments.

Report the observed maximum concurrency and throughput, route p50/p95/p99,
errors/throttles and recovery. More than one concurrent Lambda execution shows
parallel serving; compare increases across phases to demonstrate response to
load. If concurrency does not increase, describe that result and investigate
pacing, household contention, limits or insufficient demand. Do not claim
elasticity solely because all 50 VUs completed. Do not automatically raise load
after a failing run. This script supplies no evidence of AI-path scaling.

References: [ramping VUs](https://grafana.com/docs/k6/latest/using-k6/scenarios/executors/ramping-vus/),
[execution and abort](https://grafana.com/docs/k6/latest/javascript-api/k6-execution/),
[thresholds](https://grafana.com/docs/k6/latest/using-k6/thresholds/),
[custom summaries](https://grafana.com/docs/k6/latest/results-output/end-of-test/custom-summary/).
