import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api, unwrap, type Schemas } from "../api/client";
import { useUndoStockEvent } from "../api/queries";
import { Icon } from "../components/Icon";
import { LEVEL_LABELS } from "../components/Level";

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
  const events = useQuery({
    queryKey: ["stock-events"],
    queryFn: async () => unwrap(await api.GET("/api/stock-events", { params: { query: { limit: 30 } } })),
  });

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

      {events.data?.events.map((event) => <EventCard key={event.id} event={event} />)}
    </div>
  );
}

function EventCard({ event }: { event: StockEvent }) {
  const undo = useUndoStockEvent();
  const undone = undo.isSuccess;
  const anyReverted = (undo.data?.event.lines.length ?? 0) > 0;

  return (
    <section className="flex flex-col rounded-lg border border-border bg-surface px-[14px] py-[2px]">
      <div className="flex items-center gap-[10px] border-b border-border py-[12px]">
        <div className="flex min-w-px flex-1 flex-col gap-px">
          <h2 className="text-[14px] font-bold">
            {TITLES[event.type]} · {event.lines.length} {event.lines.length === 1 ? "item" : "items"}
          </h2>
          <p className="text-[12px] text-ink-muted">{when(event.created_at)}</p>
        </div>
        {event.can_undo && (
          <button
            type="button"
            disabled={undo.isPending || undone}
            onClick={() => undo.mutate(event.id)}
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
            className="flex items-center gap-[10px] border-b border-border py-[10px] last:border-b-0"
          >
            <p className="min-w-px flex-1 text-[14px] font-semibold">{line.display_name}</p>
            <p className="shrink-0 text-[12px] whitespace-nowrap text-ink-muted">
              {amount(line.before)} → {amount(line.after)}
            </p>
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
