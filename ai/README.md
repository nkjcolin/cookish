# Role 4 — AI-assisted input

You own assisted entry: turning a receipt photo, a grocery photo, or a typed or spoken list into draft items that the user reviews before anything reaches the kitchen. Read [docs/init.md](../docs/init.md) first for the conventions everyone follows.

The design is in [SPEC.md](../docs/SPEC.md), **B4**: the model options, the approach, and the evaluation.

This folder is a small FastAPI app of its own, deployed as the `ai` Lambda. It runs outside the VPC so it can reach the model provider, and it never touches the database. Locally it runs like any FastAPI app. On AWS, API Gateway sends `/ai/*` here and [Mangum](https://mangum.fastapiexpert.com/) converts the Lambda event into a normal request (`app/lambda_handler.py`). Nothing else in the code knows it is on Lambda.

## What you own

| Path | Contents |
|---|---|
| `ai/` | Everything in this folder |
| `eval/image_set/` | The labelled test set and the script that scores it |

## What already exists

The whole pipeline works, but the model is a fake that always gives the same three items. Choosing and wiring a real model is the main work left.

| Endpoint | Input | Output |
|---|---|---|
| `POST /ai/parse-image` | `kind` (`receipt` or `photo`), `media_type`, `image_base64` | `DraftResult`: a list of `DraftItem` |
| `POST /ai/parse-items` | `text`, `source` (`typed` or `voice`) | `DraftResult` |
| `POST /ai/interpret` (optional) | `text`, such as "something lighter" | `InterpretResult`: a `CookAdjust` |

## What you may change, and what you must keep

**Yours to decide:** the model and provider, the prompts, image handling, matching, and everything inside `app/` other than the two copied files.

**Keep:** the request and response shapes, which are part of the API contract (`app/schemas.py`, `app/errors.py`, see below), and the columns you read from `ingredients.csv`.

## How the frontend uses you

- **Images** are compressed in the browser to a 1500-pixel long edge (`MAX_IMAGE_EDGE` in `frontend/src/lib/image.ts`) and sent as base64 in the request. They are never stored. Tell Role 1 if a different size works better for the model.
- **Voice** is transcribed in the browser with the Web Speech API; you receive the transcript as text with `source: "voice"`. Expect recognition errors, especially on local food names.
- **Typed text** is sent to `/ai/parse-items` while the user types, so keep it fast.
- **Review.** Items with `confidence` under 0.6 are asked about individually in the review screen; the rest are shown as ready. Make the number honest.
- **Failure.** On `UPSTREAM_UNAVAILABLE` the frontend offers to try again or enter items by hand.

## Run it

Requires [uv](https://docs.astral.sh/uv/). `docker compose up` in the repository root also starts it, on port 8001.

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8001   # http://localhost:8001/ai/docs
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

To try it through the web app, start the frontend with `VITE_AI_PROXY_TARGET=http://localhost:8001`.

| Variable | Default | Meaning |
|---|---|---|
| `AI_PROVIDER` | `fake` | Which model client to use; only `fake` exists so far |
| `INGREDIENTS_CSV` | `../backend/seed/ingredients.csv` | The ingredient catalogue. If missing, every item is returned unmatched |

## Layout

| Path | Contents |
|---|---|
| `app/main.py` | The three routes; no logic |
| `app/lambda_handler.py` | Lambda entry point (`app.lambda_handler.handler`) |
| `app/parse.py` | The pipeline: prompt → model → validate (one retry) → check ids → draft |
| `app/model_client.py` | The only code that talks to the model provider. Holds the fake |
| `app/matching.py` | Loads the catalogue; keeps an `ingredient_id` only if it exists, else matches by name or alias |
| `app/prompts/` | One prompt per task: `receipt`, `photo`, `items`, `interpret`. First drafts |
| `app/schemas.py` | Request and response shapes, copied from the backend |
| `app/errors.py` | The shared error format, copied from the backend |
| `tests/` | Contract check and pipeline tests with a scripted model |

Evaluation scripts and the labelled image set belong in `eval/image_set/` at the repository root, not here, so they are not packaged into the Lambda.

## Adding the real model

1. In `app/model_client.py`, write a class with `model_id` and `generate(request) -> ModelReply`, using the provider's structured-output or JSON mode.
2. Raise `ModelUnavailable` on timeout (`TIMEOUT_SECONDS`), throttling or any provider error. The user then sees "try again or enter by hand".
3. Return the token counts in `ModelReply`; `parse.py` logs them with the latency as one JSON line per call, for the cost model.
4. Select it in `get_client()` with a new `AI_PROVIDER` value, and add the SDK to `pyproject.toml`.
5. How the Lambda gets model credentials is not decided yet; settle it with Role 3 once the provider is chosen. Never commit a key.

Rules already enforced in code, whatever the model answers:

- The answer must validate against the schema, or it is retried once and then reported as `UPSTREAM_UNAVAILABLE`.
- An `ingredient_id` that is not in the catalogue is replaced by a name or alias match, or by `null`.
- `/ai/interpret` can only return the fields of `CookAdjust`; an answer that tries to set allergens or diets is rejected.
- There is no freshness field in a draft, so the model cannot set one.

Dropping non-food lines and leaving `count` as `null` when it is not visible are still only asked for in the prompts.

## Sharing the contract with the backend

The backend owns the API contract: `docs/openapi.json` is exported from `backend/app/schemas/`, and the frontend's types are generated from that file. `app/schemas.py` and `app/errors.py` here are copies, so that each Lambda is packaged on its own.

`tests/test_contract.py` checks that the `/ai` endpoints this app serves, and every schema they use, are identical to `docs/openapi.json`. To change the contract: agree it with Role 1, change the backend and re-export the contract (see `backend/README.md`), then copy the change here until the test passes.

`backend/app/services/ai_stub.py` answers `/ai/*` with the same fixed items when the backend runs on its own without this service.

## The ingredient catalogue

`backend/seed/ingredients.csv` is written by Role 2, in the format in [backend/seed/README.md](../backend/seed/README.md), and bundled read-only with this Lambda by Role 3. `app/matching.py` reads three of its columns: `id`, `canonical_name`, and `aliases` separated by `|`. Until the file exists, every item comes back unmatched.

Local product names seen on receipts that do not match ("kangkong", "tau kwa") should go back to Role 2 as aliases.

## Tasks, in order

1. **Measure.** Run about ten real receipts, including a long one, and five grocery photos through two or three candidate models. Record latency, accuracy and cost per call. The architecture assumes a synchronous call that returns in about 10 seconds at p95; if it does not, raise it with the group, because the fallback is a queue and a background worker.
2. From that, choose the model and the image size.
3. Add the model as a client in `app/model_client.py` (above), and improve the prompts in `app/prompts/`.
4. Two rules are so far only asked for in the prompts: drop non-food lines, and leave `count` as `null` when it is not visible. Check them in the evaluation, and enforce them in code if the model does not follow them.
5. With Role 3: model credentials, and bundling `ingredients.csv` into the Lambda package.
6. Collect the evaluation set in `eval/image_set/`: 50 images (about 30 receipts, 20 grocery photos) and 20 spoken descriptions, with hand labels. Report precision, recall, time and cost per image; if time allows, compare two model sizes.

**Done when** a phone photo of a real receipt and a spoken description each become a reviewed inventory update on the deployed stack, and the accuracy table exists.
