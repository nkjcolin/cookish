import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, ApiError, type Schemas } from "./client";
import { useImageJobs } from "./imageJobs";

const id = "d041df63-1dc7-4f26-a88b-9b25757b0037";
const body: Schemas["ParseImageRequest"] = { kind: "photo", media_type: "image/jpeg", image_base64: "test" };
function job(status: Schemas["ImageJobResponse"]["status"]): Schemas["ImageJobResponse"] {
  return {
    job_id: id, kind: "photo", status, created_at: "2026-11-08T00:00:00Z",
    expires_at: "2026-11-09T00:00:00Z", result: status === "completed" ? { items: [] } : null,
    error: status === "failed" ? { code: "UPSTREAM_UNAVAILABLE", message: "Model unavailable", details: {} } : null,
    usage: null, poll_after_seconds: 2,
  };
}
function setup(client = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } })) {
  const wrapper = ({ children }: { children: ReactNode }) =>
    <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return renderHook(useImageJobs, { wrapper });
}
async function tick(ms = 1) {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
}

beforeEach(() => {
  sessionStorage.clear();
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-11-08T00:00:00Z"));
});
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("image job polling", () => {
  it("keeps polling beyond 27 seconds and stops on completion", async () => {
    const started = Date.now();
    const post = vi.spyOn(api, "POST").mockResolvedValue({ data: job("queued") } as never);
    const get = vi.spyOn(api, "GET").mockImplementation((async () => ({
      data: job(Date.now() - started >= 45000 ? "completed" : "processing"),
    })) as never);
    const hook = setup();
    await act(async () => { await hook.result.current.submit(body); });
    await tick(28000);
    expect(hook.result.current.active).toBe(true);
    expect(hook.result.current.job?.status).toBe("processing");
    expect(post).toHaveBeenCalledTimes(1);
    expect(post.mock.calls[0]?.[0]).toBe("/ai/image-jobs");
    await tick(20000);
    expect(hook.result.current.job?.status).toBe("completed");
    expect(hook.result.current.active).toBe(false);
    const calls = get.mock.calls.length;
    await tick(10000);
    expect(get).toHaveBeenCalledTimes(calls);
  });

  it("resumes a job after the page is remounted without uploading again", async () => {
    const post = vi.spyOn(api, "POST").mockResolvedValue({ data: job("queued") } as never);
    vi.spyOn(api, "GET").mockResolvedValue({ data: job("processing") } as never);
    const first = setup();
    await act(async () => { await first.result.current.submit(body); });
    await tick();
    first.unmount();
    const resumed = setup();
    await tick();
    expect(resumed.result.current.pending?.jobId).toBe(id);
    expect(resumed.result.current.job?.status).toBe("processing");
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("uses the same submission key when retrying a lost acknowledgement", async () => {
    const post = vi.spyOn(api, "POST").mockRejectedValueOnce(new Error("Connection lost"))
      .mockResolvedValue({ data: job("queued") } as never);
    vi.spyOn(api, "GET").mockResolvedValue({ data: job("processing") } as never);
    const hook = setup();
    let request: Promise<unknown>;
    await act(async () => { request = hook.result.current.submit(body); });
    await tick(1500);
    await act(async () => { await request!; });
    expect(post).toHaveBeenCalledTimes(2);
    expect(post.mock.calls[0]?.[1]).toEqual(post.mock.calls[1]?.[1]);
  });

  it("stops polling on a failed job and exposes the safe error", async () => {
    vi.spyOn(api, "POST").mockResolvedValue({ data: job("queued") } as never);
    const get = vi.spyOn(api, "GET").mockResolvedValue({ data: job("failed") } as never);
    const hook = setup();
    await act(async () => { await hook.result.current.submit(body); });
    await tick();
    expect(hook.result.current.active).toBe(false);
    expect(hook.result.current.error?.message).toBe("Model unavailable");
    const calls = get.mock.calls.length;
    await tick(30000);
    expect(get).toHaveBeenCalledTimes(calls);
  });

  it("does not retry another user's missing job and lets the user clear it", async () => {
    sessionStorage.setItem("cookish.pending-image-job", JSON.stringify({ jobId: id, kind: "photo" }));
    const get = vi.spyOn(api, "GET").mockRejectedValue(new ApiError({
      code: "NOT_FOUND", message: "Image job not found or expired", details: {},
    }));
    const hook = setup();
    await tick();
    expect(hook.result.current.error?.message).toContain("not found");
    await tick(30000);
    expect(get).toHaveBeenCalledTimes(1);
    act(() => hook.result.current.clear());
    expect(hook.result.current.active).toBe(false);
    expect(sessionStorage.getItem("cookish.pending-image-job")).toBeNull();
  });

  it("does not reuse a previous login's completed result before rechecking ownership", async () => {
    const client = new QueryClient();
    vi.spyOn(api, "POST").mockResolvedValue({ data: job("queued") } as never);
    const get = vi.spyOn(api, "GET").mockResolvedValue({ data: job("completed") } as never);
    const first = setup(client);
    await act(async () => { await first.result.current.submit(body); });
    await tick();
    expect(first.result.current.job?.status).toBe("completed");
    first.unmount();
    // Authenticator remounts the page after login, while the shared QueryClient may survive.
    get.mockImplementation((() => new Promise(() => {})) as never);
    const nextLogin = setup(client);
    expect(nextLogin.result.current.job).toBeUndefined();
    await tick();
    expect(nextLogin.result.current.job).toBeUndefined();
    expect(nextLogin.result.current.active).toBe(true);
  });
});
