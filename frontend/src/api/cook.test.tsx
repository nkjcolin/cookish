import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type Schemas } from "./client";
import { SUGGESTION_KEY, useCookStep, useCookSuggestion } from "./cook";
import { useUpdateInventoryItem } from "./queries";

function suggestion(sessionId: string): Schemas["Suggestion"] {
  return {
    session_id: sessionId,
    people: 3,
    applied_constraints: { tags: ["quicker"], max_minutes: 30, max_difficulty: null },
  } as Schemas["Suggestion"];
}

const notFound = { error: { error: { code: "NOT_FOUND", message: "Session not found", details: {} } } };

function setUp(answers: Record<string, unknown>) {
  const queryClient = new QueryClient();
  queryClient.setQueryData(SUGGESTION_KEY, suggestion("old"));
  const post = vi.spyOn(api, "POST").mockImplementation((async (path: string) => answers[path]) as never);
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const { result } = renderHook(() => useCookStep("old"), { wrapper });
  return { step: result.current, post };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useCookStep", () => {
  it("continues in a new session with the same conditions when the old one has expired", async () => {
    const { step, post } = setUp({
      "/api/cook/sessions/{session_id}/next": notFound,
      "/api/cook/sessions": { data: suggestion("new") },
      "/api/cook/sessions/{session_id}/adjust": { data: suggestion("new") },
    });

    const shown = await step.mutateAsync({ kind: "next" });

    expect(shown.session_id).toBe("new");
    expect(post).toHaveBeenCalledWith("/api/cook/sessions", { body: { people: 3 } });
    expect(post).toHaveBeenLastCalledWith("/api/cook/sessions/{session_id}/adjust", {
      params: { path: { session_id: "new" } },
      body: { tags: ["quicker"], max_minutes: 30 },
    });
  });

  it("reports other errors as they are", async () => {
    const stale = { error: { error: { code: "CONFLICT", message: "Busy", details: {} } } };
    const { step } = setUp({ "/api/cook/sessions/{session_id}/next": stale });

    await expect(step.mutateAsync({ kind: "next" })).rejects.toThrow("Busy");
  });
});

it("refreshes stock on the next Cook visit without replacing the session during a quick check", async () => {
  const queryClient = new QueryClient();
  queryClient.setQueryData(SUGGESTION_KEY, suggestion("old"));
  vi.spyOn(api, "PATCH").mockResolvedValue({ data: {} } as never);
  const post = vi.spyOn(api, "POST").mockResolvedValue({ data: suggestion("fresh") } as never);
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const active = renderHook(() => ({ session: useCookSuggestion(), update: useUpdateInventoryItem() }), { wrapper });

  await act(() => active.result.current.update.mutateAsync({
    itemId: "item",
    body: { revision: 1, remaining_state: "enough" },
  }));
  expect(active.result.current.session.data?.session_id).toBe("old");
  expect(post).not.toHaveBeenCalled();

  active.unmount();
  const returned = renderHook(useCookSuggestion, { wrapper });
  await waitFor(() => expect(returned.result.current.data?.session_id).toBe("fresh"));
  expect(post).toHaveBeenCalledExactlyOnceWith("/api/cook/sessions", { body: {} });
  returned.unmount();
});
