import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type Schemas } from "./client";
import { dropCookTag, mergeConstraints, SUGGESTION_KEY, useCookStep, useCookSuggestion } from "./cook";
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
    expect(post).toHaveBeenLastCalledWith("/api/cook/sessions", {
      body: {
        people: 3,
        previous_session_id: "old",
        skip_previous_recipe: true,
        constraints: { tags: ["quicker"], max_minutes: 30, max_difficulty: null },
      },
    });
    expect(post).toHaveBeenCalledTimes(2);
  });

  it("does not skip the old dish when recovering an adjustment", async () => {
    const { step, post } = setUp({
      "/api/cook/sessions/{session_id}/adjust": notFound,
      "/api/cook/sessions": { data: suggestion("new") },
    });
    await step.mutateAsync({ kind: "adjust", body: { people: 4 } });
    expect(post).toHaveBeenLastCalledWith("/api/cook/sessions", {
      body: {
        people: 4,
        previous_session_id: "old",
        constraints: { tags: ["quicker"], max_minutes: 30, max_difficulty: null },
      },
    });
  });

  it("reports other errors as they are", async () => {
    const stale = { error: { error: { code: "CONFLICT", message: "Busy", details: {} } } };
    const { step } = setUp({ "/api/cook/sessions/{session_id}/next": stale });

    await expect(step.mutateAsync({ kind: "next" })).rejects.toThrow("Busy");
  });
});

describe("restoring constraints", () => {
  const current = {
    ...suggestion("old"),
    recipe: { total_minutes: 30, difficulty: 2 },
    applied_constraints: { tags: ["quicker", "easier", "less_oil"], max_minutes: 30, max_difficulty: 2 },
  } as Schemas["Suggestion"];

  it("keeps achieved absolute limits without reapplying historical nudges", () => {
    expect(mergeConstraints(current, null)).toEqual({
      sourceSessionId: "old", people: 3, tags: ["quicker", "easier", "less_oil"], maxMinutes: 30, maxDifficulty: 2,
    });
  });

  it("calculates only new relative requests against the recipe the user actually saw", () => {
    expect(mergeConstraints(current, { tags: ["quicker", "easier"] })).toEqual({
      sourceSessionId: "old", people: 3, tags: ["quicker", "easier", "less_oil"], maxMinutes: 20, maxDifficulty: 1,
    });
    expect(mergeConstraints(current, { max_minutes: 60, max_difficulty: 3 })).toMatchObject({ maxMinutes: 30, maxDifficulty: 2 });
  });

  it("removes the relevant numeric restriction when a relative tag is dropped", () => {
    const conditions = mergeConstraints(current, null);
    expect(dropCookTag(conditions, "quicker")).toMatchObject({ tags: ["easier", "less_oil"], maxMinutes: null, maxDifficulty: 2 });
    expect(dropCookTag(conditions, "easier")).toMatchObject({ tags: ["quicker", "less_oil"], maxMinutes: 30, maxDifficulty: null });
    expect(dropCookTag(conditions, "less_oil")).toMatchObject({ tags: ["quicker", "easier"], maxMinutes: 30, maxDifficulty: 2 });
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
