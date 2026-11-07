# Cookish initial cost model

**Planning estimate; Lambda pricing corrected 7 November 2026. All money in USD.** Published Singapore
AWS rates are combined with assumed usage. The model is not a bill, measured
cost per user, capacity test, profit forecast or replacement for Role 3's
cloud/on-premise comparison. Deployed-provider usage has not been costed here;
model-provider charges remain assumptions.

The [business case draft](../../docs/business-case.md) uses these estimates.
The [research notes](../../docs/business-case-research.md) cover the market,
alternatives, price hypothesis and proposed free/paid offering.

## Reproduce or change an assumption

From the repository root, using the backend environment (Python standard library only):

```powershell
backend/.venv/Scripts/python.exe eval/business_case/model.py --output eval/business_case/results.json
```

The files serve different purposes:

- [`aws-rates.json`](aws-rates.json): selected public AWS product/term records,
  exact prices, region, tier bounds, publication dates, SKUs, rate codes, source
  URLs and source hashes. No account credentials or bill data.
- [`assumptions.json`](assumptions.json): editable quantities, usage, price and
  conversion hypotheses. No measured quantities are included yet.
- [`model.py`](model.py): decimal arithmetic and scenario generation. It makes
  no network requests and does not change the deployed app.
- [`results.json`](results.json): component totals, scenario results and SHA-256
  hashes of the inputs and calculator, using UTF-8 text with line endings
  normalized to LF for cross-platform consistency (not raw file-byte hashes).
  Monetary strings retain six decimal
  places for reconciliation; reporting that precision does not make assumptions
  more certain.

## Price basis and fixed monthly basket

Region: `ap-southeast-1`. Database: PostgreSQL `db.t4g.micro`, Single-AZ and 20 GB
gp3. Lambda duration now uses **ARM64** prices, matching the API, AI and migration
functions checked on 7 November 2026. The workload model uses **0.5 GB** for
API and AI, matching the **512 MB verified for both functions** on that date.
Migration is also 512 MB but its deployment-time invocations are not
included in the monthly request scenarios. Architecture is a configuration fact;
the durations, request counts and other usage inputs remain assumptions.

| Assumed fixed quantity | Published unit price | Monthly USD |
|---|---:|---:|
| Database, 730 hours | 0.025/hour | 18.250 |
| Database storage, 20 GB | 0.138/GB-month | 2.760 |
| Two Secrets Manager secrets | 0.40/secret-month | 0.800 |
| 200 Amplify build minutes | 0.01/minute | 2.000 |
| 1 GB Amplify storage | 0.023/GB-month | 0.023 |
| One CloudWatch dashboard | 3/dashboard-month | 3.000 |
| Five custom metrics | 0.30/metric-month | 1.500 |
| Five standard alarm metrics | 0.10/metric-month | 0.500 |
| **Fixed subtotal** | | **28.833** |

Sources: AWS [RDS](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/ap-southeast-1/index.json),
[Amplify](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSAmplify/current/ap-southeast-1/index.json),
[Secrets Manager](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSSecretsManager/current/ap-southeast-1/index.json),
[regional CloudWatch](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/ap-southeast-1/index.json)
and [global dashboard pricing](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/index.json),
accessed 24 October 2026. The snapshot preserves the selected terms because the
`current` URLs can change. The `us-east-1` pricing endpoint hostname does not
change the selected deployment region.

| Variable service | Rate used | Source |
|---|---:|---|
| Lambda ARM64 compute | 0.0000133334/GB-second | [AWS Lambda price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/ap-southeast-1/index.json), checked 7 November 2026 |
| Lambda ARM64 invocation | 0.20/million | Same Lambda list |
| HTTP API | **1.25/million billing units** | [API Gateway Singapore list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonApiGateway/current/ap-southeast-1/index.json) |
| Amplify data served | 0.15/GB | Amplify list above |
| Other internet egress | 0.12/GB | [AWS data transfer list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/ap-southeast-1/index.json) |
| Logs ingested / stored | 0.70/GB / 0.03/GB-month | CloudWatch list above |
| Secrets API call | 0.000005/call | Secrets list above |
| Cognito Essentials | 0.015/monthly active user before allowances | [Cognito Singapore list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCognito/current/ap-southeast-1/index.json) |

The Lambda source was refreshed to AWS's 30 October 2026 price-list publication;
other service records retain their 24 October retrieval dates. The selected ARM64
duration tier runs from zero to 7.5 billion GB-seconds/month; request pricing uses
the ARM product record too. This model uses the applicable first paid tiers. Its largest example
remains below those tier ceilings; do not extrapolate to arbitrary traffic
without adding the relevant tiers.

## Workload assumptions

Each row is per active household per month unless stated otherwise. Low/base/high
vary several inputs together and are stress scenarios, not confidence intervals.

| Input | Low | Base | High |
|---|---:|---:|---:|
| Non-AI API requests, including polling/background work/retries | 150 | 300 | 600 |
| API billed seconds per request | 0.1 | 0.2 | 0.4 |
| Imports per paying household | 5 | 10 | 20 |
| Internal model attempts per import | 1.0 | 1.1 | 1.2 |
| AI billed seconds per model attempt | 3 | 8 | 15 |
| **Assumed** model cost per attempt, USD | 0.002 | 0.01 | 0.05 |
| Frontend data served, GB | 0.02 | 0.05 | 0.10 |
| Other internet egress, GB | 0.005 | 0.02 | 0.05 |
| Logs ingested and retained, GB | 0.001 | 0.003 | 0.010 |

Common assumptions:

- Two monthly active login accounts per active household. This is independent
  of SingStat's average household size; family members need not all log in.
- A proposed **three-import one-time free trial**. Assuming 10% of active free
  households are new in a month gives **0.3 imports per active free household**.
  It is not three new imports every month. Abuse and changing acquisition mix
  would increase costs; the allowance is not enforced in the current prototype.
- A proposed **20-import monthly paid limit**, with base expected usage of ten.
  Count paid and free usage separately when actual measurements become available.
- One outer upload/invocation per import; the model has an editable outer-attempt
  multiplier. Internal model retries increase provider charges and AI duration.
  They do not create another HTTP request in this assumption.
- Three HTTP billing units per AI upload, assuming a JSON/base64 payload greater
  than 1 MiB and at most 1.5 MiB. [HTTP API uploads are billed in 512 KB increments](https://aws.amazon.com/api-gateway/pricing/).
  Other API requests are assumed to consume one unit. Replace with measured payload sizes.
- 0.1 Secrets Manager reads per Lambda invocation assumes caching. Role 3 must
  confirm how credentials reach the VPC-bound API when no NAT or VPC endpoint
  is provisioned; this is a cost parameter, not a verified retrieval design.
- Log retained volume equals monthly ingested volume as an approximation. Actual
  compression, retention, query activity and AI retry logging must be measured.
- Egress buckets cover distinct frontend and other traffic. No duplicated image
  storage is included: the current specification does not persist image uploads.

Model-provider amounts are **hypotheses, not quoted prices**. Role 4 should replace
them with `(input tokens × input rate + output tokens × output rate) / 1,000,000`,
plus applicable image/OCR fees, averaging all billable attempts including failures.

## Equations

Let `N` be active households, `q` the paying share, `P` the monthly price,
`F` fixed monthly cost and `i` mean imports per active household:

```text
i = (1 - q) × 3 trial imports × 10% new free households + q × paid imports
AI invocations = i × outer attempts
model attempts = AI invocations × internal attempts
variable cost per household = compute + API requests + model attempts
                           + egress + logs + secret reads + authentication
monthly infrastructure cost C = F + N × variable cost per household
cost per active household = C / N
cost per active login = C / (N × 2), under the two-account assumption
infrastructure allocated per paying household = C / (N × q)
monthly subscription revenue = N × q × P
```

The calculator exposes every variable cost component. Recalculate AI usage when
changing `q`; simply dividing the same total by a new paying count is incorrect.
For `q = 0`, allocated cost per paying household is undefined and reported as null.

## Calculated planning scenarios

All rows use **10% paying households** and **US$4.99/month**. No free allowances,
student credits, discounts or tax are deducted or added.

| Active households | Low monthly cost | Base monthly cost | High monthly cost | Base per active household | Base per active login | Base allocated per paying household |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 32.46 | 34.55 | 48.59 | 0.3455 | 0.1727 | 3.4546 |
| 1,000 | 65.11 | 85.96 | 226.39 | 0.0860 | 0.0430 | 0.8596 |
| 10,000 | 391.65 | 600.08 | 2,004.36 | 0.0600 | 0.0300 | 0.6001 |

The 10,000-household row holds the small deployment constant to expose cost
sensitivity. **It does not establish that one micro database supports that load.**
Database connections, CPU, storage growth and resizing must be validated before
using that row as a deployment budget. The high case at only 100 households
already allocates about US$4.86 to each paying household, leaving little of
US$4.99 for omitted costs.

At 1,000 active households under base usage:

| Paying share | Paying households | Monthly infrastructure | Cost allocated per paying household | Gross subscription revenue |
|---:|---:|---:|---:|---:|
| 5% | 50 | 80.59 | 1.61 | 249.50 |
| 10% | 100 | 85.96 | 0.86 | 499.00 |
| 20% | 200 | 96.69 | 0.48 | 998.00 |

These figures show conditional infrastructure coverage, not profit. At smaller
scale or lower conversion, fixed costs and the subsidy to free households can
consume the proposed subscription. No adoption or payment rates have been measured.

## Free allowances and excluded costs

The core tables deliberately use **gross list prices**. Student credits finance
a bill; they do not reduce underlying unit cost. Cognito is provisionally
**Essentials**, whose direct/social-login allowance is 10,000 monthly active users;
Role 3 must verify the actual edition and account eligibility. [AWS Cognito pricing](https://aws.amazon.com/cognito/pricing/)

With two active accounts per household and that entire allowance available,
the authentication line becomes US$0, US$0 and US$150 at 100, 1,000 and 10,000
households, versus gross US$3, US$30 and US$300. The separate result sensitivity
subtracts **only** that Cognito allowance. Other service allowances can also
reduce cash cost and must not be counted once per environment when shared.

Excluded from all main totals: payment/store fees, taxes, labor, support, recipe
review, acquisition, refunds, domain registration, verification emails, extra
backup/snapshot storage, cross-AZ traffic, log-query/metric-API charges, optional
security services and excess database CPU credits. The snapshot records RDS
T4g excess credits at **US$0.075/vCPU-hour**, but no zero-credit usage measurement
exists. [AWS RDS PostgreSQL pricing](https://aws.amazon.com/rds/postgresql/pricing/)

No NAT gateway, VPC endpoint, RDS Proxy, Multi-AZ instance or provisioned Lambda
concurrency is budgeted because the specified architecture does not include
them. Production availability, network access or capacity changes may add costs.

## Measurement handoff

Role 3 should replace assumptions with a dated workload and saved calculator
estimate, reconciling service line items to Cost Explorer. Role 4 supplies model
usage. Keep credits and allowances separate from gross consumption.

| Owner | Required input |
|---|---|
| Role 3 | Recheck architecture/memory after configuration changes, plus Cognito tier, database/storage/networking and secrets-access configuration |
| Roles 3 and 5 | Distinct active households, active accounts, free/paid split, new household share and import allowance definitions |
| Role 3 | Requests by route, payload billing units, billed durations, cold starts, retries, build minutes and egress |
| Roles 3 and 4 | Provider/model version, input/output tokens, image charges, failures, retries and billed cost per import |
| Role 3 | Log ingestion/retention/queries, secrets reads, verification emails, backup growth, CPU credits and cross-AZ transfer |
| Role 3 | Tested database capacity and resizing points, Cost Explorer totals, saved AWS Pricing Calculator link and on-premise TCO |

The final report should label this table “preliminary estimate” until those
measurements are available. A demand test and complete operating costs are also
needed before making a commercial viability claim.
