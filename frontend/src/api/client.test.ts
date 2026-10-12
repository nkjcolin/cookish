import { describe, expect, it } from "vitest";

import { ApiError, idempotencyKey, unwrap } from "./client";

describe("unwrap", () => {
  it("returns the data of a successful call", () => {
    expect(unwrap({ data: { status: "ok" } })).toEqual({ status: "ok" });
  });

  it("throws the backend's error envelope as an ApiError", () => {
    const result = {
      error: { error: { code: "STALE_REVISION", message: "Changed elsewhere", details: { current_revision: 3 } } },
    };

    expect(() => unwrap(result)).toThrowError(ApiError);
    try {
      unwrap(result);
    } catch (e) {
      expect((e as ApiError).code).toBe("STALE_REVISION");
      expect((e as ApiError).details).toEqual({ current_revision: 3 });
    }
  });

  it("reports an unreachable server", () => {
    expect(() => unwrap({})).toThrowError("The server could not be reached");
  });
});

describe("idempotencyKey", () => {
  it("creates a new UUID each time", () => {
    const a = idempotencyKey()["Idempotency-Key"];
    const b = idempotencyKey()["Idempotency-Key"];

    expect(a).toMatch(/^[0-9a-f-]{36}$/);
    expect(a).not.toBe(b);
  });
});
