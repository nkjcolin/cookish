# AI service implementation plan

This plan has **12 sequential parts**. Each part can be requested and completed on
its own, for example: "Implement Part 4 only." Add relevant tests and documentation
as each part is implemented rather than deferring them to the end.

Original-unit update (2026-10-24): preserve kg as kg and litres as l; normalize
spelling without converting measurement scale. Python still multiplies extracted
package factors once, so two 0.5 kg packs return 1 kg and two 280 g packs return
560 g. Receipt missing-unit/default rules and the public response shape remain
unchanged. This supersedes metric conversion in the historical records below.
The batch runner now fingerprints this behavior as
`extracted-factors-original-units-v3`, preventing reuse of the older converted
batch. Historical predictions retain their original run metadata. Original units
still need reconciliation with recipe units during backend integration.
Live checks showed that the model itself sometimes converts 1 kg into 1000 g,
even with conversion disabled in code and explicit schema instructions. A narrow
source-unit check therefore restores one unambiguous printed/stated scale in
`raw_text`, rescaling the extracted total to match it. Multiple printed scales
and missing evidence keep the model unit. No package count or size is inferred
from raw text. Verification: 258 app tests and 24 standalone checks pass, plus
Ruff/format checks. Historical outputs are retained; focused checks are separate.
Both Docker images and running containers were refreshed and source hashes
verified. The live receipt response preserved kg, but still returned 1000 kg for
the printed 1 kg purchase: unit preservation passed and numeric accuracy failed.
The response and explicit check outcomes are saved under
`output/generated/original-unit-live-check-20261024T145617Z/`. This unit change
does not solve remaining model quantity extraction errors.

Previous total-quantity update (2026-10-24): the approved response convention was total
amount in `unit`. The model extracts readable purchase count and package contents
as separate factors in a private `quantity` object; Python multiplies them once.
Already-totalled measurements are single factors. All extraction routes use
g/ml/pcs where supported, with shared spelling normalization and kg/L conversion.
Structured LAAS receipt helpers share receipt quantity finalization with the API.
Unknown measured amounts remain null, explicit unknown-size purchase units remain
usable as package counts, and an entirely unmeasured purchase retains `1 pcs`.
Null-only unit fallback, original `raw_text`, name-only fields and generic LAAS
test helpers are retained. No guessed pack sizes, densities or drained yields.
The public response shape is unchanged; backend ID matching, countable stock
batches and production service wiring remain a handoff. This supersedes the
quantity semantics in the historical execution records below.
Verification: 248 application tests and 24 standalone offline checks pass; Ruff
and whitespace checks pass. Coverage includes metric conversions, preserving
already-totalled amounts without multiplying again, unknown measured quantities,
invalid factors/counts, private-field removal and all four extraction modes.
Live school checks returned 450 g for two 225 g packs, 660 ml for 0.66 L, and
the correct measured contents on the previously failing generated receipt.
Model arithmetic was tested and found unreliable, so multiplication moved to
code rather than adding further prompt checks. The previous generated-results
batch is archived at `output/generated/history/before-total-quantity-20261024T141623Z/`.
Model-arithmetic trials are retained in the same history directory under
`before-total-quantity-self-check-20261024T142146Z/` and
`before-python-quantity-factors-20261024T143025Z/`.
The 30-image school-model rerun is recorded in `output/generated/_run.json`;
these synthetic predictions do not replace deferred human-labelled evaluation.
Final factor-based batch: 30 successful requests, 150 draft items, no failed
requests. Eleven suspect quantity/unit predictions across five receipts are
documented in `output/generated/QUANTITY_REVIEW.md`. Python removes arithmetic
errors from correctly extracted factors; selecting factors/units is still model
recognition work. Do not treat these draft outputs as verified inventory amounts.
Both local Docker images were rebuilt with the private extraction schema and
Python quantity resolution. The HTTP container uses 60-second provider and
90-second request limits for local receipt testing; the Lambda emulator keeps
fake mode and its 27-second cap. A 12-item school receipt took about 27 seconds,
so production latency/model selection remains open rather than claiming the
synchronous AWS budget has been met.
The rebuilt HTTP container returned 450 g tofu, 560 g broccoli and 500 g garlic
for a live generated receipt in 8.04 seconds. Its text route returned 450 g and
660 ml for the factor/conversion smoke input. Container source hashes matched
the current code; the public OpenAPI contains no private quantity field. The
rebuilt Lambda emulator returned HTTP 200 in fake mode for an image event.

Previous unit clarification (2026-10-24): extract a product's unit independently from the
purchase count, including mass/volume units in its printed name. Generic checkout
`Unit`/`each` labels must not replace an identifiable product unit with `pcs`.
The model returns null for an unknown unit. API receipts apply unit spelling
normalization and then a null-only fallback to `pcs`; structured `laas.py` receipt
helpers apply only the null fallback and preserve every non-null unit. Generic
free-text helpers remain unchanged. This supersedes the older prompt instruction
to replace product mass/volume units with piece units for package purchases.
Existing saved model responses remain historical and are not rewritten.
Verification: 196 application tests and 23 standalone offline checks pass. A live
school-model check of the previously affected generated curry receipt returned
`g`, `ml`, `g`, `g`, `g` with the revised prompt. Its response is saved separately
under `output/generated/unit-check-20261024T133234Z/`; this single smoke result is
not formal accuracy or confidence evaluation.

Status (2026-10-23): Parts 1–11 are implemented locally, with Part 8's ID-matching
scope superseded by the user's name-only response decision. Part 12's evaluation
runner and deployment handoff are implemented, but formal recognition/latency
evaluation, final model selection and deployed acceptance remain incomplete.
No AWS resources have been deployed.
The user explicitly deferred formal labelled-dataset evaluation on 2026-10-23
while finding suitable data; do not collect/download a dataset or run the formal
benchmark until they resume that work. The evaluation tooling remains available.

## Parts 6–12 execution record (2026-10-23)

- Parts 6/7: dedicated school-transport photo and interpretation tests cover prompt
  and server-model selection, visible/unknown counts, all supported adjustments,
  bounds, unsupported fields and all-null/no-op responses. Blank interpretation
  input is rejected before any provider call.
- Revised Part 8: normalize unit spellings and reject invalid numeric quantities
  without assigning IDs or converting package contents into inventory stock.
  Receipt defaults remain 1/pcs; text/photo missing quantities stay nullable.
  Inventory mapping/conversions require the backend owner's agreement.
- Part 9: a request-wide deadline (default 27 seconds) covers preparation, model
  calls and one validation-repair attempt. Calls use the remaining budget; Lambda
  also caps by invocation time minus one second. Tests exercise hard expiry and
  shared retry budgets. Correlated request/model logs and response headers identify
  provider/model, attempts, timing and known usage without logging request contents.
  A cancelled synchronous HTTP call may finish in the background; cancellation
  does not guarantee the school stops generation or refunds quota.
- Part 10: the local helper supports receipt/photo images, typed/voice text and
  interpretation, with distinct connection and timeout errors. Development Docker
  and school/fake configurations are documented.
- Part 11: `Dockerfile.lambda` exports hash-locked production dependencies and
  copies only app code into the official Python 3.12 Lambda base. An arm64 image
  was built and tested through the real local Runtime Interface Emulator with a
  read-only filesystem. Typed, voice, interpretation, receipt and photo-shaped
  invocations all passed using the fake provider. Credentials, prototypes, images,
  outputs, tests and development packages were checked absent from the artifact.
  Packaging/routing tests do not prove deployed IAM, authorization or networking.
- Part 12: the manifest-based runner computes identification precision/recall,
  count/unit errors, known non-food inclusions, confidence bins/Brier score, latency,
  token usage, optional observed correction time and separate interpretation
  accuracy. It does not treat missing labels as empty ground truth or invent prices.
  Formal acceptance requires real-provider results for human-labelled 30 receipts,
  20 grocery photos and 20 voice transcripts. That dataset and school pricing/quota
  terms are not present. See `eval/README.md` and `DEPLOYMENT.md`.
- The test suite passed 175 tests before final integration. Final results and any
  real-provider smoke observations are recorded below when available.

Final integration checks (2026-10-23):

- 177 automated tests, Ruff check and format check pass. The standalone Conda
  experiment's eight offline checks also pass. The existing Starlette TestClient
  and Mangum event-loop deprecation warnings are non-fatal.
- All five local HTTP-helper modes and all five read-only Lambda-emulator modes
  return 200 with the fake provider. Production image checks confirm missing school
  configuration fails closed and secrets/test/eval/development files are absent.
- Fake-provider evaluation and offline re-scoring produce expected metrics and
  correctly keep formal dataset completion false. Reports are private ignored
  artifacts under `eval/results/`.
- A three-request school smoke check returned typed input in 1.44 seconds and
  interpretation in 0.73 seconds; the receipt hit the 20-second provider timeout
  and returned controlled 503. The receipt is unlabelled and no receipt accuracy
  is claimed. Initial interpretation invented numeric defaults because the old
  prompt requested omitted fields while strict output required every field.
- Corrected the interpretation prompt to require null for unmentioned numeric
  fields, with no invented defaults. A separate live recheck returned exactly the
  expected adjustment in 1.02 seconds. This is one smoke result, not a benchmark.
- Formal labelled evaluation was then explicitly deferred by the user. Public
  dataset ideas and a small own-data pilot are documented in `eval/README.md`;
  no dataset was downloaded and no formal benchmark was run.

Local and Lambda images are built; the school-backed HTTP API and fake-provider
Lambda emulator remain available locally. No AWS resources were deployed. The
platform and frontend/backend contract handoffs remain external integration work.

The original task descriptions below are retained as history; the status above
and approved changes supersede outdated catalogue and nullable-receipt requirements.

## Approved change: name-only drafts (2026-10-22)

The user requested removal of `ingredient_id` from AI responses and prompts.
This supersedes the original catalogue-matching requirements below: image and
text extraction now return six fields per item, with no identifier and no
catalogue in the prompt. Confidence describes food identification. The pipeline
does not load a catalogue or perform ID matching; Part 8's matching work and
catalogue packaging requirements must be replanned with the backend owner.

This is an intentional AI-only contract migration. The backend schema, shared
OpenAPI export and generated frontend types are outside the allowed edit scope
and still require Role 1's update, including inventory-confirmation integration.
Contract tests allow exactly this removed property/required entry and compare
everything else unchanged. Historical experimental outputs remain untouched;
they are not used by the app.

Subsequent user request: `laas.py` now loads `receipt.md` for both normal and
combined-output modes, uses the current `DraftResult` without ID matching, and
remains a standalone experiment excluded from the service image. This overrides
the earlier instruction to leave that script unchanged, not the packaging rule.

Verification: 98 automated tests pass, including checks that all extraction paths,
prompts, provider schemas and public OpenAPI omit the field. Provider calls are
mocked; this does not establish improved school-model latency.

## Parts 1–5 execution record

Follow-up correction (2026-10-22): API receipt cleanup now matches the expanded
receipt prompt. Removed the narrow raw-text quantity veto; preserve positive
finite model counts and independently extracted units, default null counts to 1,
and turn invalid numeric counts into null for review. Non-food filtering remains.
Follow-up unit default: retain extracted units; replace null, empty or
whitespace-only receipt units with `pcs`. This fallback is independent of count
and does not change text or food-photo defaults. The receipt prompt matches it.
The expanded suite now passes 119 automated tests, including null/blank unit
fallbacks, explicit-unit preservation and unchanged text/photo behavior.
Receipt layout, prices and pack-size interpretation remain model responsibilities;
this change does not provide independent OCR validation. Text and photo routes
keep their existing nullable-count behavior. The receipt prompt uses the same
default of 1 when a quantity cannot reliably be extracted.
Verification: 111 automated tests pass, including layout-based receipt quantities,
default counts, independently retained units, invalid numeric counts and unchanged
text/photo behavior. School responses are mocked; live model accuracy is not
established by these checks.

- Baseline: the original 10 tests passed. Ruff check and format check reported
  pre-existing issues in the user's experimental `laas.py`. That script was left
  unchanged and explicitly excluded from application linting and Docker inputs.
- Host `uv` was unavailable, so verification used the project's Python 3.12 Docker
  environment. No host Python upgrade or installation was needed.
- Implemented validated configuration, per-task model overrides, the school HTTP
  client, cached secret retrieval, typed/voice source context and receipt image
  validation. Public schemas and errors remain unchanged.
- Added conservative receipt cleanup after a live sample incorrectly included
  toothpaste and interpreted a grooming razor as razor clams. Counts now require
  an explicit matching purchase marker in the original text; unsupported layouts
  remain unknown rather than being inferred from pack contents.
- The expanded suite passes 95 tests, including API contract checks. Ruff check
  and format check pass in the built development image. The existing upstream
  Starlette TestClient deprecation warning remains non-fatal.
- Built `cookish-ai:local`, verified that credentials and experimental files are
  absent from its filesystem, and added `scripts/test_local.py` plus local Docker
  instructions in the README. The helper does not import `laas.py` or read keys.
- Initial live school checks proved connectivity and receipt extraction, but
  response times were variable: one receipt took about 18 seconds, a short direct
  text diagnostic succeeded in about 7 seconds, and other text calls reached the
  service's 20-second HTTP timeout and returned the documented 503 response.
  These are smoke checks, not the formal accuracy or latency evaluation.
- Final image-first check against the built image used a 60-second local provider
  timeout. The FairPrice receipt returned `503 UPSTREAM_UNAVAILABLE` after about
  60 seconds; server logs identified a school API read timeout. A separate text
  request succeeded, but the final receipt path is not live-verified as passing.
  The local API remains available for manual testing. Increasing this local
  timeout does not establish compatibility with the planned AWS request budget.
- Remaining limitations: production `ingredients.csv` is still missing; local
  testing uses the explicitly selected fixture catalogue. The overall deadline,
  full matching improvements, confidence calibration, model-quality comparisons
  and AWS deployment remain later work. See the README for current input limits.

## Scope and agreed decisions

- Re-read [README.md](README.md) before each part. Report differences between the
  README, the implementation and the agreed requirements, including missing inputs
  or work that belongs to another role.
- Edit files only inside `ai/`. Preserve existing user changes and experimental
  files. Changes to shared infrastructure, frontend, backend or root-level
  evaluation files require a handoff to the appropriate owner.
- Keep FastAPI and the existing public request, response and error contracts.
  `app/schemas.py` and `app/errors.py` are backend-owned copies.
- Call the publicly accessible, image-capable school LLM API. Bedrock is not
  required for this integration.
- The application selects a model on the server, using a default model and
  task-specific configuration. The browser does not choose a model. Final model
  choices, including the interpretation model, will be evaluated later.
- Keep the README's baseline of one AI Lambda serving the three routes through
  API Gateway and Mangum. Separate Lambdas would be a coordinated deployment
  change, not a requirement for implementing the routes.
- The AI service returns drafts or cooking adjustments and never writes inventory
  or connects to the database. Users confirm drafts through the separate backend.
- Uploaded images stay in memory during live processing and are not saved to disk,
  S3 or logs. Controlled local evaluation fixtures are separate from live uploads.
- **`laas.py` is reference-only.** Do not import it, execute it from application
  code, use it as a Lambda entry point or include it in the production image. Its
  request format can inform the production client in `app/model_client.py`. Leave
  the experimental script intact unless removal is explicitly requested.

## Route and prompt mapping

| Route | Input distinction | Prompt | Result |
|---|---|---|---|
| `POST /ai/parse-image` | `kind: "receipt"` | `app/prompts/receipt.md` | `DraftResult` |
| `POST /ai/parse-image` | `kind: "photo"` | `app/prompts/photo.md` | `DraftResult` |
| `POST /ai/parse-items` | `source: "typed"` or `"voice"` | `app/prompts/items.md` | `DraftResult` |
| `POST /ai/interpret` | Cooking-adjustment text | `app/prompts/interpret.md` | `InterpretResult` |

The receipt and photo buttons select `kind`; the server selects the corresponding
prompt. Voice transcription occurs in the browser, so the AI service receives
text rather than audio. `/ai/interpret` is optional in the README but is included
in this implementation plan.

## Part 1 - Baseline and safe build setup

Work:

- Run the existing tests, contract checks, lint and format checks; record failures
  that exist before implementation.
- Preserve the current receipt prompt, `laas.py`, local receipts and saved outputs.
- Exclude credentials and experimental material from Docker build contexts and
  production artifacts. Preserve a secret-free environment example if provided.
- Record the existing route contracts and unresolved external dependencies.

Complete when: baseline results are recorded and build inputs exclude sensitive
files without removing the user's local material.

## Part 2 - Configuration and model selection

Work:

- Add configuration for the school endpoint, credential source and default model.
- Support separate model overrides for image tasks, item parsing and
  interpretation, with a documented fallback to the default model.
- Keep final interpretation-model selection provisional until evaluation.
- Support local environment credentials and an AWS Secrets Manager reference for
  deployment. Never accept credentials or model names from public request bodies.
- Document the settings and validate missing or inconsistent configuration.

Proposed names, to be implemented and documented in this part:

- `AI_PROVIDER=soclaas`
- `SOCLAAS_BASE_URL`
- `SOCLAAS_MODEL`
- `SOCLAAS_IMAGE_MODEL` (optional override)
- `SOCLAAS_TEXT_MODEL` (optional override)
- `SOCLAAS_INTERPRET_MODEL` (optional override)
- `SOCLAAS_API_KEY` (local credential)
- `SOCLAAS_API_KEY_SECRET_ARN` (AWS secret reference)
- `INGREDIENTS_CSV` (existing catalogue setting)

Complete when: configuration and task-to-model selection tests pass without
calling the school API or AWS.

## Part 3 - School API client

Work:

- Implement the production client behind the existing model-client interface.
- Use `laas.py` only to understand the school API request format; do not introduce
  a runtime dependency on the script or its file-processing functions.
- Add and lock runtime dependencies in `pyproject.toml` and `uv.lock`.
- Support text and image requests, the configured model, structured output where
  supported, connection reuse and explicit request timeouts.
- Extract response text and token usage. Handle unavailable usage explicitly
  rather than inventing measurements.
- Translate provider failures into `ModelUnavailable`, while preserving the
  pipeline's validation-retry behavior.
- Retain the fake client for development and scripted tests. Never silently fall
  back to fake ingredients when the real provider fails.

Complete when: mocked text/image calls produce the expected internal replies and
provider failures are handled predictably.

## Part 4 - Typed and spoken-list parsing

Work:

- Connect `/ai/parse-items` to the school client and configured text model.
- Preserve the typed/voice distinction in the internal processing context.
- Handle spoken quantities and local ingredient names without guessing unstated
  amounts.
- Return the existing `DraftResult` contract. Do not add an audio-upload route.

Complete when: route tests return valid drafts for typed input and voice
transcripts, including quantity and unknown-ingredient cases.

## Part 5 - Receipt-image parsing

Work:

- Connect `kind: "receipt"` to the receipt prompt and configured image model.
- Validate base64, actual image content, supported types, dimensions and byte size.
- Extract food purchases and exclude non-food products, totals, discounts and
  payment metadata. Evaluate ambiguous lines rather than inventing food names.
- Preserve quantity evidence. Per the later user decision, default a missing
  receipt count to 1 and missing unit to pcs; invalid numeric counts remain unknown.
- Keep the public draft contract: do not introduce price extraction from the
  experimental script.

Complete when: receipt requests use the correct prompt and response schema, and
invalid image inputs produce controlled errors.

## Part 6 - Food-photo parsing

Work:

- Connect `kind: "photo"` to the grocery-photo prompt through the same image route.
- Reuse the image validation introduced in Part 5.
- Identify visible groceries, count only clearly visible units and handle
  ambiguity conservatively.
- Exclude freshness, ripeness, spoilage and expiry judgments.

Complete when: food-photo requests select the correct prompt and return valid
drafts in route tests.

## Part 7 - Cooking interpretation

Work:

- Connect `/ai/interpret` to the configured interpretation model and prompt.
- Validate output against `CookAdjust` and wrap it in `InterpretResult`.
- Allow only supported tags, people, maximum minutes and difficulty.
- Reject attempts to alter allergies, diets or other unsupported fields.
- Keep model choice configurable for later comparison.

Complete when: supported adjustments succeed in tests and unsupported changes are
rejected. The route does not generate recipes or update cooking sessions itself.

## Part 8 - Ingredient matching and draft consistency

Revised scope: ID/catalogue matching below was cancelled by the user. Only numeric
and unit consistency remains in AI scope; backend inventory mapping is a handoff.

Work:

- Match canonical names and aliases against the agreed catalogue format.
- Detect a returned ingredient ID that exists but conflicts with the item name.
- Leave ambiguous matches unresolved instead of forcing a catalogue assignment.
- Check quantity and unit consistency, distinguishing pack count from pack
  contents. Coordinate inventory-unit conversions with the backend owner.
- Continue using fixture data while the production catalogue is unavailable.

Complete when: matching tests pass for known, unknown, ambiguous and inconsistent
items without changing the catalogue's agreed columns.

## Part 9 - Request deadlines, failures and logging

Work:

- Apply an overall deadline across model calls and the single allowed
  validation-repair attempt; account for SDK retries and other overhead.
- Fit the request within the planned 29-second Lambda timeout and 30-second HTTP
  API integration limit. Keep approximately 10 seconds at p95 as the measurement
  target, not an assumed property of the school model.
- Preserve the existing `UPSTREAM_UNAVAILABLE` response and frontend fallback.
- Log request correlation, task, actual selected model, available token usage,
  attempt outcomes, model-call latency and overall request latency.
- Keep images, API keys and raw sensitive request content out of logs.

Complete when: deadline, retry and failure tests return the documented errors and
logs accurately identify the selected model and outcome.

## Part 10 - Local Docker testing

Work:

- Build and run the development image with fake/scripted responses.
- Provide repeatable requests for receipt images, food images, typed lists, voice
  transcripts and cooking interpretation.
- Supply credentials at runtime for explicitly enabled school API testing.
- Document fixture-catalogue use and the mounts needed for contract tests.
- Report any frontend integration changes to its owner; do not edit outside `ai/`.

Complete when: the local container starts and all three routes can be exercised,
with a documented distinction between fake responses and live school-model tests.

## Part 11 - Lambda image and local Lambda testing

Work:

- Add a separate Lambda-compatible Dockerfile and reproducible packaging scripts.
- Include production dependencies and prompts (no catalogue is now needed), with
  `app.lambda_handler.handler` as the entry point.
- Exclude `.env`, `laas.py`, local receipt images, saved outputs and development
  material from the production image.
- Build for a single Linux architecture matching the intended Lambda setting.
- Test API Gateway-shaped invocations through Mangum using the local Lambda
  emulator or SAM, without deploying AWS resources.
- Coordinate container packaging with Role 3 because the shared deployment plan
  currently describes SAM ZIP packaging.

Complete when: the Lambda-compatible image handles a local API Gateway-shaped
request, and missing production inputs are explicitly reported rather than
silently replaced with test data.

## Part 12 - Evaluation, documentation and deployment handoff

Work:

- Perform explicit live evaluation and finalize models, prompts and image size.
  The README puts measurement first; this agreed build sequence defers final
  comparisons, but deployment suitability remains provisional until measured.
- Start with about 10 receipts and 5 grocery photos, including a long receipt.
  Compare available school models or configurations where practical.
- Complete the specified evaluation of 50 images and 20 spoken descriptions.
  Report precision, recall, quantity errors, non-food inclusion, confidence
  behavior, latency, usage, cost or quota consumption, and correction time.
- Target ingredient precision of at least 90% and assess the approximately
  10-second p95 synchronous-response target. If latency does not fit, report it
  before introducing a queue or changing the architecture.
- Hand off root `eval/image_set/` placement to the appropriate owner under the
  current `ai/`-only edit restriction. Do not package evaluation data into Lambda.
- Update `README.md` with implemented configuration, commands, limitations and
  outstanding dependencies.
- Document the image artifact, model settings, secret reference, catalogue path,
  IAM permissions, API Gateway integration and logging requirements for Role 3.

Complete when: evaluation results and deployment instructions are recorded, or
specific unresolved dependencies are clearly identified. An unresolved
requirement must not be reported as completed.

## Checks and external integration milestones

Run relevant focused tests during each part. Run the complete checks at integration
points and before handoff, from `ai/`:

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The production ingredient catalogue is owned by Role 2. Shared AWS resources and
deployment are owned by Role 3. Frontend and API contract changes are coordinated
with Role 1. These are external dependencies, not permission to edit their folders.

Actual deployment is a separate integration milestone: push the tested image to
ECR, create or update the image-based Lambda, configure API Gateway authentication
and routing, and verify school API access. One infrastructure tool must own each
resource; do not have SAM and Terraform independently manage the same resources.

The README's final project completion check remains a real receipt and a spoken
description becoming reviewed inventory updates on the deployed stack, plus an
accuracy table. Inventory confirmation goes through
`POST /api/inventory/items`; the AI Lambda never performs that database write.
