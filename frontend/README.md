# Role 1 — Frontend and API contract

You own what the user sees and the contract every other role builds against: the web app, the API's request and response shapes, and the thin layer that connects HTTP to the services. Read [docs/init.md](../docs/init.md) first for the conventions everyone follows.

The design is in [SPEC.md](../docs/SPEC.md): **A7** for the API, **B1** for your brief, **A10** for the user study.

## What you own

| Path | Contents |
|---|---|
| `frontend/` | The React web app: Vite, TypeScript, Tailwind CSS, TanStack Query, React Router |
| `backend/app/schemas/` | The API contract, as Pydantic models |
| `backend/app/routers/`, `backend/app/main.py` | Thin HTTP handlers, one service call each |
| `backend/app/errors.py`, `auth.py`, `clock.py`, `deps.py` | Shared backend plumbing |
| `backend/app/mock.py` | The local development user and demo data; not served on AWS |
| `docs/openapi.json` | Generated from the schemas; never edited by hand |
| `eval/user_study/` | Protocol, consent sheet, task script and results |

## What already exists

Kitchen improvements implemented in this branch:

- My Kitchen's search opens a focused input and filters loaded ingredient names,
  combining case-insensitive partial matching with the existing storage/status filters.
- Receipt/photo review can enlarge the uploaded photo. Clicking the backdrop, Close or
  Escape dismisses it; clicking the photo keeps it open. A bounded browser-memory cache
  retains previews through processing. Confirming the draft releases its preview.
  Reloading the tab clears photo previews; acknowledged jobs and extracted drafts still work.
- Kitchen History can edit the current remaining quantity or remove an individual batch.
  Actions fetch the latest inventory revision and use the existing PATCH/DELETE APIs.
  Changes create new reversible events; original submissions stay unchanged. Editing a
  history item never changes another batch of the same ingredient. History, inventory
  and recipe/shop caches refresh after corrections, removals and undo.
- Bare rice now aliases uncooked rice in the seeded catalogue. Cooked rice and rice
  vermicelli remain distinct. This fixes future exact-name links; existing free-text
  rice entries need a separate confirmed correction.

The history controls add no backend endpoint or database schema. The only backend
change for these improvements is the catalogue alias and its regression test.

- **The contract**: 25 endpoints, all backed by real logic.
- **Every screen** of the Figma design, plus kitchen history, working against the real API (see Screens below).
- **The behaviours agreed with Roles 2 and 5**, already built:
  - *Quick check.* Each question carries the batch it is about (`StockCheck.item`, `FreshnessCheck.item`), and the answer updates that batch with `PATCH`.
  - *"No, I don't have it"* records the batch as `out`, then asks for the next dish.
  - *Removing a condition.* Adjustments only add, so the app starts a new session with the remaining conditions; **Reset** starts one with none.
  - *Nothing fits.* `NO_RESULT` shows what can be relaxed; only `max_minutes` and `tags` are understood.
  - *Expired sessions.* Sessions last 12 hours. On `NOT_FOUND`, the app starts a new session with the same conditions (`src/api/cook.ts`, `src/api/shop.ts`).
- **`backend/app/auth.py`** reads the Cognito claims on AWS; locally it is a fixed development user.

## What other roles expect from you

- **A stable contract.** Others change it only through you; the procedure is in `docs/init.md`.
- **Sign-in.** Role 3 provides a Cognito user pool. The app signs in with `aws-amplify` and sends the **ID token** as `Authorization: Bearer …` on every request, including `/ai/*`.
- **The API address.** In production the app calls API Gateway directly at `VITE_API_URL`; `src/api/client.ts` already uses it when set. Role 3 sets it, with `VITE_COGNITO_USER_POOL_ID` and `VITE_COGNITO_CLIENT_ID`, in Amplify's build settings.

## Tasks, in order

1. Get the first CI run green once the pull request is opened.
2. Test photo capture and voice input on a real phone; neither could be exercised in the development browser.
3. Sign-in, once Role 3 has the user pool: a sign-in screen, and the ID token attached in `src/api/client.ts`.
4. Keep the contract in step as other roles ask for changes.
5. The user study: protocol, consent sheet, task script, and the comparison condition, a plain filterable recipe list, which is not built yet.
6. Timing instrumentation before the study: time to "Cook this", number of taps.

---

## Run it

Requires Node 22 or newer and [pnpm](https://pnpm.io/). Start the backend first (see `../backend/README.md`); the dev server forwards `/api` and `/ai` to `http://localhost:8000`. To send `/ai` to a separately running ai service instead, set `VITE_AI_PROXY_TARGET` (for example `http://localhost:8001`).

```bash
pnpm install
pnpm dev          # http://localhost:5173
pnpm test
pnpm typecheck && pnpm lint
pnpm build
```

## Talking to the backend

Receipt and grocery uploads now use POST /ai/image-jobs followed by short status polls.
The loading screen stays active while the separate worker calls the school model.
A pending job ID/kind is kept in session storage to resume a same-tab reload; completed
items still require the existing review/confirmation before inventory changes.
For local image testing, point VITE_AI_PROXY_TARGET at the AI service and start its
separate worker as described in [ai/IMAGE_JOBS.md](../ai/IMAGE_JOBS.md). Backend-only
development returns a clear 503 for these contract declarations.

`src/api/schema.d.ts` is generated from `../docs/openapi.json`. Regenerate it whenever the contract changes:

```bash
pnpm gen:api
```

All calls go through the typed client in `src/api/client.ts`, so paths, request bodies and responses are checked at compile time:

```ts
import { api, idempotencyKey, unwrap } from "./api/client";

const inventory = unwrap(await api.GET("/api/inventory"));

const change = unwrap(
  await api.PATCH("/api/inventory/items/{item_id}", {
    params: { path: { item_id: item.id }, header: idempotencyKey() },
    body: { revision: item.revision, remaining_state: "low" },
  }),
);
```

- `unwrap` returns the data or throws an `ApiError` carrying the backend's error `code`, such as `STALE_REVISION`.
- Requests that change inventory need `idempotencyKey()`. Create it once per user action and reuse it when retrying.
- TypeScript is pinned to 5.9: the client generator and the linter do not support TypeScript 7 yet.

## Screens

Every screen comes from the Figma file "Cookish – User Flow Demo". Where the design and the
API contract disagreed, the contract won, so some elements of the design are not built.

| Route | Screen | Design frames |
|---|---|---|
| `/onboarding` | Welcome, hard rules, cooking habits | A1–A3 |
| `/cook` | Suggestion, adjust, quick check, rating, nothing fits | B1–B4, B7, B8 |
| `/cook/recipe` | Recipe and "what's left?" | B5, B6 |
| `/buy` | Shopping list, meals, adjust basket | C1–C4 |
| `/buy/confirm` | Confirm purchase | C5, C6 |
| `/more` | More | D1 |
| `/more/add`, `/more/add/review` | Add ingredients, review a receipt or photo | D2, D3 |
| `/more/kitchen` | My Kitchen and the update sheet | D4, D5 |
| `/more/preferences` | Preferences | D6 |
| `/more/history` | Kitchen history and undo | no design |

## Layout

| Path | Contents |
|---|---|
| `src/api/` | Generated types, typed client, query hooks |
| `src/assets/icons/` | SVGs exported from the Figma file; use them through `components/Icon.tsx`, do not redraw them |
| `src/index.css` | Design tokens (colours, radii, font) from the Figma file |
| `src/components/` | Shared components and the app layout |
| `src/pages/` | One file per screen; `pages/<area>/` holds its sheets and the pure logic (`view.ts`) with tests |
| `src/lib/` | Labels for the contract's vocabularies, image compression, speech, router hand-over state |
