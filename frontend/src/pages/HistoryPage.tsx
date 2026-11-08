import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api, unwrap, type Schemas } from "../api/client";
import { useInventory, useUndoStockEvent } from "../api/queries";
import { Icon } from "../components/Icon";
import { LEVEL_LABELS } from "../components/Level";
import { StockCorrectionSheet } from "./history/StockCorrectionSheet";

type StockEvent = Schemas["StockEvent"];
type Snapshot = Schemas["ItemSnapshot"];

const TITLES: Record<Schemas["StockEventType"], string> = {
  purchase: "Added",
  consume: "Cooked",
  adjust: "Updated",
  undo: "Undone",
};

function amount(snapshot: Snapshot | null): string {
  if (snapshot === null) return "—";
  if (snapshot.count !== null) return `${snapshot.count} ${snapshot.unit ?? ""}`.trim();
  return LEVEL_LABELS[snapshot.remaining_state];
}

function when(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

/**
 * Every purchase, meal and correction, newest first, each reversible. There is no design
 * for this screen; it follows the list style of My Kitchen.
 */
export function HistoryPage() {
  const inventory = useInventory();
  const batches = new Map(inventory.data?.groups.flatMap((group) =>
    group.batches.map((batch) => [batch.id, batch] as const)));
  const [correction, setCorrection] = useState<{
    batch: Schemas["InventoryItem"]; action: "edit" | "remove";
  } | null>(null);
  const [opening, setOpening] = useState(false);
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const events = useQuery({
    queryKey: ["stock-events"],
    queryFn: async () => unwrap(await api.GET("/api/stock-events", { params: { query: { limit: 30 } } })),
  });

  async function openCorrection(itemId: string, action: "edit" | "remove") {
    setOpening(true);
    setActionError("");
    setNotice("");
    try {
      // History contains old snapshots; editing always starts with a fresh batch/revision.
      const { data } = await inventory.refetch({ throwOnError: true });
      const batch = data?.groups.flatMap((group) => group.batches).find((item) => item.id === itemId);
      if (!batch) setNotice("This batch is no longer in your kitchen.");
      else setCorrection({ batch, action });
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not load the current item");
    } finally {
      setOpening(false);
    }
  }

  return (
    <div className="flex flex-col gap-[14px]">
      <div className="flex items-center justify-between">
        <Link
          to="/more"
          aria-label="Back"
          className="flex size-[40px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface"
        >
          <Icon name="chevron-left" />
        </Link>
        <h1 className="text-[16px] font-bold whitespace-nowrap">Kitchen history</h1>
        <span className="size-[40px]" />
      </div>

      {events.isPending && <p className="text-[14px] text-ink-muted">Loading…</p>}
      {events.isError && (
        <p role="alert" className="text-[13px] text-danger">
          Could not load the history: {events.error.message}
        </p>
      )}
      {events.data?.events.length === 0 && <p className="text-[14px] text-ink-muted">Nothing has changed yet.</p>}

      <p className="text-[12px] text-ink-muted">
        Edit or remove current kitchen stock below. Earlier submissions stay unchanged; each correction can be undone.
      </p>
      {(actionError || inventory.isError) && (
        <p role="alert" className="text-[13px] text-danger">
          Could not load current stock: {actionError || inventory.error?.message}.
          {" "}<button type="button" className="font-semibold underline"
            onClick={() => { setActionError(""); void inventory.refetch(); }}>Try again</button>
        </p>
      )}
      {notice && <p role="status" className="text-[13px] text-ink-muted">{notice}</p>}
      {opening && <p role="status" className="text-[13px] text-ink-muted">Loading current item…</p>}
      {events.data?.events.map((event) => (
        <EventCard key={event.id} event={event} batches={batches}
          stockLoaded={inventory.isSuccess}
          busy={opening || inventory.isFetching || inventory.isError}
          onUndo={() => setNotice("")}
          onAction={(id, action) => void openCorrection(id, action)} />
      ))}
      {correction && (
        <StockCorrectionSheet key={correction.batch.id} batch={correction.batch}
          action={correction.action} onClose={() => setCorrection(null)} onSaved={setNotice} />
      )}
    </div>
  );
}

function EventCard({ event, batches, stockLoaded, busy, onAction, onUndo }: {
  event: StockEvent;
  batches: Map<string, Schemas["InventoryItem"]>;
  stockLoaded: boolean;
  busy: boolean;
  onAction: (itemId: string, action: "edit" | "remove") => void;
  onUndo: () => void;
}) {
  const undo = useUndoStockEvent();
  const undone = undo.isSuccess;
  const anyReverted = (undo.data?.event.lines.length ?? 0) > 0;

  return (
    <section className="flex flex-col rounded-lg border border-border bg-surface px-[14px] py-[2px]">
      <div className="flex items-center gap-[10px] border-b border-border py-[12px]">
        <div className="flex min-w-px flex-1 flex-col gap-px">
          <h2 className="text-[14px] font-bold">
            {event.type === "adjust" && event.lines.length > 0
              && event.lines.every((line) => line.after === null) ? "Removed" : TITLES[event.type]}
            {" · "}{event.lines.length} {event.lines.length === 1 ? "item" : "items"}
          </h2>
          <p className="text-[12px] text-ink-muted">{when(event.created_at)}</p>
        </div>
        {event.can_undo && (
          <button
            type="button"
            disabled={undo.isPending || undone}
            onClick={() => undo.mutate(event.id, { onSuccess: onUndo })}
            className="flex shrink-0 items-center gap-[6px] rounded-pill border border-border bg-surface px-[12px] py-[6px] text-[12px] font-bold whitespace-nowrap disabled:opacity-50"
          >
            <Icon name="undo-sm" />
            {undone ? anyReverted ? "Undone" : "Nothing undone" : "Undo"}
          </button>
        )}
      </div>
      <ul className="flex flex-col">
        {event.lines.map((line) => (
          <li
            key={line.inventory_item_id}
            className="flex flex-col gap-[8px] border-b border-border py-[10px] last:border-b-0"
          >
            <div className="flex items-center gap-[10px]">
              <p className="min-w-px flex-1 text-[14px] font-semibold">{line.display_name}</p>
              <p className="shrink-0 text-[12px] whitespace-nowrap text-ink-muted">
                {amount(line.before)} → {amount(line.after)}
              </p>
            </div>
            {batches.has(line.inventory_item_id) ? (
              <>
                <p className="text-[12px] text-ink-muted">
                  Current remaining: {amount(batches.get(line.inventory_item_id)!)}
                </p>
                <div className="flex gap-[12px]">
                  <button type="button" disabled={busy}
                    aria-label={"Edit quantity for " + line.display_name}
                    className="text-[12px] font-semibold text-primary disabled:opacity-50"
                    onClick={() => onAction(line.inventory_item_id, "edit")}>Edit quantity</button>
                  <button type="button" disabled={busy}
                    aria-label={"Remove " + line.display_name}
                    className="text-[12px] font-semibold text-danger disabled:opacity-50"
                    onClick={() => onAction(line.inventory_item_id, "remove")}>Remove item</button>
                </div>
              </>
            ) : stockLoaded && (
              <p className="text-[12px] text-ink-muted">No longer in your kitchen.</p>
            )}
          </li>
        ))}
      </ul>
      {undo.isError && (
        <p role="alert" className="py-[10px] text-[13px] text-danger">
          Could not undo: {undo.error.message}
        </p>
      )}
      {undo.data && undo.data.conflicts.length > 0 && (
        <p className="py-[10px] text-[13px] text-warn">
          Left as they are because they changed since: {undo.data.conflicts.map((c) => c.display_name).join(", ")}
        </p>
      )}
    </section>
  );
}
