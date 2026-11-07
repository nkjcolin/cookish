import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, it, vi } from "vitest";

import { api, type Schemas } from "../api/client";
import { QuickCheckSheet } from "./cook/QuickCheckSheet";
import { UpdateItemSheet } from "./kitchen/UpdateItemSheet";

const eggs: Schemas["InventoryItem"] = {
  id: "egg-batch", ingredient_id: "egg", display_name: "Eggs", countable: true, count: null,
  unit: null, remaining_state: "unknown", storage: "fridge", revision: 1, category: "egg",
  last_confirmed_at: new Date().toISOString(), acquired_at: "2026-11-07", freshness_status: "ok",
  est_use_first_date: null, label_date: null, label_date_kind: null, freshness_confirmed_at: null, source: "manual",
};
const recipe = { id: "recipe", ingredients: [{ ingredient_id: "egg", unit: "pcs" }] };

function setup(batch = eggs) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const patch = vi.spyOn(api, "PATCH").mockResolvedValue({ data: { items: [{ ...batch, revision: 2 }] } } as never);
  const get = vi.spyOn(api, "GET").mockImplementation((async (path: string) => ({ data: path === "/api/ingredients" ? { items: [{ id: "egg", default_unit: "pcs" }] } : recipe })) as never);
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return { wrapper, patch, get };
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("asks for an unknown count and unit in Kitchen without assuming zero or enough", async () => {
  const { wrapper, patch } = setup();
  const close = vi.fn();
  render(<UpdateItemSheet name="Eggs" batch={eggs} batchCount={1} onClose={close} />, { wrapper });
  const input = await screen.findByRole("spinbutton", { name: "Amount of Eggs left (pieces)" });
  expect(input).toHaveValue(null);
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  fireEvent.change(input, { target: { value: "6" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(close).toHaveBeenCalled());
  expect(patch).toHaveBeenCalledWith("/api/inventory/items/{item_id}", expect.objectContaining({ body: { revision: 1, count: 6, unit: "pcs", remaining_state: "enough" } }));
});

it("does not reuse a quantity in incompatible units", async () => {
  const batch = { ...eggs, count: 2, unit: "tray" };
  const { wrapper } = setup(batch);
  render(<UpdateItemSheet name="Eggs" batch={batch} batchCount={1} onClose={() => {}} />, { wrapper });
  expect(await screen.findByRole("spinbutton")).toHaveValue(null);
  expect(screen.getByText(/cannot convert it automatically/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
});

it("resolves the unit by catalogue ID even when the batch has a custom display name", async () => {
  const batch = { ...eggs, display_name: "Grandma's breakfast box" };
  const { wrapper, get } = setup(batch);
  render(<UpdateItemSheet name={batch.display_name} batch={batch} batchCount={1} onClose={() => {}} />, { wrapper });
  expect(await screen.findByRole("spinbutton")).toHaveAccessibleName("Amount of Grandma's breakfast box left (pieces)");
  expect(get).toHaveBeenCalledWith("/api/ingredients", {
    params: { query: { q: batch.display_name, ingredient_id: eggs.ingredient_id, limit: 1 } },
  });
});

it("allows retrying failed unit lookup, with saving blocked until the unit is known", async () => {
  const { wrapper, get } = setup();
  get.mockRejectedValueOnce(new Error("Offline"));
  render(<UpdateItemSheet name="Eggs" batch={eggs} batchCount={1} onClose={() => {}} />, { wrapper });
  expect(await screen.findByRole("alert")).toHaveTextContent("Could not find the unit");
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("spinbutton")).toHaveValue(null);
});

function stockSuggestion(batch = eggs) {
  return { recipe: { id: "recipe", title: "Egg soup" }, needs_check: [{ item: batch }], freshness_check: [] } as unknown as Schemas["Suggestion"];
}

it("Quick Check submits a real count and canonical unit before proceeding", async () => {
  const { wrapper, patch } = setup();
  const proceed = vi.fn();
  render(<QuickCheckSheet suggestion={stockSuggestion()} onClose={() => {}} onProceed={proceed} onUnavailable={() => {}} />, { wrapper });
  const input = await screen.findByRole("spinbutton", { name: "Amount of Eggs left (pieces)" });
  expect(screen.getByRole("button", { name: "Show recipe" })).toBeDisabled();
  expect(screen.queryByRole("radio", { name: "Have it" })).not.toBeInTheDocument();
  fireEvent.change(input, { target: { value: "6" } });
  fireEvent.click(screen.getByRole("button", { name: "Show recipe" }));
  await waitFor(() => expect(proceed).toHaveBeenCalled());
  expect(patch).toHaveBeenCalledWith("/api/inventory/items/{item_id}", expect.objectContaining({ body: { revision: 1, count: 6, unit: "pcs", remaining_state: "enough" } }));
});

it("Quick Check sends zero as out and looks for another meal", async () => {
  const { wrapper, patch } = setup();
  const unavailable = vi.fn();
  const proceed = vi.fn();
  render(<QuickCheckSheet suggestion={stockSuggestion()} onClose={() => {}} onProceed={proceed} onUnavailable={unavailable} />, { wrapper });
  fireEvent.change(await screen.findByRole("spinbutton"), { target: { value: "0" } });
  fireEvent.click(screen.getByRole("button", { name: "Show recipe" }));
  await waitFor(() => expect(unavailable).toHaveBeenCalled());
  expect(proceed).not.toHaveBeenCalled();
  expect(patch).toHaveBeenCalledWith("/api/inventory/items/{item_id}", expect.objectContaining({ body: { revision: 1, count: 0, unit: "pcs", remaining_state: "out" } }));
});

it("does not try to select unchecked stock when checking is deferred", async () => {
  const { wrapper, patch } = setup();
  const close = vi.fn();
  const proceed = vi.fn();
  render(<QuickCheckSheet suggestion={stockSuggestion()} onClose={close} onProceed={proceed} onUnavailable={() => {}} />, { wrapper });
  fireEvent.click(screen.getByRole("button", { name: "Check later" }));
  expect(close).toHaveBeenCalled();
  expect(proceed).not.toHaveBeenCalled();
  expect(patch).not.toHaveBeenCalled();
});

it("asks for the unknown quantity as well as freshness before proceeding", async () => {
  const { wrapper, patch } = setup();
  const proceed = vi.fn();
  const suggestion = { ...stockSuggestion(), needs_check: [], freshness_check: [{ item: eggs, reason: "past_estimate" }] } as Schemas["Suggestion"];
  render(<QuickCheckSheet suggestion={suggestion} onClose={() => {}} onProceed={proceed} onUnavailable={() => {}} />, { wrapper });
  fireEvent.click(screen.getByRole("radio", { name: "It’s fine" }));
  const input = await screen.findByRole("spinbutton");
  expect(screen.getByRole("button", { name: "Show recipe" })).toBeDisabled();
  fireEvent.change(input, { target: { value: "4" } });
  fireEvent.click(screen.getByRole("button", { name: "Show recipe" }));
  await waitFor(() => expect(proceed).toHaveBeenCalled());
  expect(patch).toHaveBeenCalledWith("/api/inventory/items/{item_id}", expect.objectContaining({ body: { revision: 1, count: 4, unit: "pcs", remaining_state: "enough", freshness_confirmed: true } }));
});

it("retries a partially saved Quick Check without resubmitting an already updated revision", async () => {
  const { wrapper, patch } = setup();
  const onion: Schemas["InventoryItem"] = { ...eggs, id: "onion-batch", ingredient_id: "onion", display_name: "Onion", countable: false, category: "produce" };
  patch.mockResolvedValueOnce({ data: { items: [{ ...eggs, revision: 2 }] } } as never)
    .mockRejectedValueOnce(new Error("Connection lost"))
    .mockResolvedValueOnce({ data: { items: [{ ...onion, revision: 2 }] } } as never);
  const proceed = vi.fn();
  const suggestion = { ...stockSuggestion(), needs_check: [{ item: eggs }, { item: onion }] };
  render(<QuickCheckSheet suggestion={suggestion} onClose={() => {}} onProceed={proceed} onUnavailable={() => {}} />, { wrapper });
  fireEvent.change(await screen.findByRole("spinbutton"), { target: { value: "6" } });
  fireEvent.click(screen.getByRole("radio", { name: "Have it" }));
  fireEvent.click(screen.getByRole("button", { name: "Show recipe" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Connection lost");
  expect(proceed).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Show recipe" }));
  await waitFor(() => expect(proceed).toHaveBeenCalled());
  expect(patch).toHaveBeenCalledTimes(3);
  expect(patch.mock.calls.map((call) => call[1]?.params?.path?.item_id)).toEqual(["egg-batch", "onion-batch", "onion-batch"]);
});
