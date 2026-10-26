# AI Lambda packaging and platform handoff

No AWS resources have been created or modified. This document is a handoff to the
platform owner, not an automatic deployment script. All build/test tools operate
locally unless someone separately publishes/deploys the image.

## Two different images

| Image | Purpose | Start mechanism |
|---|---|---|
| `cookish-ai:local` | Development and HTTP testing on port 8001 | Uvicorn |
| `cookish-ai:lambda` | Lambda runtime and local emulator on port 9000 | `app.lambda_handler.handler` via Mangum |

`Dockerfile.lambda` uses the official AWS Python 3.12 base, which includes the
runtime interface client and local emulator. Runtime requirements are exported
from `uv.lock` without dev dependencies and installed with hash verification.
Only `app/` is copied into the production image. No catalogue is required after
the user's ingredient-ID removal. The development image is not the Lambda artifact.
The Lambda image defaults to `AI_PROVIDER=soclaas`, so missing production settings
fail with a controlled 503 rather than serving fake data. Fake mode must be enabled
explicitly for local emulator tests.

Build exactly one Linux architecture and configure Lambda to match. The helper
defaults to arm64 for this Apple Silicon workspace; amd64 maps to Lambda x86_64:

```bash
python3 ai/scripts/build_lambda.py --arch arm64
# Or select x86_64 deployment explicitly:
python3 ai/scripts/build_lambda.py --arch amd64 --tag cookish-ai:lambda-amd64
```

The helper uses buildx with `--load` and `--provenance=false`; it never pushes to ECR.
Record the tested image digest before handoff and pin approved base-image digests
in release automation; a mutable base tag can change across future builds.

## Test the Lambda runtime locally

Stop an existing container with the same name first, if one is running. Then:

```bash
docker run --rm --name cookish-ai-lambda-local --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  -p 127.0.0.1:9000:8080 -e AI_PROVIDER=fake cookish-ai:lambda
```

In another terminal, from the repository root:

```bash
python3 ai/scripts/test_lambda.py --text "2 eggs"
python3 ai/scripts/test_lambda.py --source voice --text "two packs of tofu"
python3 ai/scripts/test_lambda.py --interpret "something quicker"
python3 ai/scripts/test_lambda.py --image ai/dataset/receipt/fairprice-receipt.jpeg --kind receipt
python3 ai/scripts/test_lambda.py --image YOUR_GROCERY_PHOTO.jpeg --kind photo
```

The helper wraps input in an API Gateway HTTP API v2 event and posts it to the
emulator invocation endpoint. The outer HTTP request can succeed while the Lambda
invocation fails, so the helper checks the inner `statusCode`. Fake mode proves
packaging and routing only. Use your own grocery image for recognition evaluation.

For explicitly enabled school testing, replace `-e AI_PROVIDER=fake` with
`--env-file ai/.env -e AI_PROVIDER=soclaas`. Local keys need no AWS account.
Do not pass host AWS credentials or create a real secret merely to test fake mode.
Local Secrets Manager behavior is covered by mocks, not real AWS calls.

The request deadline is capped at 27 seconds for Lambda and at the invocation's
remaining time minus one second. The platform's planned function timeout is 29
seconds; this is a project setting, not AWS's maximum supported timeout. Slow
school requests may return 503 and still consume provider quota. An aborted local
wait does not guarantee the school server cancels its generation.

The emulator does not validate API Gateway authorization, IAM, deployed networking,
real concurrency or end-to-end production latency. Those are deployment checks.

## Platform owner checklist

1. Agree image-based deployment versus the shared plan's existing SAM ZIP flow.
   Exactly one infrastructure tool must own each resource; do not let SAM and
   Terraform manage the same Lambda independently.
   An existing ZIP-package function cannot be converted in place to an image:
   create an image-based function and migrate its routing if that situation arises.
2. Publish the tested single-architecture image to the selected regional ECR
   repository; reference its immutable digest in release configuration.
3. Create/update an image-package Lambda matching arm64 or x86_64. Leave the image
   command as `app.lambda_handler.handler`; do not set the development Uvicorn command.
4. Configure the school base URL, default/per-task models, output mode and token
   limit. Use `AI_PROVIDER=soclaas`, `AI_REQUEST_TIMEOUT_SECONDS=27`, and an HTTP
   timeout at most the overall budget. Never configure fake mode as a hidden fallback.
   Set `SOCLAAS_AUDIO_MODEL` to the verified speech-to-text model ID to enable
   `/ai/transcribe-audio`; it does not fall back to the default image/text model.
   `SOCLAAS_PRICING_CACHE_SECONDS` defaults to 3600 for each warm runtime. The
   service fetches rates from the school `/v1/models` using the same credential,
   and reports unknown cost if pricing is unavailable; no extra Lambda is needed.
5. Prefer `SOCLAAS_API_KEY_SECRET_ARN` rather than embedding a key in the image.
   Grant the execution role `secretsmanager:GetSecretValue` for that specific secret
   and any required customer-managed KMS key permission. Configure exactly one
   credential source. The implementation accepts a raw key or JSON containing
   `SOCLAAS_API_KEY`/`api_key` and caches it for five minutes.
6. Provide execution-role logging permissions scoped to this function's log group.
   Use the JSON `ai_request` and `model_call` events and their `request_id` for
   correlation, latency, usage and failure monitoring. Unknown usage is not zero.
   Both event types include estimated model cost: aggregate one event type to
   avoid double counting. `model_call` includes rate snapshots; `ai_request`
   includes all-attempt totals and partial coverage. Keep model estimates separate
   from actual school charges and AWS infrastructure billing.
7. Route authenticated `/ai/*` API Gateway HTTP API requests to this Lambda using
   payload format 2.0. Cognito authorization is the gateway/platform's responsibility;
   the app assumes it has already run. Local test ports bind only to loopback.
   If the frontend reads accounting headers across origins, expose `X-AI-Model`,
   `X-AI-Input-Tokens`, `X-AI-Output-Tokens`, `X-AI-Estimated-Cost`,
   `X-AI-Known-Estimated-Cost`, `X-AI-Cost-Status`, `X-AI-Cost-Unit`,
   `X-AI-Pricing-Fetched-At` and correlation/attempt headers in gateway CORS.
8. Keep this AI Lambda outside the project's database VPC as planned, with public
   HTTPS access to the school API. It has no database, inventory-write or S3-upload
   permissions requirement. Re-evaluate routing if the school endpoint changes.
9. Set memory/concurrency and gateway throttling against measured workloads and
   school quota, then verify failures and timeout behavior on the deployed stack.
   These settings have not been load-tested or cost-optimized here.

## Shared-contract and acceptance handoff

- Role 1 must remove `DraftItem.ingredient_id` from the backend schema, shared
  OpenAPI export and generated frontend types, and adapt review/confirmation logic.
  AI tests permit precisely that one AI-only field-removal difference for now.
  Export the added `/ai/transcribe-audio` contract and generated frontend types
  too. AI tests separately allow this one route addition. The frontend can send
  its returned text to `/ai/parse-items` with `source: "voice"`; both requests use
  authenticated `/ai/*` routing. No audio is stored and no S3 permission is needed.
- Role 2 must agree how food names become inventory entries and what count/unit
  pairs mean for package contents. The AI does not assign IDs or convert stock.
  Receipt defaults are count 1/unit pcs when missing; text/photo counts stay nullable.
- Role 4's full human-labelled recognition and latency evaluation remains required.
  See `eval/README.md`. Formal accuracy/latency and final model selection
  are not established by unit tests or fake-provider emulator results.
- Final project acceptance remains a real receipt and spoken transcript becoming
  user-reviewed inventory updates on the deployed stack, plus the accuracy table.

Official references checked for this packaging flow:
[AWS Python container images](https://docs.aws.amazon.com/lambda/latest/dg/python-image.html),
[Lambda image requirements](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html),
[Secrets Manager GetSecretValue](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html).
