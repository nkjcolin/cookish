# Role 4 — AI-assisted input

You own assisted entry: turning a receipt photo, a grocery photo, or a typed or spoken list into draft items that the user reviews before anything reaches the kitchen. Read [docs/init.md](../docs/init.md) first for the conventions everyone follows.

The design is in [SPEC.md](../docs/SPEC.md), **B4**: the model options, the approach, and the evaluation.

This folder is a small FastAPI app of its own, deployed as the `ai` Lambda. It runs outside the VPC so it can reach the model provider, and it never touches the database. Locally it runs like any FastAPI app. On AWS, API Gateway sends `/ai/*` here and [Mangum](https://mangum.fastapiexpert.com/) converts the Lambda event into a normal request (`app/lambda_handler.py`). Nothing else in the code knows it is on Lambda.

## What you own

| Path | Contents |
|---|---|
| `ai/` | Everything in this folder |
| `ai/eval/` | Evaluation tooling, manifests and local test data |

## What already exists

The service supports an offline fake and the school's image-capable Chat Completions
API. Parts 1–11 of [implementation.md](implementation.md), with Part 8 revised
after identifier removal, now include all routes, request deadlines, local test
tools and Lambda container packaging. Part 12's evaluation runner and handoff
documentation exist; formal accuracy, final model choice and deployment acceptance
still require labelled data and live measurements. Nothing has been deployed to AWS.

Known limitation: live school-model checks have returned incorrect numeric
quantities even when the unit was preserved. Draft quantities require review;
passing software tests does not establish extraction accuracy. The formal
evaluation dataset and labels are still to be selected.

`laas.py` is a standalone script for testing the school model API. It
is never imported by the service and is excluded from Docker images. Local
`eval/data/` and `output/` folders are ignored by Git. Shared input copies are
published under [dataset/](dataset/README.md) and used by the default test paths.
Both datasets and local outputs are excluded from Docker images. Live uploads are
processed only in memory.

| Endpoint | Input | Output |
|---|---|---|
| `POST /ai/parse-image` | `kind` (`receipt` or `photo`), `media_type`, `image_base64` | `DraftResult`: a list of `DraftItem` |
| `POST /ai/parse-items` | `text`, `source` (`typed` or `voice`) | `DraftResult` |
| `POST /ai/interpret` (optional) | `text`, such as "something lighter" | `InterpretResult`: a `CookAdjust` |
| `POST /ai/transcribe-audio` | `media_type`, `audio_base64`, optional `language` | `TranscriptionResult`: `{"text": "..."}` |

## What you may change, and what you must keep

**Yours to decide:** the model and provider, the prompts, image handling, matching, and everything inside `app/` other than the two copied files.

**Keep:** request and error shapes and all response fields other than the
user-requested removal of `DraftItem.ingredient_id`. That AI-only change is pending
in the shared backend contract and frontend types (see below).
The user-requested audio transcription route is also an AI-owned addition pending
the shared OpenAPI export; the existing three route contracts remain checked.

## How the frontend uses you

- **Images** are compressed in the browser to a 1500-pixel long edge (`MAX_IMAGE_EDGE` in `frontend/src/lib/image.ts`) and sent as base64 in the request. They are never stored. Tell Role 1 if a different size works better for the model.
- **Voice** can use the existing browser Web Speech API, or a recording uploaded to
  `/ai/transcribe-audio`. Send either transcript to `/ai/parse-items` with
  `source: "voice"`. Recording/upload integration still belongs to the frontend
  owner. Expect recognition errors, especially on local food names.
- **Typed text** is sent to `/ai/parse-items` while the user types, so keep it fast.
- **Review.** Items with `confidence` under 0.6 are asked about individually in the review screen; the rest are shown as ready. Make the number honest.
- **Failure.** On `UPSTREAM_UNAVAILABLE` the frontend offers to try again or enter items by hand.

## Run it

Requires [uv](https://docs.astral.sh/uv/). `docker compose up` in the repository root also starts it, on port 8001.

```bash
cd ai
uv sync
uv run uvicorn app.main:app --reload --port 8001   # http://localhost:8001/ai/docs
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

To try it through the web app, start the frontend with `VITE_AI_PROXY_TARGET=http://localhost:8001`.

### Local testing with Docker

The following commands run from the **repository root**. Docker is sufficient;
you do not need to install Python 3.12 or uv on your host.

```bash
docker build -t cookish-ai:local ./ai
docker run --rm --name cookish-ai-local \
  -p 127.0.0.1:8001:8000 \
  -e AI_PROVIDER=fake \
  cookish-ai:local
```

Open <http://localhost:8001/ai/docs>. In another terminal:

```bash
python3 ai/scripts/test_local.py --text "a dozen eggs, two packs of tofu, some kangkong"
python3 ai/scripts/test_local.py --source voice --text "some kang kong and eggs"
python3 ai/scripts/test_local.py --image ai/dataset/receipt/fairprice-receipt.jpeg --kind receipt
python3 ai/scripts/test_local.py --image YOUR_GROCERY_PHOTO.jpeg --kind photo
python3 ai/scripts/test_local.py --interpret "less oily and ready in 20 minutes"
python3 ai/scripts/test_local.py --audio ai/dataset/audio/ingredients.wav
```

The image command uses a local sample if present; substitute your own compressed
JPEG, PNG or WebP. The helper uses only Python's standard library, sends one
request to your local API and never reads school credentials. Fake mode always
returns fixed items, so it tests wiring rather than recognition accuracy.

To use the school API, keep your existing `ai/.env` private and supply
`SOCLAAS_BASE_URL`, `SOCLAAS_MODEL` and `SOCLAAS_API_KEY`. See `.env.example` for
settings; do not overwrite an existing `.env` with the example. Stop the fake
container before starting the school-backed instance on the same port:

```bash
docker stop cookish-ai-local
docker run --rm --name cookish-ai-local \
  -p 127.0.0.1:8001:8000 \
  --env-file ai/.env \
  -e AI_PROVIDER=soclaas \
  -e SOCLAAS_TIMEOUT_SECONDS=20 \
  -e AI_REQUEST_TIMEOUT_SECONDS=27 \
  cookish-ai:local
```

The helper waits up to 45 seconds by default, longer than the normal 27-second
request budget. To explicitly choose a different client wait:

```bash
python3 ai/scripts/test_local.py --text "2 eggs" --timeout 35
python3 ai/scripts/test_local.py --image ai/dataset/receipt/fairprice-receipt.jpeg --timeout 35
```

The provider default is 20 seconds; the whole request, including one repair
attempt, defaults to 27 seconds. For deliberately slow local experiments only,
override both `SOCLAAS_TIMEOUT_SECONDS=60` and `AI_REQUEST_TIMEOUT_SECONDS=90`,
and use helper `--timeout 100`. This does not demonstrate AWS suitability; the
Lambda request budget is always capped at 27 seconds and by remaining invocation time.
Repeat the helper requests to exercise the real school endpoint. These calls use
school quota but create no AWS resources. View logs with
`docker logs -f cookish-ai-local`; stop with `docker stop cookish-ai-local`.

For slow local receipt experiments, use `-e SOCLAAS_TIMEOUT_SECONDS=60` and
`-e AI_REQUEST_TIMEOUT_SECONDS=90` in the Docker run command, with
`scripts/test_local.py --timeout 100`. The current local container uses these
testing overrides: a 12-item generated receipt took about 27 seconds with the
school model and private quantity evidence. Lambda still caps requests at 27
seconds; these overrides do not establish deployment latency acceptance.
AI drafts contain food names, not catalogue identifiers. Neither prompts nor the
live parsing pipeline load an ingredient CSV.

Run automated checks inside the image, mounting the API contract read-only:

```bash
docker run --rm \
  --mount "type=bind,source=$PWD/docs,target=/docs,readonly" \
  cookish-ai:local uv run --frozen pytest
docker run --rm cookish-ai:local uv run --frozen ruff check .
docker run --rm cookish-ai:local uv run --frozen ruff format --check .
```

The tests use mocked providers and make no school or AWS calls. The standalone
`laas.py` test script is excluded from application linting and packaging.

### Standalone receipt experiment

`laas.py` uses `app/prompts/receipt.md` in both batch modes, with the current
`DraftResult` public shape (no prices or ingredient IDs). It reads that file at run time;
there is no second hardcoded receipt prompt or catalogue lookup. It remains
separate from the FastAPI/Lambda app and does not apply the app's non-food filter.
Structured receipt helpers share the API's quantity normalization and defaults:
totals in their original measurement units, unknown measured amounts left null,
and a final null-unit
fallback to `pcs`. Generic `ask_image` helpers
still return the model's raw text without changing its fields.

`main()` at the bottom of `laas.py` has five numbered test blocks. Keep the call
for the one you want uncommented, comment out the others, then run the file. The
audio test is currently enabled, preserving your latest selected test.
No command-line arguments are used.

1. **Receipt images + prompt file:** uncomment `process_receipts_with_prompt()`.
   This is the existing function: it reads `app/prompts/receipt.md`, processes every
   image in `ai/dataset/receipt/` and saves/overwrites `ai/output/prompt.json`.
2. **Image + selected prompt file:** edit `image_path` and `prompt_name`, then use
   `print(ask_image_with_prompt_file(image_path, prompt_name))`. Set the name to
   `photo.md`, `receipt.md`, or any new prompt you add inside `ai/app/prompts/`.
   The `.md` extension is optional: `photo` also works. The file is read fresh on
   every call, regardless of your terminal's working directory. Missing/empty
   prompts fail before any API call, with available filenames shown for missing files.
3. **Custom image + inline prompt:** edit `image_path` and the multiline
   `custom_prompt`, then uncomment `print(ask_image(image_path, custom_prompt))`.
   Both single-image helpers return plain model text without forcing receipt JSON,
   adding receipt instructions or applying app cleanup. They print but do not save.
4. **Audio transcription:** set `SOCLAAS_AUDIO_MODEL` in `ai/.env` to the school's
   speech-to-text model ID, comment out the enabled image call and uncomment
   `print(transcribe_audio(audio_path))`. The supplied
   `dataset/audio/ingredients.wav` is a 3.86-second synthetic English shopping list.
   Edit `audio_path` to try your own recording. The helper uploads multipart audio
   to `/v1/audio/transcriptions` when `SOCLAAS_BASE_URL` ends in `/v1`, and returns
   transcript text. Optional keywords are `model`, `language`, `prompt` (transcription
   context) and `timeout`. It does not send the transcript to `/ai/parse-items`.
   The supplied WAV was verified against the configured school speech model;
   other models/codecs still need verification. No speech-model ID is hardcoded.
   The service now provides the separate `/ai/transcribe-audio` route
   described below; it does not import this script.
5. **Model catalogue and pricing:** comment out the active audio call and uncomment
   `print(json.dumps(list_models(), indent=2, ensure_ascii=False))`. It sends
   `GET /v1/models` with your base URL/key and retains the school's custom
   `soclaas` pricing and capability fields. No `SOCLAAS_MODEL` is required.

These functions read credentials from your private `ai/.env`; no Docker or running
local API is needed.

From the repository root:

```bash
conda run -n cookish python ai/laas.py
```

Use `script_dir / "dataset/grocery/your-image.jpg"` for a path relative to `ai/`, or
`Path("/absolute/path/to/image.jpg")` for any other location in the custom block.
Calls consume school quota when you uncomment a test.
Use `show_details=True` with `ask_image`, `ask_image_with_prompt_file` or
`transcribe_audio` to print the requested/returned model, response usage and
relevant billing/rate-limit headers before the answer. Missing usage/cost fields
remain null. The helpers keep returning plain answer/transcript text.
The default timeout is 180 seconds with no automatic retries. The helper still
accepts optional Python keywords `model` and `timeout` if you need them. Otherwise
`SOCLAAS_IMAGE_MODEL` takes precedence over `SOCLAAS_MODEL`. Supported formats are
JPEG, PNG, WebP and GIF; export HEIC images to JPEG first.

From a Python session started in `ai/`, with the `cookish` environment active:

```python
from laas import ask_image, ask_image_with_prompt_file

answer = ask_image("/path/to/your/image.jpg", "Your own instructions here")
print(answer)
print(ask_image_with_prompt_file("/path/to/your/image.jpg", "photo.md"))
```

The other batch helper `process_receipts()` remains available to call directly if
needed. The numbered calls in `main()` are the normal manual test switches.

`count` is the **total amount expressed in `unit`**, rather than a package count
paired with its contents' measurement unit. The model reads purchased packages
and contents per package from the full receipt block as separate numeric factors.
Python multiplies them once and preserves their measurement unit, including `kg`,
`g`, `l`, `ml` or `pcs`.
For example, two 280 g packs return
`count: 560, unit: "g"`; two 0.5 kg packs return `count: 1, unit: "kg"`;
one 1 L bottle returns `count: 1, unit: "l"`.
An explicitly printed total measured amount is used directly, without multiplying
it again. Code normalizes spelling (such as kilograms to `kg`) without rescaling
quantities. It does not derive quantities
from prices or re-parse `raw_text` with quantity regexes. Live tests found model
arithmetic unreliable even with a final prompt check.

If the model rescaled a measured amount despite the prompt, a narrow source-unit
check restores the single unambiguous measurement scale in `raw_text`, adjusting
the amount to that scale. It does not infer package counts or contents from text.
When several scales are printed, or no source measurement is available (including
food-photo drafts with null `raw_text`), it retains the extracted unit.

The school model's private `ExtractionResult` schema adds a `quantity` object
containing `factors` and their original `unit`. `app/quantities.py` calculates the
product, then removes that object. The app still exposes only `DraftResult` and
the same six public item fields. Generic LAAS helpers return raw model text;
use the structured receipt helpers or the API to test the calculated public result.

If no purchase count is printed, the prompt assumes one package internally and
uses its readable contents amount. Unknown contents retain a known package count
and explicit purchase unit, or a null measured amount for review. No pack sizes,
weights, densities or drained yields are guessed. Printed net contents remain
net contents; they do not establish a drained or cooked yield. Prefer a printed
drained amount for solids in liquid when available, and preserve that evidence.
When neither amount nor unit is identifiable, receipts keep the `1 pcs` fallback.
Unknown measured quantities stay null, rather than becoming 1 g or 1 ml. Invalid
non-positive/non-finite counts also stay null. Identifiable units survive; only
a null unit defaults to `pcs` after spelling normalization.

Quantities may precede or follow the description, appear in a quantity column,
or on associated continuation lines without a price or literal Qty label. The
prompt preserves all supporting evidence in `raw_text`, without adding calculated
totals. Layout interpretation and selecting the correct factors remain model
responsibilities and need evaluation. Text/photo prompts use the same convention when
evidence is available, with no receipt-specific missing-count or unit defaults.
Backend ingredient matching, countable batch creation and exact unit agreement
are still integration responsibilities; this service never writes stock.

From the repository root, install the locked dependencies and run the standalone
script or its offline checks. `uv sync` includes `openai` and `python-dotenv`:

```bash
cd ai
uv sync --frozen
uv run python laas.py  # run whichever test you uncommented in main()
uv run python scripts/test_laas.py  # offline checks, no model calls
```

Configure `SOCLAAS_BASE_URL`, `SOCLAAS_API_KEY` and `SOCLAAS_MODEL` in your local
`ai/.env` or process environment. The comments at the top of `laas.py` explain the
optional image-model override and which settings take precedence. Image paths
under `dataset/` use the shared fixtures; put private working inputs in `eval/data/`.

If explicitly called, the batch functions process supported files in `ai/dataset/receipt/`
and overwrite their corresponding output files. The custom-image test does not
run those functions or overwrite batch outputs.

The root Compose configuration still explicitly sets `AI_PROVIDER=fake`. Running
Compose alone does not enable the school client. Use the standalone commands
above for school testing; coordinate shared Compose changes with its owner.

### Inspecting school usage and advertised rates

A live check on 2026-10-26 found 19 entries (including aliases) in `/v1/models`.
Each entry's `soclaas` metadata supplied:

- `input_microdollars_per_million_tokens`
- `output_microdollars_per_million_tokens`
- `audio_microdollars_per_minute`

Divide a rate by 1,000,000 to convert microdollars to advertised dollars. For
example, the catalogue reported Qwen3-VL 32B rates of 0.104 dollars per million
input tokens and 0.416 per million output tokens, and Whisper Large v3 at
0.006 dollars per audio minute. Fetch current metadata with `list_models()`;
these are school-advertised rates, not OpenAI prices or a confirmed invoice.

Chat cost estimate in dollars:

```text
(input_tokens * input_microdollars_per_million_tokens
 + output_tokens * output_microdollars_per_million_tokens) / 1_000_000_000_000
```

Audio cost estimate in dollars:

```text
audio_seconds / 60 * audio_microdollars_per_minute / 1_000_000
```

The live chat response contained `usage.prompt_tokens`, `completion_tokens` and
`total_tokens`. The audio response contained only `text`, with no duration or
usage. Neither sampled POST response supplied cost/pricing fields or relevant
cost headers. A WAV's local duration can support an estimate (the 3.86-second
sample is about 0.000386 advertised dollars); minimum charges, rounding, currency
and whether rates represent billed spend or school quota need provider confirmation.
Keep actual billed cost unknown unless the provider supplies it. Image token
usage must come from the response, rather than counting just the text prompt.

For manual tests, select the model with the helper's `model=` keyword and enable
`show_details=True`. Capability metadata matters: speech models use the audio
endpoint, and only models advertising vision should receive image inputs.
The running app already exposes known chat counts in `X-AI-Input-Tokens` and
`X-AI-Output-Tokens`, alongside `X-AI-Model`; missing usage stays absent.
The service now calculates estimates automatically with `app/pricing.py`. Each
school client/runtime caches `/v1/models` for `SOCLAAS_PRICING_CACHE_SECONDS`
(default one hour). Pricing lookup uses the same credentials and HTTP operation
timeouts of at most one second, clipped to the remaining budget with a 0.25-second
reserve. Lookup time counts toward the shared request deadline. Short deadlines
skip the optional lookup. Failed lookups back
off for up to 30 seconds; expired rates are not reused. A concurrent refresh does
not block another request. Unknown rates leave costs unknown while parsing proceeds.
The reported model's rate is preferred; a requested alias can supply its own
rate only when its `alias_of` explicitly matches the reported model.

These response headers expose accounting without changing the result JSON:

| Header | Meaning |
|---|---|
| `X-AI-Input-Tokens`, `X-AI-Output-Tokens` | Complete reported token totals across model attempts; omitted when incomplete |
| `X-AI-Estimated-Cost` | Decimal estimated total across all attempts; omitted when any attempt is unpriced |
| `X-AI-Known-Estimated-Cost` | Known priced subtotal, including when the total is incomplete |
| `X-AI-Cost-Status` | `estimated`, `partial`, `unknown`, or explicit offline `fake` |
| `X-AI-Cost-Unit` | `provider_dollars`; the school's currency/billing terms are unconfirmed |
| `X-AI-Pricing-Fetched-At` | UTC timestamp of the last contributing rate snapshot |

The estimate includes invalid-JSON repair calls and known usage from unusable
provider answers. A timeout can hide consumption, so incomplete totals stay
unknown and any previous priced subtotal is marked partial. Zero is reported only
when the available usage/rates calculate zero, or for explicitly marked fake calls.

`model_call` JSON logs contain each attempt's tokens, estimate, duration source and
exact rate snapshot. `ai_request` logs contain request totals, known subtotals and
coverage. Aggregate **one event type** to avoid counting the same call twice.
The local test helper prints the accounting headers. Evaluation predictions retain
them; reports sum school estimates and show incomplete cost coverage separately.
Actual billed `cost` remains null. AWS Lambda, gateway and logging costs belong
to AWS billing and are excluded from these model estimates.

The gateway/platform owner must expose these headers through CORS when the
frontend reads responses across origins. No new database or AWS permission is
needed by this accounting code; use the normal public school API connection.

### Configuration

The app reads **process environment variables**, not `.env` files implicitly. Use
Docker's `--env-file` as above, or from `ai/` with host uv installed:

```bash
AI_PROVIDER=soclaas uv run --env-file .env uvicorn app.main:app --reload --port 8001
```

Restart the service after changing provider/model settings; the client is cached.
Paired wrapping quotes in environment-file values are accepted, including when
Docker preserves them, so an existing dotenv-style school configuration works.
Use a base URL such as `https://school-api.example/v1`, not a full
`/chat/completions` endpoint. HTTPS is required except for loopback mock servers.

| Variable | Default | Meaning |
|---|---|---|
| `AI_PROVIDER` | `fake` | `fake` or `soclaas`; missing school settings never fall back to fake |
| `SOCLAAS_BASE_URL` | Required for school | API base URL, without credentials or query parameters |
| `SOCLAAS_MODEL` | Required for school | Default hosted model |
| `SOCLAAS_IMAGE_MODEL` | Default model | Optional override for receipt/photo tasks |
| `SOCLAAS_TEXT_MODEL` | Default model | Optional override for typed/voice lists |
| `SOCLAAS_INTERPRET_MODEL` | Default model | Optional override for interpretation; final choice awaits testing |
| `SOCLAAS_AUDIO_MODEL` | None | Required for real transcription; no fallback to the image/text default |
| `SOCLAAS_API_KEY` | None | Local school credential; keep it outside code and images |
| `SOCLAAS_API_KEY_SECRET_ARN` | None | AWS alternative to a local key; set exactly one credential source |
| `SOCLAAS_OUTPUT_MODE` | `json_schema` | Structured output; explicitly choose `json_object` if the school endpoint lacks schema support |
| `SOCLAAS_MAX_OUTPUT_TOKENS` | `4096` | Output limit, from 1 to 16384; tune for long receipts during evaluation |
| `SOCLAAS_TIMEOUT_SECONDS` | `20` | HTTP read/write timeout; 60 can help slow local experiments, but does not fit the AWS budget; maximum 120 |
| `SOCLAAS_PRICING_CACHE_SECONDS` | `3600` | Model-rate cache lifetime per runtime; integer from 1 to 86400 |
| `AI_REQUEST_TIMEOUT_SECONDS` | `27` | Overall deadline across preparation, calls and validation retry; local maximum 120; Lambda cap 27 and remaining invocation time minus 1 second |

In AWS, grant the Lambda role read access to the specific Secrets Manager secret.
The secret can contain the raw API key or JSON with `SOCLAAS_API_KEY` or `api_key`.
AWS keys are retrieved lazily and cached for five minutes, then refreshed. Local
key and fake configurations do not contact AWS.

### Audio transcription

`POST /ai/transcribe-audio` accepts JSON, keeping uploads compatible with the
existing API Gateway/Lambda flow:

```json
{
  "media_type": "audio/wav",
  "audio_base64": "BASE64_FILE_BYTES_WITHOUT_A_DATA_URL_PREFIX",
  "language": "en"
}
```

It uploads multipart data to the school's `/audio/transcriptions` endpoint under
`SOCLAAS_BASE_URL` (normally ending in `/v1`), using `SOCLAAS_AUDIO_MODEL`,
`response_format=json` and the configured credential source. Model choice is
server-owned. `language` defaults to `en`; use another two-letter language code,
or `null` to omit it and let the provider detect the language. No prompt is sent.

The response is the provider's nonempty transcript, for example:

```json
{"text": "Four eggs, two hundred grams of rice, and four potatoes."}
```

The complete flow is recording → transcription → `/ai/parse-items` with
`{"source": "voice", "text": "..."}` → user review → backend inventory confirmation.
Transcription does not parse ingredients or change inventory. The text route's
existing 2000-character limit still applies; split longer transcripts before
submitting them there. Browser transcription remains supported as an alternative.

Audio bytes are limited to **3 MiB** and processed only in memory. Supported media
types are `audio/wav` (also `audio/x-wav`), `audio/mpeg`, `audio/webm`, `audio/ogg`,
`audio/mp4` (M4A/MP4) and `audio/flac`. Send the media type without codec parameters.
Base64 and container signatures are checked locally; full codec decoding is left
to the school provider. For cost estimation, provider-reported duration takes
priority; complete supported PCM WAV files can also be measured from their frames.
Other formats without provider duration retain unknown cost. Accepted codecs
depend on the provider. The bundled WAV sample is about 3.86 seconds; this is not
a duration limit. Client-supplied durations are not accepted for accounting.

Transcription uses the same overall deadline and clipped provider timeout as the
other routes. Empty/malformed responses, missing speech-model configuration and
provider failures return `503 UPSTREAM_UNAVAILABLE`, without an automatic retry.
Malformed uploads return `422 VALIDATION` before a school call. Logs contain
request/model/latency metadata, not audio bytes or transcript text. Missing speech
token usage remains unknown, even when a duration-based cost is available.
Explicit `AI_PROVIDER=fake` returns a fixed
sample transcript for offline testing; it is never a real-provider fallback.

### Image input and current limits

Send base64 bytes **without** a `data:` prefix, along with the actual media type.
The service checks base64, format, still-image content, complete decoding and
dimensions before contacting the school API. Uploads must be at most **3 MiB**,
with an edge at most 8192 pixels and at most 16 million pixels in total. The
browser's 1500-pixel resize remains the recommended starting point; actual byte
size still matters. Oversized, mismatched or corrupt uploads return `VALIDATION`
without echoing the image in the error details.

The provider defaults to 20-second HTTP timeouts, with at most 5-second connection/
pool timeouts and no automatic HTTP retries. HTTP timeouts are clipped to the
remaining request budget. Invalid model JSON gets at most one validation retry
within the same overall deadline, not a new timeout allowance. On expiry the API
returns `503 UPSTREAM_UNAVAILABLE`. Responses are buffered before sending headers
so expiry cannot leave a partial success response.

Synchronous provider work runs off the event loop. Deadline cancellation stops
waiting and discards its result; a synchronous HTTP call may finish in the
background until its own timeout. It does not cancel generation on the school's
server or guarantee quota is refunded. No inventory mutation is performed.

Each response has `X-Request-ID`; model responses also include `X-AI-Model`,
`X-AI-Provider`, `X-AI-Attempts` and known token-usage headers. Missing or timed-out
usage stays unknown, not zero. JSON logs correlate model attempts and total request
time without recording prompts, grocery text, images or API keys. An incoming
UUID request ID is accepted; arbitrary strings are replaced with a generated UUID.

Initial live checks also showed that the currently configured school model can
time out on text requests and exceed the approximately 10-second image target.
Use `SOCLAAS_TEXT_MODEL` to evaluate a suitable text model later; do not assume a
vision-model configuration meets the typed-entry latency requirement. Upstream
timeouts are returned as the documented 503 error rather than hidden with fake
results. Model choice and latency remain evaluation work.

Receipt cleanup removes clear non-food categories and grooming razors that the
model might mislabel as razor clams. It no longer re-parses `raw_text` with a
narrow quantity regex: positive finite counts and units from the model survive
cleanup, including leading, trailing, column and continuation-line quantities.
Python calculates totals from the model's private numeric factors. Missing unmeasured
purchase counts default to 1; unknown measured and invalid numeric counts remain
null. After unit spelling normalization, only a null unit defaults to `pcs`.
The prompt distinguishes package contents and prices from purchase quantity and
preserves supporting lines in `raw_text`. These are
model instructions, not independently verified OCR guarantees; recognition and
quantity accuracy still require live evaluation.

Common draft cleanup normalizes unit spellings, preserves measurement scale and
clears non-finite/non-positive counts after factor multiplication, without repeating
package arithmetic or
assigning identifiers. Receipt-only
defaults do not affect text or food-photo requests. All supported interpretation
fields and boundary checks have dedicated tests, including rejection of unsupported
fields and all-null/no-op results. Confidence calibration and inventory integration
still require labelled evaluation and backend integration. Before comparing
inventory against recipes, the backend must reconcile units such as kg and g;
the AI now preserves the receipt's original measurement scale.

## Layout

| Path | Contents |
|---|---|
| `app/main.py` | The four routes; no business logic |
| `app/lambda_handler.py` | Lambda entry point (`app.lambda_handler.handler`) |
| `app/parse.py` | The pipeline: prompt → model → validate (one retry) → receipt checks → draft |
| `app/model_client.py` | School API transport, model selection, usage extraction and offline fake |
| `app/config.py` | Validated server-side provider and model configuration |
| `app/credentials.py` | Local credentials or cached Secrets Manager retrieval |
| `app/images.py` | In-memory image validation before provider calls |
| `app/receipts.py` | Conservative non-food checks and receipt count/unit defaults |
| `app/quantities.py` | Private quantity evidence and deterministic factor multiplication |
| `app/drafts.py` | Unit spelling and numeric consistency, without catalogue matching |
| `app/runtime.py` | Shared deadlines, correlation headers and content-free request logs |
| `app/audio.py` | In-memory base64, size and audio-container validation |
| `app/pricing.py` | Cached model rates, decimal estimates and rate provenance |
| `app/matching.py` | Legacy catalogue utility; no longer called by the AI routes |
| `app/prompts/` | One prompt per task: `receipt`, `photo`, `items`, `interpret`. First drafts |
| `app/schemas.py` | Request and response shapes, copied from the backend |
| `app/errors.py` | The shared error format, copied from the backend |
| `tests/` | Contract check and pipeline tests with a scripted model |
| `scripts/test_local.py` | Standard-library helper for local text and image requests |
| `Dockerfile.lambda` | Production Lambda base image; runtime dependencies and app only |
| `scripts/test_lambda.py` | API Gateway-shaped local emulator invocations |
| `eval/` | AI-owned evaluation runner and example manifests; not production assets |
| `dataset/tools/` | Published dataset preparation, validation and macOS OCR helpers |
| `dataset/` | Curated receipts and provenance index, grocery images, sample audio, retail catalogue and reserved generation config folder |

Evaluation tooling lives in `ai/eval/`. Shared images in `ai/dataset/receipt/`
and `ai/dataset/grocery/` are intended for Git; local working copies under
`ai/eval/data/`, result folders, `ai/output/` and `ai/dataset/work/` remain ignored.
The four reference photos stay at the `dataset/receipt/` root, and all 30 selected
synthetic receipts remain in `dataset/receipt/generated/`. The curated index is
`dataset/receipt/manifest.json`. Batch records/galleries stay locally
under `dataset/work/receipts/20261024/`. The one-time
[retail catalogue](dataset/catalogs/README.md) covers all recipe ingredient names;
its prices were collected on 2026-10-28. Historical generation helpers are not yet
wired to this catalogue.
All dataset inputs and local outputs are excluded from Docker builds. The project specification's
root-level `eval/image_set/` remains a separate formal-dataset handoff location.

### Lambda image and evaluation

The separate [deployment handoff](DEPLOYMENT.md) contains production-image build
commands, read-only local Lambda emulator tests, runtime settings and the platform
owner's AWS checklist. Example, from the repository root:

```bash
python3 ai/scripts/build_lambda.py --arch arm64
docker run --rm --name cookish-ai-lambda-local --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  -p 127.0.0.1:9000:8080 -e AI_PROVIDER=fake cookish-ai:lambda
```

In another terminal:

```bash
python3 ai/scripts/test_lambda.py --text "2 eggs"
python3 ai/scripts/test_lambda.py --interpret "something quicker"
```

See [eval/README.md](eval/README.md) for the labelled-manifest format,
offline scoring, explicitly enabled model calls, confidence/quantity/latency
reports and incomplete-dataset gates. The AI-owned runner stays here to honor the
`ai/`-only edit restriction; the dataset owner must supply the final root-level
labelled set. No test images, labels or evaluation code enter the Lambda image.

## Provider integration

The school client sends Chat Completions requests directly with HTTPX; it does
not require an OpenAI account, import `laas.py`, or use the prototype's price
schema. Model JSON is validated by the shared pipeline. Token usage is logged as
`null` if the provider omits it, rather than fabricated as zero. Logs identify the
selected task model. Provider errors/refusals return `UPSTREAM_UNAVAILABLE` without
exposing credentials or school error bodies.

To add a different provider later:

1. In `app/model_client.py`, write a class with `model_id` and `generate(request) -> ModelReply`, using the provider's structured-output or JSON mode.
2. Raise `ModelUnavailable` on timeout (`TIMEOUT_SECONDS`), throttling or any provider error. The user then sees "try again or enter by hand".
3. Return the token counts in `ModelReply`; `parse.py` logs them with the latency as one JSON line per call, for the cost model.
4. Select it in `get_client()` with a new `AI_PROVIDER` value, and add the SDK to `pyproject.toml`.
5. Configure the credential source with Role 3. The school client supports a Secrets Manager reference; the deployment must grant access to that secret. Never commit a key.

Rules already enforced in code, whatever the model answers:

- The answer must validate against the schema, or it is retried once and then reported as `UPSTREAM_UNAVAILABLE`.
- AI drafts expose no `ingredient_id`; provider schemas and prompts do not request it.
- `/ai/interpret` can only return the fields of `CookAdjust`; an answer that tries to set allergens or diets is rejected.
- There is no freshness field in a draft, so the model cannot set one.

Receipt prompts are backed by conservative non-food checks and numeric/default cleanup.
Unrecognized non-food descriptions and OCR mistakes can still pass; measure these
in evaluation. Typed lists and grocery photos still rely on prompts for food
recognition and quantity evidence.

## Sharing the contract with the backend

The backend owns the API contract: `docs/openapi.json` is exported from `backend/app/schemas/`, and the frontend's types are generated from that file. `app/schemas.py` and `app/errors.py` here are copies, so that each Lambda is packaged on its own.

At the user's request, `DraftItem.ingredient_id` has been removed from both AI
extraction routes, the fake provider, the school output schema and all extraction
prompts. `confidence` now describes confidence in the food identification, not
catalogue matching. This is a breaking response change relative to the current
shared contract; frontend code must not assume this property exists.

`tests/test_contract.py` compares the full AI contract while allowing precisely
this approved field removal and the added `/ai/transcribe-audio` route. The original
three routes still undergo full comparison. It does not claim exact shared-contract parity.
Role 1 still needs to remove the field from the backend schema, re-export
`docs/openapi.json`, regenerate frontend types and adapt review/confirmation logic.
Those files are outside the `ai/`-only edit scope. All other contract differences
remain test failures. Normal future changes follow the shared export workflow.
The shared-contract owner also needs to export `TranscribeAudioRequest`,
`TranscriptionResult` and the new audio route, regenerate frontend types, and wire
recording/upload → transcription → voice parsing if server transcription is used.

`backend/app/services/ai_stub.py` answers `/ai/*` with the same fixed items when the backend runs on its own without this service.

## The ingredient catalogue

For synthetic receipt generation, `dataset/catalogs/ingridients.json` contains a
frozen 2026-10-28 FairPrice snapshot: 41 products covering all 42 ingredient names
from 48 backend recipes, with tap water excluded. It records real product names,
retailer stock descriptions, pack quantities, prices, source URLs and source
recipe hashes. Cabbage head mass and chickpea drained mass remain explicitly
unverified. See the [catalogue guide](dataset/catalogs/README.md) and validate
offline with `python3 ai/dataset/tools/validate_ingredient_catalog.py` from the
repository root. Reusable generation/selection integration remains future work.

The extraction routes no longer load a catalogue or resolve IDs. The legacy
`app/matching.py` utility and fixture CSV remain for reference, not live parsing.
Coordinate any required name-to-inventory matching with the backend owner; this
service still never writes inventory. Historical saved experimental outputs are
not rewritten by code edits and may reflect the previous response contract.

## Tasks, in order

1. **Measure.** Run about ten real receipts, including a long one, and five grocery photos through two or three candidate models. Record latency, accuracy and cost per call. The architecture assumes a synchronous call that returns in about 10 seconds at p95; if it does not, raise it with the group, because the fallback is a queue and a background worker.
2. From that, choose the model and the image size.
3. Add the model as a client in `app/model_client.py` (above), and improve the prompts in `app/prompts/`.
4. Evaluate non-food exclusion, total-quantity arithmetic and unit extraction.
   Unknown measured amounts stay null; receipts default to 1/`pcs` only for
   unmeasured purchases. Text/photo unknown quantities remain null. Code guards
   do not replace recognition evaluation.
5. With Role 3: model credentials and deployment configuration. The AI extraction
   pipeline no longer needs `ingredients.csv` bundled into its package.
6. Collect the evaluation set in `eval/image_set/`: 50 images (about 30 receipts, 20 grocery photos) and 20 spoken descriptions, with hand labels. Report precision, recall, time and cost per image; if time allows, compare two model sizes.

**Done when** a phone photo of a real receipt and a spoken description each become a reviewed inventory update on the deployed stack, and the accuracy table exists.
