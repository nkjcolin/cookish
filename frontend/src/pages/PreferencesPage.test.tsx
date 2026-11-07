import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { api, type Schemas } from "../api/client";
import { COOK_RECORD_KEY, SUGGESTION_KEY, useCookSuggestion } from "../api/cook";
import { BASKET_KEY, CART_KEY, CART_REVIEW_KEY } from "../api/stockCache";
import { PreferencesPage } from "./PreferencesPage";

const preferences: Schemas["Preferences"] = {
  allergens: [], diets: [], equipment: ["stove"], cuisines: [], disliked_ingredient_ids: [],
  max_cook_minutes: 30, max_difficulty: null, household_size: 2,
  last_cook_people: 2, last_shop_people: 2, last_shop_meals: 3,
  updated_at: "2026-11-08T00:00:00+08:00",
};

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(["me"], { preferences });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}><MemoryRouter>{children}</MemoryRouter></QueryClientProvider>;
  render(<PreferencesPage />, { wrapper });
  return { client, wrapper };
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("keeps rapid allergy changes in one draft and sends them together on Save", async () => {
  let finish!: (result: unknown) => void;
  const put = vi.spyOn(api, "PUT").mockImplementation((() => new Promise((resolve) => { finish = resolve; })) as never);
  const { client } = setup();
  client.setQueryData(SUGGESTION_KEY, { session_id: "unchanged" });
  client.setQueryData(BASKET_KEY, { id: "unchanged" });
  fireEvent.click(screen.getByRole("button", { name: "Edit" }));
  fireEvent.click(screen.getByRole("button", { name: "Egg allergy" }));
  fireEvent.click(screen.getByRole("button", { name: "Peanut allergy" }));
  expect(screen.getByRole("button", { name: "Egg allergy" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "Peanut allergy" })).toHaveAttribute("aria-pressed", "true");
  expect(put).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));
  await waitFor(() => expect(put).toHaveBeenCalledTimes(1));
  expect(put).toHaveBeenCalledWith("/api/household/preferences", { body: expect.objectContaining({ allergens: ["egg", "peanut"] }) });
  expect(screen.getByRole("button", { name: "Egg allergy" })).toBeDisabled();
  await act(() => finish({ data: { ...preferences, allergens: ["egg", "peanut"] } }));
  expect(await screen.findByRole("status")).toHaveTextContent("Preferences saved");
});

it("retains the unsaved draft when saving fails, so the same choices can be retried", async () => {
  const put = vi.spyOn(api, "PUT").mockRejectedValueOnce(new Error("Offline"));
  const { client } = setup();
  client.setQueryData(SUGGESTION_KEY, { session_id: "unchanged" });
  client.setQueryData(BASKET_KEY, { id: "unchanged" });
  fireEvent.click(screen.getByRole("button", { name: "Edit" }));
  fireEvent.click(screen.getByRole("button", { name: "Egg allergy" }));
  fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Offline");
  expect(screen.getByRole("button", { name: "Egg allergy" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "Save preferences" })).toBeEnabled();
  expect(client.getQueryData(SUGGESTION_KEY)).toEqual({ session_id: "unchanged" });
  expect(client.getQueryData(BASKET_KEY)).toEqual({ id: "unchanged" });
  put.mockResolvedValueOnce({ data: { ...preferences, allergens: ["egg"] } } as never);
  fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Preferences saved");
  expect(put).toHaveBeenCalledTimes(2);
});

it("restarts cached Cook and Buy plans after saving, and clears a reviewed shopping cart", async () => {
  vi.spyOn(api, "PUT").mockResolvedValue({ data: { ...preferences, allergens: ["egg"] } } as never);
  const post = vi.spyOn(api, "POST").mockResolvedValue({ data: { session_id: "new-egg-free" } } as never);
  const { client, wrapper } = setup();
  client.setQueryData(SUGGESTION_KEY, { session_id: "old-with-eggs" });
  client.setQueryData(BASKET_KEY, { session_id: "old-with-eggs" });
  client.setQueryData(COOK_RECORD_KEY, { id: "selected-with-eggs" });
  client.setQueryData(CART_KEY, ["eggs"]);
  client.setQueryData(CART_REVIEW_KEY, { hasMadeSelection: true, quantityReviewIds: ["eggs"] });
  fireEvent.click(screen.getByRole("button", { name: "Edit" }));
  fireEvent.click(screen.getByRole("button", { name: "Egg allergy" }));
  expect(screen.getByText(/clears shopping-list ticks/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));
  await screen.findByRole("status");
  expect(client.getQueryData(SUGGESTION_KEY)).toBeUndefined();
  expect(client.getQueryData(BASKET_KEY)).toBeUndefined();
  expect(client.getQueryData(COOK_RECORD_KEY)).toBeUndefined();
  expect(client.getQueryData(CART_KEY)).toEqual([]);
  expect(client.getQueryData(CART_REVIEW_KEY)).toEqual({ hasMadeSelection: false, quantityReviewIds: [] });
  const returned = renderHook(useCookSuggestion, { wrapper });
  await waitFor(() => expect(returned.result.current.data?.session_id).toBe("new-egg-free"));
  expect(post).toHaveBeenCalledWith("/api/cook/sessions", { body: {} });
});
