import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type Schemas } from "../api/client";
import { kitchenBatch } from "../test-fixtures/kitchen";
import { HistoryPage } from "./HistoryPage";

type StockEvent = Schemas["StockEvent"];

function purchase(): StockEvent {
  const batch = kitchenBatch();
  return {
    id: "purchase-event", type: "purchase", ref_type: "manual", ref_id: null,
    user_id: "test-user", created_at: "2026-11-08T12:00:00Z",
    lines: [{
      inventory_item_id: batch.id, display_name: batch.display_name, before: null,
      after: { count: 12, unit: "pcs", remaining_state: "enough" },
    }],
    reverts_event_id: null, can_undo: true,
  };
}

function setup(events: StockEvent[] = [purchase()]) {
  const get = vi.spyOn(api, "GET").mockResolvedValue({ data: { events } } as never);
  const patch = vi.spyOn(api, "PATCH");
  const remove = vi.spyOn(api, "DELETE");
  const undo = vi.spyOn(api, "POST").mockResolvedValue({ data: {
    event: { ...purchase(), id: "undo-event", type: "undo", can_undo: false },
    items: [], conflicts: [],
  } } as never);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter><HistoryPage /></MemoryRouter>
    </QueryClientProvider>,
  );
  return { get, patch, remove, undo };
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe("kitchen history", () => {
  it("shows historical amounts and Undo without stock editing or removal controls", async () => {
    const { get, patch, remove } = setup();
    expect(await screen.findByRole("heading", { name: "Added · 1 item" })).toBeVisible();
    expect(screen.getByText("Eggs")).toBeVisible();
    expect(screen.getByText("— → 12 pcs")).toBeVisible();
    expect(screen.getByRole("button", { name: "Undo" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /Edit quantity|Remove/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/Current remaining|Edit or remove current kitchen stock/)).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledWith("/api/stock-events", { params: { query: { limit: 30 } } });
    expect(patch).not.toHaveBeenCalled();
    expect(remove).not.toHaveBeenCalled();
  });

  it("keeps the existing Undo endpoint and refreshes history after success", async () => {
    const { get, undo, patch, remove } = setup();
    fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
    await waitFor(() => expect(undo).toHaveBeenCalledWith("/api/stock-events/{event_id}/undo", {
      params: { path: { event_id: "purchase-event" }, header: { "Idempotency-Key": expect.any(String) } },
    }));
    expect(await screen.findByRole("button", { name: "Undone" })).toBeDisabled();
    expect(get).toHaveBeenCalledTimes(2);
    expect(patch).not.toHaveBeenCalled();
    expect(remove).not.toHaveBeenCalled();
  });

  it("shows conflicts when Undo cannot restore a batch that changed later", async () => {
    const { undo } = setup();
    undo.mockResolvedValueOnce({ data: {
      event: { ...purchase(), id: "undo-event", type: "undo", lines: [], can_undo: false },
      items: [], conflicts: [{
        inventory_item_id: kitchenBatch().id, display_name: "Eggs", reason: "Changed since",
      }],
    } } as never);
    fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
    expect(await screen.findByText(/Left as they are because they changed since: Eggs/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Nothing undone" })).toBeDisabled();
  });

  it("reports an Undo failure and leaves the action available for retry", async () => {
    const { undo } = setup();
    undo.mockResolvedValueOnce({ error: { error: {
      code: "STALE_REVISION", message: "Changed elsewhere", details: {},
    } } } as never);
    fireEvent.click(await screen.findByRole("button", { name: "Undo" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not undo: Changed elsewhere");
    expect(screen.getByRole("button", { name: "Undo" })).toBeEnabled();
  });

  it("does not offer Undo for an event that cannot be reversed", async () => {
    setup([{ ...purchase(), can_undo: false }]);
    await screen.findByRole("heading", { name: "Added · 1 item" });
    expect(screen.queryByRole("button", { name: "Undo" })).not.toBeInTheDocument();
  });

  it("shows the empty state when there are no past changes", async () => {
    setup([]);
    expect(await screen.findByText("Nothing has changed yet.")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Undo" })).not.toBeInTheDocument();
  });
});
