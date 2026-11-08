import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type Schemas } from "../api/client";
import { kitchenBatch, kitchenInventory } from "../test-fixtures/kitchen";
import { HistoryPage } from "./HistoryPage";

type Batch = Schemas["InventoryItem"];
type Event = Schemas["StockEvent"];
type Snapshot = Schemas["ItemSnapshot"];

function snapshot(item: Batch): Snapshot {
  return { count: item.count, unit: item.unit, remaining_state: item.remaining_state };
}

function eventFor(batch: Batch, type: Event["type"], before: Snapshot | null, after: Snapshot | null): Event {
  return {
    id: crypto.randomUUID(), type, ref_type: "manual", ref_id: null,
    user_id: "test-user", created_at: new Date().toISOString(),
    lines: [{ inventory_item_id: batch.id, display_name: batch.display_name, before, after }],
    reverts_event_id: null, can_undo: type !== "undo",
  };
}

async function setup(initial = kitchenBatch(), extra: Batch[] = []) {
  const batches = new Map([initial, ...extra].map((batch) => [batch.id, batch]));
  const originals = new Map(batches);
  const submission = eventFor(initial, "purchase", null, snapshot({ ...initial, count: 12 }));
  let events = [submission];
  let revision = initial.revision;
  const get = vi.spyOn(api, "GET").mockImplementation((async (path: string) => ({
    data: path === "/api/stock-events" ? structuredClone({ events })
      : kitchenInventory([...batches.values()]),
  })) as never);
  const patch = vi.spyOn(api, "PATCH").mockImplementation((async (_path: string, options: {
    params: { path: { item_id: string } }; body: Schemas["InventoryItemUpdate"];
  }) => {
    const current = batches.get(options.params.path.item_id)!;
    const updated = { ...current, ...options.body, revision: ++revision } as Batch;
    batches.set(current.id, updated);
    const event = eventFor(current, "adjust", snapshot(current), snapshot(updated));
    events = [event, ...events];
    return { data: { event, items: [updated] } };
  }) as never);
  const remove = vi.spyOn(api, "DELETE").mockImplementation((async (_path: string, options: {
    params: { path: { item_id: string } };
  }) => {
    const current = batches.get(options.params.path.item_id)!;
    batches.delete(current.id);
    const event = eventFor(current, "adjust", snapshot(current), null);
    events = [event, ...events];
    return { data: { event, items: [] } };
  }) as never);
  const undo = vi.spyOn(api, "POST").mockImplementation((async (_path: string, options: {
    params: { path: { event_id: string } };
  }) => {
    const target = events.find((event) => event.id === options.params.path.event_id)!;
    const line = target.lines[0]!;
    const restored = { ...originals.get(line.inventory_item_id)!, ...line.before, revision: ++revision };
    batches.set(restored.id, restored);
    const event = eventFor(restored, "undo", line.after, line.before);
    event.reverts_event_id = target.id;
    events = [event, ...events.map((item) => item.id === target.id ? { ...item, can_undo: false } : item)];
    return { data: { event, items: [restored], conflicts: [] } };
  }) as never);
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter><HistoryPage /></MemoryRouter>
    </QueryClientProvider>,
  );
  await waitFor(() => expect(screen.getByRole("button", { name: "Edit quantity for " + initial.display_name })).toBeEnabled());
  return { batches, get, patch, remove, undo, submission, events: () => events };
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

async function openEdit(name = "Eggs") {
  fireEvent.click(screen.getAllByRole("button", { name: "Edit quantity for " + name })[0]!);
  return screen.findByRole("dialog", { name: "Edit quantity remaining" });
}

describe("history current-stock corrections", () => {
  it("edits the latest amount and exact submission batch rather than the old snapshot or another batch", async () => {
    const second = kitchenBatch({ id: "second-batch", count: 99, acquired_at: "2026-10-01" });
    const { batches, patch, events, submission } = await setup(kitchenBatch(), [second]);
    // Another update occurs after History first loads; opening the editor must refetch.
    batches.set(kitchenBatch().id, kitchenBatch({ count: 5, revision: 7 }));
    const dialog = await openEdit();
    expect(within(dialog).getByRole("spinbutton")).toHaveValue(5);
    fireEvent.change(within(dialog).getByRole("spinbutton"), { target: { value: "3" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save quantity" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(patch).toHaveBeenCalledWith("/api/inventory/items/{item_id}", expect.objectContaining({
      params: expect.objectContaining({ path: { item_id: kitchenBatch().id } }),
      body: { revision: 7, count: 3, unit: "pcs", remaining_state: "enough" },
    }));
    expect(batches.get(second.id)?.count).toBe(99);
    expect(events().find((event) => event.id === submission.id)?.lines[0]?.after?.count).toBe(12);
    expect(events()[0]?.lines[0]?.before?.count).toBe(5);
    expect(screen.getAllByText("Current remaining: 3 pcs")).not.toHaveLength(0);
  });

  it("records zero as out without turning it into deletion", async () => {
    const { patch, remove } = await setup();
    const dialog = await openEdit();
    fireEvent.change(within(dialog).getByRole("spinbutton"), { target: { value: "0" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save quantity" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({
      body: { revision: 3, count: 0, unit: "pcs", remaining_state: "out" },
    }));
    expect(remove).not.toHaveBeenCalled();
  });

  it("requires explicit quantities and units when the saved amount is unknown", async () => {
    await setup(kitchenBatch({ count: null, unit: null }));
    const dialog = await openEdit();
    expect(within(dialog).getByRole("spinbutton")).toHaveValue(null);
    expect(within(dialog).getByRole("button", { name: "Save quantity" })).toBeDisabled();
    fireEvent.change(within(dialog).getByRole("spinbutton"), { target: { value: "6" } });
    expect(within(dialog).getByRole("button", { name: "Save quantity" })).toBeDisabled();
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Unit" }), { target: { value: "pcs" } });
    expect(within(dialog).getByRole("button", { name: "Save quantity" })).toBeEnabled();
    fireEvent.change(within(dialog).getByRole("spinbutton"), { target: { value: "-1" } });
    expect(within(dialog).getByRole("button", { name: "Save quantity" })).toBeDisabled();
  });

  it("preserves kilogram quantities and the user's coarse availability choice", async () => {
    const { patch } = await setup(kitchenBatch({
      display_name: "Rice", countable: false, count: 1, unit: "kg", remaining_state: "low",
    }));
    const dialog = await openEdit("Rice");
    fireEvent.change(within(dialog).getByRole("spinbutton"), { target: { value: "0.25" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save quantity" }));
    await waitFor(() => expect(patch).toHaveBeenCalled());
    expect(patch).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({
      body: { revision: 3, count: 0.25, unit: "kg", remaining_state: "low" },
    }));
  });

  it("shows a stale-revision error without rewriting the original submission", async () => {
    const { patch, events, submission } = await setup();
    patch.mockResolvedValueOnce({ error: { error: {
      code: "STALE_REVISION", message: "Changed elsewhere", details: {},
    } } } as never);
    const dialog = await openEdit();
    fireEvent.change(within(dialog).getByRole("spinbutton"), { target: { value: "6" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save quantity" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("changed elsewhere");
    expect(events()).toEqual([submission]);
    expect(dialog).toBeInTheDocument();
  });

  it("requires confirmation to remove a batch and can undo the new removal", async () => {
    const { remove, undo, batches } = await setup();
    fireEvent.click(screen.getByRole("button", { name: "Remove Eggs" }));
    let dialog = await screen.findByRole("dialog", { name: "Remove item" });
    expect(remove).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Remove Eggs" }));
    dialog = await screen.findByRole("dialog", { name: "Remove item" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove item" }));
    await screen.findByRole("heading", { name: "Removed · 1 item" });
    expect(remove).toHaveBeenCalledWith("/api/inventory/items/{item_id}", {
      params: {
        path: { item_id: kitchenBatch().id }, query: { revision: 3 },
        header: { "Idempotency-Key": expect.any(String) },
      },
    });
    expect(screen.queryByRole("button", { name: "Edit quantity for Eggs" })).not.toBeInTheDocument();
    const card = screen.getByRole("heading", { name: "Removed · 1 item" }).closest("section")!;
    fireEvent.click(within(card).getByRole("button", { name: "Undo" }));
    await waitFor(() => expect(batches.get(kitchenBatch().id)?.count).toBe(8));
    expect(undo).toHaveBeenCalledWith("/api/stock-events/{event_id}/undo", expect.anything());
    await waitFor(() => expect(screen.getAllByRole("button", { name: "Edit quantity for Eggs" }).length).toBeGreaterThan(0));
  });

  it("undoes a quantity correction to the previous remaining amount, not the purchase amount", async () => {
    const { batches } = await setup();
    const dialog = await openEdit();
    fireEvent.change(within(dialog).getByRole("spinbutton"), { target: { value: "6" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save quantity" }));
    const heading = await screen.findByRole("heading", { name: "Updated · 1 item" });
    fireEvent.click(within(heading.closest("section")!).getByRole("button", { name: "Undo" }));
    await waitFor(() => expect(batches.get(kitchenBatch().id)?.count).toBe(8));
    await waitFor(() => expect(screen.queryByText(/Quantity updated. Undo the new/)).not.toBeInTheDocument());
  });

  it("leaves stock unchanged and reports the conflict when undo cannot restore a later-edited batch", async () => {
    const { undo, batches } = await setup();
    undo.mockResolvedValueOnce({ data: {
      event: { ...eventFor(kitchenBatch(), "undo", null, null), lines: [] },
      items: [], conflicts: [{
        inventory_item_id: kitchenBatch().id, display_name: "Eggs", reason: "Changed since",
      }],
    } } as never);
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(await screen.findByText(/Left as they are because they changed since/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Nothing undone" })).toBeDisabled();
    expect(batches.get(kitchenBatch().id)?.count).toBe(8);
  });
});
