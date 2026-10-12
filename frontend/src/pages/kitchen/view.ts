import type { Schemas } from "../../api/client";
import type { LevelName } from "../../components/Level";

type Inventory = Schemas["Inventory"];
type Group = Schemas["InventoryGroup"];
type Batch = Schemas["InventoryItem"];

export type KitchenSection = "use-soon" | "not-sure" | "rest";
export type KitchenFilter = "all" | "use-soon" | "not-sure" | "freezer";

export type KitchenRow = {
  key: string;
  name: string;
  section: KitchenSection;
  detail: string;
  /** The detail line is a date printed on the package or an overdue estimate. */
  detailIsWarning: boolean;
  /** Countable ingredients show their total; the rest show a coarse level. */
  amount: { kind: "count"; text: string } | { kind: "level"; level: LevelName };
  inFreezer: boolean;
  batchIds: string[];
};

export type KitchenView = {
  rows: KitchenRow[];
  counts: Record<Exclude<KitchenFilter, "freezer">, number>;
  /** Whole days since anything in the kitchen was last confirmed; null when empty. */
  daysSinceUpdate: number | null;
};

const DAY_MS = 24 * 60 * 60 * 1000;
const NEEDS_ATTENTION = new Set<Batch["freshness_status"]>(["use_soon", "check", "expired"]);

// Interim mapping: the contract has three states, the design has four filled levels.
const LEVEL: Record<Batch["remaining_state"], LevelName> = {
  enough: "plenty",
  low: "a-bit",
  out: "almost-out",
  unknown: "unsure",
};

function capitalise(word: string): string {
  return word.charAt(0).toUpperCase() + word.slice(1);
}

function daysBetween(from: Date, to: Date): number {
  const start = Date.UTC(from.getFullYear(), from.getMonth(), from.getDate());
  const end = Date.UTC(to.getFullYear(), to.getMonth(), to.getDate());
  return Math.round((end - start) / DAY_MS);
}

function parseDate(isoDate: string): Date {
  const [year, month, day] = isoDate.split("-").map(Number);
  return new Date(year!, month! - 1, day!);
}

/** The batch that should be eaten first decides what the row says. */
function firstToUse(batches: Batch[]): Batch {
  const dated = batches.filter((b) => b.est_use_first_date !== null);
  const pool = dated.length > 0 ? dated : batches;
  return pool.reduce((a, b) => ((a.est_use_first_date ?? "") <= (b.est_use_first_date ?? "") ? a : b));
}

function sectionOf(batches: Batch[]): KitchenSection {
  if (batches.every((b) => b.remaining_state === "unknown")) return "not-sure";
  if (batches.some((b) => NEEDS_ATTENTION.has(b.freshness_status))) return "use-soon";
  return "rest";
}

function detailOf(section: KitchenSection, batch: Batch, today: Date): { text: string; warning: boolean } {
  const storage = capitalise(batch.storage);
  if (section === "not-sure") {
    const days = daysBetween(new Date(batch.last_confirmed_at), today);
    return { text: `Last confirmed ${days} ${days === 1 ? "day" : "days"} ago`, warning: false };
  }
  if (section === "rest" || batch.est_use_first_date === null) return { text: storage, warning: false };

  const useFirst = parseDate(batch.est_use_first_date);
  const daysLeft = daysBetween(today, useFirst);
  if (batch.label_date !== null) {
    const weekday = useFirst.toLocaleDateString("en-GB", { weekday: "short" });
    const phrase = batch.label_date_kind === "use_by" ? "use by" : "best by";
    return { text: `${storage} · ${phrase} ${weekday}`, warning: true };
  }
  if (daysLeft < 0) return { text: `${storage} · check before using`, warning: true };
  if (daysLeft === 0) return { text: `${storage} · today`, warning: true };
  return { text: `${storage} · ~${daysLeft} ${daysLeft === 1 ? "day" : "days"}`, warning: false };
}

function amountOf(group: Group): KitchenRow["amount"] {
  const counted = group.batches.filter((b) => b.count !== null);
  if (group.countable && counted.length === group.batches.length) {
    const total = counted.reduce((sum, b) => sum + (b.count ?? 0), 0);
    const unit = counted[0]?.unit;
    return { kind: "count", text: unit ? `${total} ${unit}` : `${total}` };
  }
  return { kind: "level", level: LEVEL[firstToUse(group.batches).remaining_state] };
}

export function buildKitchenView(inventory: Inventory, today: Date): KitchenView {
  const rows = inventory.groups
    .filter((group) => group.batches.length > 0)
    .map((group): KitchenRow => {
      const section = sectionOf(group.batches);
      const detail = detailOf(section, firstToUse(group.batches), today);
      return {
        key: group.ingredient_id ?? `free:${group.name}`,
        name: group.name,
        section,
        detail: detail.text,
        detailIsWarning: detail.warning,
        amount: amountOf(group),
        inFreezer: group.batches.some((b) => b.storage === "freezer"),
        batchIds: group.batches.map((b) => b.id),
      };
    });

  const confirmations = inventory.groups.flatMap((g) => g.batches.map((b) => new Date(b.last_confirmed_at)));
  const latest = confirmations.reduce<Date | null>((a, b) => (a === null || b > a ? b : a), null);

  return {
    rows,
    counts: {
      all: rows.length,
      "use-soon": rows.filter((r) => r.section === "use-soon").length,
      "not-sure": rows.filter((r) => r.section === "not-sure").length,
    },
    daysSinceUpdate: latest === null ? null : daysBetween(latest, today),
  };
}

export function filterRows(rows: KitchenRow[], filter: KitchenFilter): KitchenRow[] {
  if (filter === "all") return rows;
  if (filter === "freezer") return rows.filter((r) => r.inFreezer);
  return rows.filter((r) => r.section === filter);
}
