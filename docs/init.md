# Cookish — where the project stands and what each role does next

Written 13 October 2026, at the end of the initial setup (branch `danielsu/init`). Read Part 1, then your own section in Part 2. The design decisions behind all of this are in [SPEC.md](SPEC.md).

---

## Part 1 — For everyone

### What exists now

The whole app runs locally and every screen works, but **nothing behind the API is real yet**. The backend answers every request with fixed sample data. Your work is to replace that sample data with the real thing, one function at a time, without changing the shape of what is returned.

| Part | State |
|---|---|
| API contract | Complete. 25 endpoints, defined in `backend/app/schemas/` and exported to [openapi.json](openapi.json) |
| Backend | Every endpoint answers with sample data from `backend/app/mock.py`. No database code, no real logic |
| Frontend | Complete against the contract: all 24 screens of the Figma design plus a kitchen-history screen |
| AI service (`ai/`) | Empty. `/ai/*` is answered by a stand-in inside the backend |
| Infrastructure (`infra/`) | Empty. Nothing is deployed to AWS |
| Evaluation (`eval/`) | Empty folders |
| CI | A GitHub Actions workflow exists but has not run yet; expect to fix small things on its first run |
| Local stack | `docker compose up` starts frontend, backend and an empty Postgres |

### Run it

With Docker:

```bash
docker compose up
```

- Web app: http://localhost:5173 (open it at phone width)
- API and interactive docs: http://localhost:8000/api/docs
- Postgres: `postgres://cookish:cookish@localhost:5432/cookish`

Without Docker, see [backend/README.md](../backend/README.md) (needs `uv`) and [frontend/README.md](../frontend/README.md) (needs Node 22+ and `pnpm`).

### How the backend is laid out

A request passes through three layers, and each role owns a different one:

```
routers/   thin HTTP handlers            Role 1 — do not edit
   │  calls exactly one function in
services/  business logic                Roles 2 and 5 — replace the function bodies
   │  today returns
mock.py    fixed sample data             disappears as services become real
```

- **Keep every service function's name, parameters and return type.** The routers and the frontend depend on them.
- `backend/tests/test_contract.py` calls every endpoint and must keep passing.
- Raise `ApiError` for failures (see `backend/app/errors.py`); never build an error response by hand.
- The caller comes from `backend/app/auth.py`, which for now always returns one development user.

### If the contract has to change

It will, and that is fine, but it changes the frontend's generated types, so:

1. Agree the change with Role 1 first.
2. Edit `backend/app/schemas/`, then run `uv run python scripts/export_openapi.py` in `backend/`.
3. Run `pnpm gen:api` in `frontend/` and fix what the type checker reports.
4. Commit all three together. CI fails if `docs/openapi.json` or the generated types are out of date.

### Things the stubs do on purpose

So that the frontend could be built, the sample data is not neutral. Do not be surprised by:

- A kitchen with two batches of eggs, cabbage that is running low, chicken past its estimated date, and rice of unknown stock.
- `POST /api/cook/sessions/{id}/adjust` returning `NO_RESULT` whenever the time limit is under 20 minutes.
- Nothing being remembered: add an item and the kitchen still shows the same seven ingredients.
- `/ai/parse-image` and `/ai/parse-items` always returning the same three items, one of them with low confidence.

### Decisions that differ from what you may expect

- **Stock has four states**: `enough`, `low`, `out`, `unknown`. Countable ingredients carry a count instead.
- **Ratings happen only after cooking.** Before cooking there is "Not tonight" and "Cook this".
- **There are no prices and no budget anywhere.**
- **Images are never stored.** The browser compresses a photo and sends it in the request.
- **Suggestions carry no reason text.**
- **One deployed environment**, no separate production.

### Open questions for the kickoff meeting

These were found while building the frontend. Each is currently worked around on the client.

| Question | Affects | Current workaround |
|---|---|---|
| An adjustment can only add constraints. How does a user drop one? | Role 5 | The frontend starts a new session and resends the rest |
| The user answers "No, I don't have it" in the quick check. What should happen? | Roles 2, 5 | Recorded as `out`, then the next suggestion is requested |
| An ingredient has several batches. Which does "update this item" change? | Role 2 | The batch to use first |
| How does the `ai` Lambda reuse the request and response definitions? | Roles 1, 4 | They live in `backend/app/schemas/ai.py`; nothing shares them yet |
| Which AWS account, and is it a restricted Learner Lab account? | Role 3, everyone | Unknown |
| Which model provider? | Role 4 | Unknown |

### Working agreements

- `main` is protected. Branch as `<name>/<topic>`, open a pull request, one reviewer, checks green.
- The repository is public: no credentials, account details or course materials.
- Declare AI use; the final report needs where, how and what was learnt.

---

## Part 2 — Next steps by role

### Role 1 — Frontend and contract (Su Yubo)

Done: contract, stubs, all screens, local stack, CI file.

Next:

1. Get the first CI run green after the pull request is opened.
2. Test photo capture and voice input on a real phone. Neither could be exercised in the development browser.
3. Sign-in. The app has no sign-in screen and sends no token; add Cognito through `aws-amplify` once Role 3 has a user pool, and attach the JWT in `frontend/src/api/client.ts`.
4. Keep the contract in step as other roles ask for changes (procedure in Part 1).
5. Prepare the user study: protocol, consent sheet, task script, and the plain filterable recipe list that serves as the comparison condition. That baseline view is not built yet.
6. Add timing instrumentation (time to "Cook this", number of taps) before the study.

### Role 2 — Database and inventory services

You own `backend/app/db/`, `backend/migrations/`, `backend/seed/` and these service files:

| File | Functions to make real |
|---|---|
| `services/identity.py` | `get_me`, `save_preferences` |
| `services/catalogue.py` | `search_ingredients` |
| `services/inventory.py` | `list_inventory`, `add_items`, `update_item`, `delete_item` |
| `services/stock_events.py` | `list_events`, `undo_event`, `apply_stock_event`, `get_inventory_snapshot` |

Next, in this order:

1. **Publish the two internal signatures first.** `apply_stock_event` and `get_inventory_snapshot` currently raise `NotImplementedError`, and Role 5 cannot write real Cook or Shop logic until their shapes are fixed. Decide what `lines` looks like and what the snapshot returns, even before the bodies work.
2. Add SQLAlchemy, Alembic and a Postgres driver to `backend/pyproject.toml`; write models and the first migration from SPEC A6. `DATABASE_URL` is already set in `docker-compose.yml`.
3. Make the backend container migrate and seed on start, so `docker compose up` gives everyone the same data.
4. Write `seed/ingredients.csv` with **fixed UUIDs in the file**, because the `ai` Lambda bundles the same file. Take the ingredient list from Role 5's recipes.
5. Seed a demo household that matches the kitchen in `backend/app/mock.py`. Then the frontend looks the same when a stub is replaced.
6. Replace the stubs. Start with `get_me` and `list_inventory`, then the write path through `apply_stock_event`: idempotency key, revision check, before and after snapshots, undo.
7. Compute `freshness_status` and `est_use_first_date` on read. The frontend shows them as given.
8. Write the reliability tests in SPEC A10: repeated keys, concurrent edits, undo after a later edit, cross-household access.
9. Replace `backend/app/auth.py` with Role 3 once Cognito exists: read the verified claims, look up the household.

You are also the editor of the final report and slides.

### Role 3 — Cloud platform, delivery and cost

You own `infra/` and `.github/workflows/`. Nothing is deployed yet.

Next:

1. **Today: find out what the AWS account allows.** Can it create IAM roles? Are Cognito, Amplify, API Gateway, RDS and Bedrock available in `ap-southeast-1`? Write the answer in `infra/README.md`. Every other choice depends on it.
2. Write the SAM template for the walking skeleton: VPC with private subnets, RDS, the `api` Lambda, an HTTP API with a Cognito JWT authorizer, and a route for `/ai/*`.
   - The Lambda entry point already exists: `app.lambda_handler.handler` in `backend/`.
   - `api` goes in the VPC and needs no internet access; `ai` stays outside the VPC.
3. Connect Amplify Hosting to the repository for `frontend/`, with a rewrite of all non-file paths to `/index.html`. The frontend expects `/api` and `/ai` on its own origin, or `VITE_API_URL` set at build time.
4. Create the Cognito user pool and give Role 1 the pool and client IDs.
5. Extend `.github/workflows/ci.yml` with a deploy job on merge to `main`, using GitHub OIDC rather than stored keys.
6. CloudWatch dashboard and alarms; an AWS Budgets alert that reaches the whole group.
7. Later: the k6 load test, and the on-premise versus cloud cost comparison, which the project specification requires.

Until step 2 is done, everyone develops against `docker compose up`.

### Role 4 — AI-assisted input

You own `ai/`, which is empty. The backend currently answers for you from `backend/app/services/ai_stub.py`; read it and `backend/app/schemas/ai.py` to see exactly what the frontend sends and expects.

| Endpoint | Input | Output |
|---|---|---|
| `POST /ai/parse-image` | `kind` (`receipt` or `photo`), `media_type`, `image_base64` | `DraftItem[]` |
| `POST /ai/parse-items` | `text`, `source` (`typed` or `voice`) | `DraftItem[]` |
| `POST /ai/interpret` (optional) | `text` | a `CookAdjust` |

Next:

1. **This week: measure.** Run about ten real receipts, including a long one, and five grocery photos through two or three candidate models. Record latency, accuracy and cost per call. The architecture assumes a synchronous call that returns within about 10 seconds; if it does not, raise it with the team.
2. From that, fix two numbers that are still open: the model, and the image size. The frontend compresses to a 1500-pixel long edge in `frontend/src/lib/image.ts`; tell Role 1 if that should change.
3. Build the `ai` Lambda with the three endpoints. Use structured output and validate it; return `null` for a count that is not visible; never infer freshness from a photo; drop non-food lines.
4. Match against `backend/seed/ingredients.csv` once Role 2 has written it, and return `ingredient_id: null` when unsure. Items with confidence under 0.6 are asked about in the review screen.
5. Return `UPSTREAM_UNAVAILABLE` on timeout or model failure; the frontend then offers retry and manual entry.
6. Log model, tokens and latency per call, so Role 3 can cost it.
7. Decide with Role 1 how your Lambda shares the definitions in `backend/app/schemas/ai.py`.
8. Collect the evaluation set: 50 images and 20 spoken descriptions with hand labels, in `eval/image_set/`.

### Role 5 — Recommendation algorithms and recipes

You own `backend/app/reco/`, `backend/seed/recipes/` and these service files:

| File | Functions to make real |
|---|---|
| `services/cook.py` | `start_session`, `adjust`, `next_suggestion`, `previous_suggestion`, `select`, `confirm`, `give_feedback`, `get_recipe`, `set_star`, `use_first` (optional) |
| `services/shop.py` | `start_session`, `adjust`, `confirm_basket` |

Next:

1. **Start with the recipes**, because Role 2's ingredient list comes from them. 40 to 60 recipes in `seed/recipes/*.yaml`, using only the taste tags, cuisines, equipment and diet values in `backend/app/schemas/common.py`. You own the taste-tag list; change it if it does not fit, through the contract procedure.
2. Write `reco/` as pure functions with no database imports: filter, score, suggest, adjust, build a basket, estimate use-first. You can do all of this with fixture data, before Role 2 is ready.
3. Implement the freshness gate from SPEC B5: a batch past its date is never promoted; it is checked or excluded.
4. Fill `needs_check` and `freshness_check` on a suggestion. The frontend asks about exactly those before cooking.
5. Return `NO_RESULT` with `relaxable` when nothing fits. The frontend understands `"max_minutes"` and `"tags"` in that list; tell Role 1 if you add others.
6. Wire the service functions to sessions and to Role 2's `get_inventory_snapshot` and `apply_stock_event` once their signatures are published.
7. Answer the first two open questions in Part 1; both are yours to decide.
8. Write the 100 evaluation scenarios in `eval/reco_scenarios/`, keeping 30 unseen during development.

You also own the business case and pricing section of the final report.
