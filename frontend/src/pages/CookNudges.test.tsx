import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type Schemas } from "../api/client";
import { SUGGESTION_KEY } from "../api/cook";
import { CookPage } from "./CookPage";
import { AdjustSheet } from "./cook/AdjustSheet";

type Suggestion = Schemas["Suggestion"];

function suggestion(overrides: Partial<Suggestion> = {}): Suggestion {
  return {
    session_id: "session",
    recipe: {
      id: "recipe",
      title: "Chicken rice",
      cuisine: "chinese",
      difficulty: 2,
      total_minutes: 30,
      servings: 2,
      starred: false,
      taste_tags: [],
    },
    people: 2,
    ingredients: [],
    applied_constraints: { max_minutes: null, max_difficulty: null, tags: [] },
    has_previous: false,
    needs_check: [],
    freshness_check: [],
    available_nudges: ["quicker", "less_oil"],
    ...overrides,
  };
}

function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
}

function setupCook(current: Suggestion) {
  const queryClient = client();
  queryClient.setQueryData(SUGGESTION_KEY, current);
  queryClient.setQueryData(["me"], { preferences: { diets: [], allergens: [], equipment: [] } });
  const post = vi.spyOn(api, "POST").mockResolvedValue({ data: current } as never);
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter><CookPage /></MemoryRouter>
    </QueryClientProvider>,
  );
  return { queryClient, post };
}

function setupAdjust(current: Suggestion) {
  const queryClient = client();
  queryClient.setQueryData(["me"], { preferences: { diets: [], allergens: [], equipment: [] } });
  const onApply = vi.fn();
  const onClose = vi.fn();
  render(
    <QueryClientProvider client={queryClient}>
      <AdjustSheet suggestion={current} meal="dinner" onApply={onApply} onClose={onClose} />
    </QueryClientProvider>,
  );
  return { onApply, onClose };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("server-checked cooking nudges", () => {
  it("replaces the available actions after a response and blocks extra taps while waiting", async () => {
    const current = suggestion();
    const { post } = setupCook(current);
    const nudges = within(screen.getByRole("region", { name: "Recipe nudges" }));
    expect(nudges.getByRole("button", { name: "Quicker" })).toBeEnabled();
    expect(nudges.getByRole("button", { name: "Less oil" })).toBeEnabled();
    expect(nudges.queryByRole("button", { name: "More protein" })).not.toBeInTheDocument();

    let finish!: (value: never) => void;
    post.mockReturnValueOnce(new Promise<never>((resolve) => { finish = resolve; }));
    fireEvent.click(nudges.getByRole("button", { name: "Quicker" }));
    await waitFor(() => expect(nudges.getByRole("button", { name: "Less oil" })).toBeDisabled());
    fireEvent.click(nudges.getByRole("button", { name: "Less oil" }));
    expect(post).toHaveBeenCalledExactlyOnceWith("/api/cook/sessions/{session_id}/adjust", {
      params: { path: { session_id: "session" } }, body: { tags: ["quicker"] },
    });

    await act(async () => finish({ data: suggestion({
      recipe: { ...current.recipe, id: "next", title: "Quick soup", total_minutes: 20 },
      applied_constraints: { max_minutes: 20, max_difficulty: null, tags: ["quicker"] },
      available_nudges: ["more_vegetables"],
    }) } as never));
    expect(await screen.findByRole("heading", { name: "Quick soup" })).toBeInTheDocument();
    expect(nudges.queryByRole("button", { name: "Quicker" })).not.toBeInTheDocument();
    expect(nudges.queryByRole("button", { name: "Less oil" })).not.toBeInTheDocument();
    expect(nudges.getByRole("button", { name: "More vegetables" })).toBeEnabled();
    // The applied constraint is still visible outside the action row.
    expect(screen.getByRole("button", { name: "Quicker" })).toHaveAttribute("aria-pressed", "true");
  });

  it("keeps the current recipe and constraints visible when a nudge conflicts", async () => {
    const current = suggestion();
    const { post, queryClient } = setupCook(current);
    post.mockResolvedValueOnce({ error: { error: {
      code: "CONFLICT", message: "That change has no matching recipe. Try another nudge.", details: {},
    } } } as never);
    fireEvent.click(screen.getByRole("button", { name: "Quicker" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That change has no matching recipe");
    expect(screen.getByRole("heading", { name: "Chicken rice" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not tonight" })).toBeEnabled();
    expect(queryClient.getQueryData(SUGGESTION_KEY)).toEqual(current);
  });

  it("does not invent actions for an older response without availability", () => {
    const legacy = suggestion();
    delete legacy.available_nudges;
    setupCook(legacy);
    const nudges = within(screen.getByRole("region", { name: "Recipe nudges" }));
    expect(nudges.queryByRole("button", { name: "Quicker" })).not.toBeInTheDocument();
    expect(nudges.queryByRole("button", { name: "Less oil" })).not.toBeInTheDocument();
    expect(nudges.getByText(/No nudges fit/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Not tonight" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Adjust" })).toBeEnabled();
  });

  it("allows another relative nudge but does not advertise an applied binary tag", async () => {
    const { post } = setupCook(suggestion({
      applied_constraints: { max_minutes: 30, max_difficulty: 2, tags: ["quicker", "easier", "less_oil"] },
      available_nudges: ["quicker", "easier", "less_oil"],
    }));
    const nudges = within(screen.getByRole("region", { name: "Recipe nudges" }));
    expect(nudges.getByRole("button", { name: "Quicker" })).toBeEnabled();
    expect(nudges.getByRole("button", { name: "Easier" })).toBeEnabled();
    expect(nudges.queryByRole("button", { name: "Less oil" })).not.toBeInTheDocument();
    fireEvent.click(nudges.getByRole("button", { name: "Quicker" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/cook/sessions/{session_id}/adjust", {
      params: { path: { session_id: "session" } }, body: { tags: ["quicker"] },
    }));
  });
});

describe("recovering when no recipe fits", () => {
  const noResult = { error: { error: {
    code: "NO_RESULT", message: "Nothing fits all of that", details: { relaxable: ["max_minutes", "tags"] },
  } } };

  it("allows more time after skipping by restarting with skips and absolute difficulty preserved", async () => {
    const current = suggestion({
      applied_constraints: { max_minutes: 15, max_difficulty: 1, tags: ["quicker", "easier", "less_oil"] },
    });
    const { post } = setupCook(current);
    post.mockResolvedValueOnce(noResult as never);
    fireEvent.click(screen.getByRole("button", { name: "Not tonight" }));
    fireEvent.click(await screen.findByRole("button", { name: /Allow up to 30 min/ }));
    await waitFor(() => expect(post).toHaveBeenLastCalledWith("/api/cook/sessions", {
      body: {
        people: 2,
        previous_session_id: "session",
        constraints: { max_minutes: 30, max_difficulty: 1, tags: ["easier", "less_oil"] },
      },
    }));
    expect(post).toHaveBeenCalledTimes(2);
  });

  it("removes time without applying the old Quicker command again", async () => {
    const { post } = setupCook(suggestion({
      applied_constraints: { max_minutes: 15, max_difficulty: 1, tags: ["quicker", "less_oil"] },
    }));
    post.mockResolvedValueOnce(noResult as never);
    fireEvent.click(screen.getByRole("button", { name: "Not tonight" }));
    fireEvent.click(await screen.findByRole("button", { name: /15 min.*Remove/ }));
    await waitFor(() => expect(post).toHaveBeenLastCalledWith("/api/cook/sessions", {
      body: {
        people: 2,
        previous_session_id: "session",
        constraints: { max_minutes: null, max_difficulty: 1, tags: ["less_oil"] },
      },
    }));
  });

  it("Reset clears skips and uses household preference defaults", async () => {
    const { post } = setupCook(suggestion({
      applied_constraints: { max_minutes: 15, max_difficulty: 1, tags: ["quicker", "easier"] },
    }));
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    await waitFor(() => expect(post).toHaveBeenCalledExactlyOnceWith("/api/cook/sessions", { body: { people: 2 } }));
  });
});

describe("adjust sheet nudges", () => {
  it("shows supported actions, keeps applied tags read-only, and submits only the latest selection", () => {
    const { onApply, onClose } = setupAdjust(suggestion({
      applied_constraints: { max_minutes: 30, max_difficulty: 2, tags: ["quicker", "easier", "less_oil"] },
      available_nudges: ["quicker", "easier", "less_oil"],
    }));
    const choices = within(screen.getByRole("region", { name: "Choose a nudge" }));
    expect(choices.getAllByRole("button").map((button) => button.textContent)).toEqual(["Quicker", "Easier"]);
    expect(screen.getByText("Less oil")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Less oil" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "≤ 45 min" })).toBeDisabled();
    fireEvent.click(choices.getByRole("button", { name: "Quicker" }));
    fireEvent.click(choices.getByRole("button", { name: "Easier" }));
    expect(choices.getByRole("button", { name: "Quicker" })).toHaveAttribute("aria-pressed", "false");
    expect(choices.getByRole("button", { name: "Easier" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "Update suggestion" }));
    expect(onApply).toHaveBeenCalledExactlyOnceWith({ tags: ["easier"] });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("keeps numeric adjustments usable when an old response has no nudge availability", () => {
    const legacy = suggestion();
    delete legacy.available_nudges;
    const { onApply } = setupAdjust(legacy);
    expect(within(screen.getByRole("region", { name: "Choose a nudge" })).queryByRole("button")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "One more" }));
    fireEvent.click(screen.getByRole("button", { name: "Update suggestion" }));
    expect(onApply).toHaveBeenCalledExactlyOnceWith({ tags: [], people: 3 });
  });

  it("lets a typed combination reach the service for validation", async () => {
    const post = vi.spyOn(api, "POST").mockResolvedValue({ data: { adjust: { tags: ["less_oil", "more_protein"] } } } as never);
    const { onApply } = setupAdjust(suggestion({ available_nudges: ["less_oil"] }));
    fireEvent.change(screen.getByRole("textbox", { name: "Describe what you feel like" }), { target: { value: "less oil and more protein" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Understood as: + Less oil · + More protein")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Update suggestion" }));
    expect(post).toHaveBeenCalledWith("/ai/interpret", { body: { text: "less oil and more protein" } });
    expect(onApply).toHaveBeenCalledExactlyOnceWith({ tags: ["less_oil", "more_protein"] });
  });
});
