# Authenticated read load: 7 November 2026

The **5 → 25 → 50 → 5 virtual-user** run completed with **5,100 read loops**,
**10,200 workload requests** and **zero request errors**. All HTTP responses were
200, including two additional preflight requests. k6 exited with code 0 and all
configured thresholds passed. The route p95 target was 2,000 ms.

Each loop read the inventory and one fixed seeded recipe, then waited two seconds.
All users shared one pre-existing household and a pre-obtained authentication token.
There were no intentional writes, recipe-ranking calls, confirmations or AI calls.

| Stable phase | Observed VUs | Seconds | Requests | Requests/s | p50 ms | p95 ms | p99 ms | Errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline | 5 | 60 | 282 | 4.70 | 39.27 | 89.27 | 630.30 | 0 |
| Intermediate | 25 | 60 | 1,448 | 24.13 | 34.71 | 44.83 | 53.30 | 0 |
| Peak | 50 | 120 | 5,803 | 48.36 | 33.37 | 44.57 | 49.63 | 0 |
| Recovery | 5 | 60 | 289 | 4.82 | 35.01 | 41.94 | 50.01 | 0 |

Ramps and stopping are included in the [aggregate JSON](2026-11-07-read-only-50-vus.json).
Requests are assigned to their phase when they start, so phase request counts need
not equal twice the number of loops completed in that phase.

Across the workload, inventory p95 was **39.38 ms**, recipe p95 **47.34 ms**, and
combined p95 **45.41 ms**. The slowest request took **4,996 ms** during baseline;
passing a percentile target does not mean every request was below two seconds.
These are client HTTP durations, excluding connection/TLS setup and sign-in token
acquisition. Cold starts were not separately identified.

## Lambda concurrency evidence

CloudWatch `AWS/Lambda ConcurrentExecutions`, **Maximum over 60 seconds**, for
`cookish-api`:

| UTC minute | 06:48 | 06:49 | 06:50 | 06:51 | 06:52 | 06:53 | 06:54 | 06:55 | 06:56 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Maximum concurrent executions | 1 | 1 | 5 | 3 | 4 | 6 | 5 | 5 | 1 |

The service handled up to **six simultaneous Lambda invocations**, compared with
one in the two preceding minutes, and returned to one in the recovery/stopping
minute. The initial five-VU baseline minute already reached five concurrent
executions, so the increase from baseline to peak was modest and not proportional
to virtual users. Minute buckets overlap phase boundaries. This supports increased
parallel serving under the read workload; it does not show 50 Lambda instances or
prove full-application scalability. Falling active concurrency does not establish
that AWS immediately removed warm execution environments.

The corresponding **06:50–06:56 UTC minute buckets** recorded **10,203 Lambda
invocations, zero Lambda errors and zero throttles**. This is one more invocation
than the client's 10,202 requests: minute buckets include time outside the exact
run, so no exact reconciliation or exclusive attribution is claimed.

RDS reached **five client connections**, **8.88% maximum CPU**, and a minimum of
**183.17 MiB freeable memory** in those buckets. Connections remained at five
through 06:58 and reached six at 06:59; these later samples do not show connection
teardown and cannot be attributed solely to the test. The [sanitized minute
series](2026-11-07-read-only-50-vus-cloudwatch.csv) retains the before/after context.
These observations show limited database pressure for this workload, not its
capacity under transaction-heavy traffic. API Gateway and server-duration exports
are not included in this evidence set.

## Run context and limits

- API source: `c55ff3b9b298d553524f65640588dea03299279f`, merged into main as
  `b5b78fcb75266f9995c6a07d33bc8ffb7b196039`; script: `eval/load/sessions.js`.
- Region: Singapore (`ap-southeast-1`); API Python 3.12, ARM64, 512 MB.
- Generator: local Windows machine in Singapore, k6 2.3.0. Generator CPU/network
  headroom was not recorded.
- Reported start: **06:50:08.214 UTC**; summary finished **06:56:48.484 UTC**.
  Configured schedule: **400 seconds**; peak held for 120 seconds.
- This is a **single-household read test**, not multi-household transaction testing,
  the full sign-in/select/confirm workflow, or the specified 30-minute soak.
- Source-file SHA256 values, route/phase metrics and calculation conventions are
  retained in the aggregate JSON. Credentials and household/recipe IDs are omitted.

The remaining evaluation needs representative independent households, Cook/Shop
transactions and the longer soak. This run supplies no AI-path scaling evidence,
database-capacity estimate or measured cost per user.
