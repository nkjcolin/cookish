import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

/** Typed client for the whole contract. Regenerate the types with `pnpm gen:api`. */
export const api = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL ?? "",
});

export type Schemas = components["schemas"];

/**
 * Header for requests that change inventory. Create it once per user action and reuse
 * the same value when retrying, so a repeated tap never applies the change twice.
 */
export function idempotencyKey(): { "Idempotency-Key": string } {
  return { "Idempotency-Key": crypto.randomUUID() };
}

export class ApiError extends Error {
  readonly code: Schemas["ErrorCode"];
  readonly details: Record<string, unknown>;

  constructor(body: Schemas["ErrorBody"]) {
    super(body.message);
    this.name = "ApiError";
    this.code = body.code;
    this.details = body.details ?? {};
  }
}

/**
 * True when the server no longer knows the thing asked about. For a Cook or Shop session
 * this means it has expired (after 12 hours) and a new one should be started.
 */
export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.code === "NOT_FOUND";
}

/** Turns an openapi-fetch result into data, or throws the backend's error envelope. */
export function unwrap<T>(result: { data?: T; error?: unknown }): T {
  if (result.data !== undefined) return result.data;
  const envelope = result.error as Schemas["ErrorResponse"] | undefined;
  if (envelope?.error) throw new ApiError(envelope.error);
  throw new Error("The server could not be reached");
}
