# Load-test monitoring

On 7 November 2026, the existing [cookish-ops dashboard](https://ap-southeast-1.console.aws.amazon.com/cloudwatch/home?region=ap-southeast-1#dashboards/dashboard/cookish-ops)
was updated successfully from seven to twelve widgets. The deployed dashboard
includes the concurrency and RDS graphs below. The live RDS identifier was
verified as `cookish-db` (PostgreSQL, `db.t4g.micro`, single-AZ in Singapore).
The previous dashboard source is retained locally under
`private/release/backups/cookish-ops-before-20261107.json`.

The existing `cookish-api-gateway-5xx` and `cookish-api-errors` alarms now have
enabled ALARM-state actions targeting SNS topic `cookish-api-alerts`. Its email
subscription is confirmed. Both alarms were OK when checked; their thresholds
remain unchanged: Sum at least one, one datapoint within five minutes, with
missing data treated as not breaching. Actual alarm notification delivery has
not been tested.

Both existing monthly budgets, `cookish-monthly-20` ($20) and
`cookish-monthly-40` ($40), were checked and saved with the user-approved email
recipient added; the existing recipient was retained. Both cover the whole AWS
account (no filters) and alert when actual cost exceeds 100% of the budget.
The new recipient remains unverified. The console's Send verification action
was denied because the school role lacks `notifications-contacts:CreateEmailContact`,
`notifications-contacts:SendActivationCode` and `notifications-contacts:ListEmailContacts`.
An administrator for the school account must resolve or complete this verification;
no IAM permissions were changed. Budget alert delivery has not been tested.

`cloudwatch-dashboard.json` is the reusable source template. Render it with verified resource IDs
before applying it. The renderer does not contact AWS or deploy a dashboard.
The database identifier remains an explicit render input; verify it again when
applying the template to another deployment.

From the repository root, using Python 3.12 or later:

```powershell
python infra/render_dashboard.py --account-id YOUR_AWS_ACCOUNT_ID --region ap-southeast-1 --api-id cit4onmvhf --db-instance-id cookish-db --output private/release/cloudwatch-dashboard.json
```

Supply your AWS account ID locally. `--db-instance-id` takes the RDS **DB identifier**,
not its endpoint, database name or CloudFormation logical ID. The command validates placeholders
and widget positions, rejects overlapping widgets, and preserves JSON strings
such as the HTTP API stage `$default`. It never embeds credentials.

After reviewing the rendered file, use the existing dashboard's **Actions → View/edit
source** in CloudWatch. Preserve its current source as a rollback copy, paste the
rendered body, save, and check that each resource has data in the intended time
range. A successful local render does not verify AWS permissions or live metrics.

| Graph | Statistic | Purpose |
|---|---|---|
| API and AI Lambda concurrent executions | Maximum, 60 seconds | Peak simultaneous invocations per minute |
| Lambda invocations, errors, throttles | Sum, 60 seconds | Traffic and failure counts |
| Lambda duration | p95, 60 seconds | Function execution latency |
| HTTP API requests, 4xx, 5xx | Sum, 60 seconds | Gateway traffic and failures |
| HTTP API latency and integration latency | p95, 60 seconds | End-to-end and integration latency |
| RDS database connections | Maximum, 60 seconds | Client connections during load |
| RDS CPU utilization | Average and Maximum, 60 seconds | Database CPU pressure |
| RDS freeable memory | Minimum, 60 seconds | Lowest available database memory |

Lambda concurrency has one-minute granularity, and AWS recommends viewing its
maximum. Dashboard `periodOverride: inherit` keeps the explicit periods when the
dashboard opens. See [Lambda concurrency metrics](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-concurrency.html)
and [dashboard syntax](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Dashboard-Body-Structure.html).
RDS connection counts are client network connections, not every internal database
session, and freeable memory is reported in bytes. See [RDS metric definitions](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-metrics.html).

## Recorded run

The [7 November 50-VU read-test report](../eval/load/results/2026-11-07-read-only-50-vus.md)
records 10,200 workload GET requests with zero client errors. API concurrency
rose from one in the quiet minutes to a maximum of six, then returned to one.
The initial five-VU phase already reached five concurrent executions, so the
increase from that phase to peak was modest. Use the report's phase timings and
limits rather than treating 50 VUs as 50 simultaneous Lambda invocations.

## Evidence to capture

Use the [load script](../eval/load/README.md) and a single UTC time range covering
the quiet baseline, load ramp, sustained traffic and recovery. Save the load
summary and dashboard screenshots with their start/end times and actual resource
IDs. Export the concurrency and database series when numerical evidence is needed.

More than 20 test users is not proof of elasticity. Look for a rise in simultaneous
Lambda invocations as demand rises, acceptable latency/error rates under load,
and a decline after traffic stops. Do not infer provisioned capacity or persistent
container counts from this graph. Compare database pressure too: household locks
can serialize requests, while separate Lambda environments can open additional
database connections. Single-household and distributed-household runs answer
different questions.

No-data graphs are not zeroes. Check the account, region, resource dimension,
time range and metric publication delay before interpreting them. Neither the authenticated read-only load profile nor the Cook/Shop session
profile calls the AI service, so neither demonstrates AI scaling. The dashboard
source does not provision alarms, SNS subscriptions or budgets; those resources
are configured separately. Actual alarm delivery, budget alert delivery and AI timeout classification remain
unchecked. The new budget recipient's verification is blocked by the permission
denial above.
