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

## Layout

| Path | Contents |
|---|---|
| `src/api/` | Generated types, typed client, query hooks |
| `src/components/` | Shared components and the app layout |
| `src/pages/` | One file per screen |
