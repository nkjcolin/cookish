import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useInventory } from "../api/queries";
import { Chip } from "../components/Chip";
import { Icon } from "../components/Icon";
import { Level } from "../components/Level";
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
  const view = useMemo(
    () => (inventory.data ? buildKitchenView(inventory.data, new Date()) : null),
    [inventory.data],
  );

  return (
    <div className="flex flex-col gap-[14px]">
      <div className="flex items-center justify-between">
        <Link to="/more" aria-label="Back" className={roundButton}>
          <Icon name="chevron-left" />
        </Link>
        <h1 className="text-[16px] font-bold whitespace-nowrap">My Kitchen</h1>
        <button type="button" aria-label="Search" className={roundButton}>
          <Icon name="search" />
        </button>
      </div>

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

          <Sections rows={filterRows(view.rows, filter)} />
        </>
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

function Sections({ rows }: { rows: KitchenRow[] }) {
  if (rows.length === 0) return <p className="text-[14px] text-ink-muted">Nothing here.</p>;

  return SECTION_ORDER.map((section) => {
    const sectionRows = rows.filter((row) => row.section === section);
    if (sectionRows.length === 0) return null;
    return (
      <section key={section} className="flex flex-col gap-[14px]">
        <h2 className="text-[12px] font-bold tracking-[0.72px] text-ink-muted uppercase">{SECTION_TITLES[section]}</h2>
        <ul className="flex flex-col rounded-lg border border-border bg-surface px-[14px] py-[2px]">
          {sectionRows.map((row) => (
            <li
              key={row.key}
              className="flex items-center gap-[10px] border-b border-border py-[12px] last:border-b-0"
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
      <button
        type="button"
        className="shrink-0 rounded-pill border border-border bg-surface px-[12px] py-[6px] text-[12px] font-bold whitespace-nowrap"
      >
        Check
      </button>
    );
  }
  if (row.amount.kind === "count") {
    return <p className="shrink-0 text-[12px] font-semibold whitespace-nowrap text-ink">{row.amount.text}</p>;
  }
  return <Level level={row.amount.level} />;
}
