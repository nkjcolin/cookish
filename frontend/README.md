# frontend

React web app (Role 1): Vite, TypeScript, Tailwind CSS, TanStack Query and React Router.

## Run it

Requires Node 22 or newer and [pnpm](https://pnpm.io/). Start the backend first (see `../backend/README.md`); the dev server forwards `/api` and `/ai` to `http://localhost:8000`.

```bash
pnpm install
pnpm dev          # http://localhost:5173
pnpm test
pnpm typecheck && pnpm lint
pnpm build
```

## Talking to the backend

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
