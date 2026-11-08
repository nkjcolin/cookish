import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { useInventory } from "../api/queries";
import { Chip } from "../components/Chip";
import { Icon } from "../components/Icon";
import { Level } from "../components/Level";
import { UndoToast } from "../components/UndoToast";
import { useArrivalState, type KitchenChanged } from "../lib/arrival";
import { UpdateItemSheet } from "./kitchen/UpdateItemSheet";
import {
  buildKitchenView,
  filterRows,
  type KitchenFilter,
  type KitchenRow,
  type KitchenSection,
} from "./kitchen/view";

const SECTION_TITLES: Record<KitchenSection, string> = {
  "use-soon": "Use soon",
  "not-sure": "Not sure",
  rest: "Fridge & pantry",
};
const SECTION_ORDER: KitchenSection[] = ["use-soon", "not-sure", "rest"];

/** Days without any update before the catch-up banner appears. */
const STALE_AFTER_DAYS = 3;

const roundButton =
  "flex size-[40px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface";

export function KitchenPage() {
  const inventory = useInventory();
  const [filter, setFilter] = useState<KitchenFilter>("all");
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const searchButton = useRef<HTMLButtonElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState<KitchenRow | null>(null);
  const changed = useArrivalState<KitchenChanged>();
  const [showToast, setShowToast] = useState(changed !== null);
  const view = useMemo(
    () => (inventory.data ? buildKitchenView(inventory.data, new Date()) : null),
    [inventory.data],
  );

  function closeSearch() {
    setQuery("");
    setSearchOpen(false);
    searchButton.current?.focus();
  }

  return (
    <div className="flex flex-col gap-[14px]">
      <div className="flex items-center justify-between">
        <Link to="/more" aria-label="Back" className={roundButton}>
          <Icon name="chevron-left" />
        </Link>
        <h1 className="text-[16px] font-bold whitespace-nowrap">My Kitchen</h1>
        <button
          ref={searchButton}
          type="button"
          aria-label={searchOpen ? "Close search" : "Search"}
          aria-expanded={searchOpen}
          onClick={() => searchOpen ? closeSearch() : setSearchOpen(true)}
          className={roundButton}
        >
          <Icon name={searchOpen ? "x" : "search"} />
        </button>
      </div>

      {searchOpen && (
        <form role="search" onSubmit={(event) => event.preventDefault()} className="flex items-center gap-[8px]">
          <label htmlFor="kitchen-search" className="sr-only">Search kitchen</label>
          <input
            ref={searchInput}
            id="kitchen-search"
            type="search"
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => { if (event.key === "Escape") closeSearch(); }}
            placeholder="Search your kitchen"
            className="min-w-px flex-1 rounded-md border border-border bg-surface px-[12px] py-[10px] text-[14px]"
          />
          {query && (
            <button type="button" className="text-[13px] font-semibold text-primary" onClick={() => {
              setQuery("");
              searchInput.current?.focus();
            }}>Clear</button>
          )}
        </form>
      )}

      {inventory.isPending && <p className="text-[14px] text-ink-muted">Loading…</p>}
      {inventory.isError && (
        <p role="alert" className="text-[14px] text-danger">
          Could not load your kitchen: {inventory.error.message}
        </p>
      )}

      {view && (
        <>
          {view.daysSinceUpdate !== null && view.daysSinceUpdate >= STALE_AFTER_DAYS && (
            <CatchUpBanner
              days={view.daysSinceUpdate}
              toCheck={view.counts["not-sure"]}
              onStart={() => setFilter("not-sure")}
            />
          )}

          <div className="-mx-[20px] flex items-start gap-[8px] overflow-x-auto px-[20px] [scrollbar-width:none]">
            <Chip selected={filter === "all"} onClick={() => setFilter("all")}>
              All · {view.counts.all}
            </Chip>
            <Chip selected={filter === "use-soon"} onClick={() => setFilter("use-soon")}>
              Use soon · {view.counts["use-soon"]}
            </Chip>
            <Chip selected={filter === "not-sure"} onClick={() => setFilter("not-sure")}>
              Not sure · {view.counts["not-sure"]}
            </Chip>
            <Chip selected={filter === "freezer"} onClick={() => setFilter("freezer")}>
              Freezer
            </Chip>
          </div>

          <Sections
            rows={filterRows(view.rows, filter, query)}
            onEdit={setEditing}
            emptyMessage={query.trim() ? "No matching ingredients. Try another name or filter." : "Nothing here."}
          />
        </>
      )}

      {changed && showToast && (
        <UndoToast eventId={changed.eventId} message={changed.message} onDismiss={() => setShowToast(false)} />
      )}

      {editing && (
        <UpdateItemSheet
          key={editing.editBatch.id}
          name={editing.name}
          batch={editing.editBatch}
          batchCount={editing.batchCount}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function CatchUpBanner({ days, toCheck, onStart }: { days: number; toCheck: number; onStart: () => void }) {
  return (
    <div className="flex items-center gap-[12px] rounded-md bg-info-soft p-[14px] text-info">
      <Icon name="refresh" />
      <div className="flex min-w-px flex-1 flex-col gap-px">
        <p className="text-[14px] font-bold">{days} days since your last update</p>
        <p className="text-[12px]">
          60-second catch-up: {toCheck} {toCheck === 1 ? "item" : "items"} to check
        </p>
      </div>
      <button
        type="button"
        onClick={onStart}
        className="shrink-0 rounded-pill bg-info px-[12px] py-[7px] text-[13px] font-bold whitespace-nowrap text-surface"
      >
        Start
      </button>
    </div>
  );
}

function Sections({ rows, onEdit, emptyMessage }: {
  rows: KitchenRow[];
  onEdit: (row: KitchenRow) => void;
  emptyMessage: string;
}) {
  if (rows.length === 0) return <p role="status" className="text-[14px] text-ink-muted">{emptyMessage}</p>;

  return SECTION_ORDER.map((section) => {
    const sectionRows = rows.filter((row) => row.section === section);
    if (sectionRows.length === 0) return null;
    return (
      <section key={section} className="flex flex-col gap-[14px]">
        <h2 className="text-[12px] font-bold tracking-[0.72px] text-ink-muted uppercase">{SECTION_TITLES[section]}</h2>
        <ul className="flex flex-col rounded-lg border border-border bg-surface px-[14px] py-[2px]">
          {sectionRows.map((row) => (
            <li key={row.key} className="border-b border-border last:border-b-0">
              <button
                type="button"
                onClick={() => onEdit(row)}
                className="flex w-full items-center gap-[10px] py-[12px] text-left"
              >
                <div className="flex min-w-px flex-1 flex-col gap-px">
                  <p className="text-[14px] font-bold">{row.name}</p>
                  <p
                    className={`text-[12px] ${row.detailIsWarning ? "font-semibold text-warn" : "text-ink-muted"}`}
                  >
                    {row.detail}
                  </p>
                </div>
                <RowAction row={row} />
              </button>
            </li>
          ))}
        </ul>
      </section>
    );
  });
}

function RowAction({ row }: { row: KitchenRow }) {
  if (row.section === "not-sure") {
    return (
      <span className="shrink-0 rounded-pill border border-border bg-surface px-[12px] py-[6px] text-[12px] font-bold whitespace-nowrap">
        Check
      </span>
    );
  }
  if (row.amount.kind === "count") {
    return <p className="shrink-0 text-[12px] font-semibold whitespace-nowrap text-ink">{row.amount.text}</p>;
  }
  return <Level state={row.amount.state} />;
}
