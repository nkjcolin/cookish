import type { Schemas } from "../../api/client";
import { formatCount } from "../../lib/count";

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
  amount: { kind: "count"; text: string } | { kind: "level"; state: Batch["remaining_state"] };
  inFreezer: boolean;
  /** The batch that should be used first; this is the one the update sheet edits. */
  editBatch: Batch;
  batchCount: number;
};

export type KitchenView = {
  rows: KitchenRow[];
  counts: Record<Exclude<KitchenFilter, "freezer">, number>;
  /** Whole days since anything in the kitchen was last confirmed; null when empty. */
  daysSinceUpdate: number | null;
};

const DAY_MS = 24 * 60 * 60 * 1000;
const NEEDS_ATTENTION = new Set<Batch["freshness_status"]>(["use_soon", "check", "expired"]);

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

// Added by Role 2 (inventory). A row lands in the "use-soon" section when ANY of its batches
// needs attention (use soon, check or expired). The row's text used to come from the batch
// that is used first, which can be a different batch, so the line under the name did not
// explain why the row was listed. These helpers pick the batch that actually caused it.
const SEVERITY: Record<string, number> = { expired: 3, use_soon: 2, check: 1 };

/** The batch that put this row in the attention section: the most urgent one. */
function attentionBatch(batches: Batch[]): Batch | null {
  const flagged = batches.filter((b) => NEEDS_ATTENTION.has(b.freshness_status));
  if (flagged.length === 0) return null;
  return flagged.reduce((a, b) =>
    (SEVERITY[b.freshness_status] ?? 0) > (SEVERITY[a.freshness_status] ?? 0) ? b : a,
  );
}

function sectionOf(batches: Batch[]): KitchenSection {
  if (batches.every((b) => b.remaining_state === "unknown")) return "not-sure";
  if (batches.some((b) => NEEDS_ATTENTION.has(b.freshness_status))) return "use-soon";
  return "rest";
}

export function lastConfirmedText(batch: Batch, today: Date): string {
  const days = daysBetween(new Date(batch.last_confirmed_at), today);
  if (days <= 0) return "Last confirmed today";
  return `Last confirmed ${days} ${days === 1 ? "day" : "days"} ago`;
}

/** The line under "Stored in": what we know about when to use this batch, or null. */
export function freshnessNote(batch: Batch, today: Date): string | null {
  if (batch.label_date !== null) {
    const date = parseDate(batch.label_date).toLocaleDateString("en-GB", {
      weekday: "short",
      day: "numeric",
      month: "short",
    });
    const phrase = batch.label_date_kind === "use_by" ? "Use by" : "Best before";
    return `${phrase} ${date} — the date on the package.`;
  }
  if (batch.est_use_first_date === null) return null;
  const daysLeft = daysBetween(today, parseDate(batch.est_use_first_date));
  const estimate = "an estimate from storage type, not a food-safety date.";
  if (daysLeft < 0) return `Past its estimated use-first date. Check it before using — ${estimate}`;
  if (daysLeft === 0) return `Use today — ${estimate}`;
  return `Use within ~${daysLeft} ${daysLeft === 1 ? "day" : "days"} — ${estimate}`;
}

function detailOf(section: KitchenSection, batch: Batch, today: Date): { text: string; warning: boolean } {
  const storage = capitalise(batch.storage);
  if (section === "not-sure") return { text: lastConfirmedText(batch, today), warning: false };
  // Role 2: a batch with no date and no estimate has status "check". Say so, instead of
  // showing only the storage place, so the user can see why it is in this section.
  if (section === "use-soon" && batch.est_use_first_date === null) {
    return { text: `${storage} · no date, check it`, warning: true };
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
    return { kind: "count", text: unit ? `${formatCount(total)} ${unit}` : formatCount(total) };
  }
  return { kind: "level", state: firstToUse(group.batches).remaining_state };
}

export function buildKitchenView(inventory: Inventory, today: Date): KitchenView {
  // A used-up batch stays on record, for undo and so Cook knows it is gone, but is not
  // something in the kitchen any more.
  const rows = inventory.groups
    .map((group) => ({ ...group, batches: group.batches.filter((b) => b.remaining_state !== "out") }))
    .filter((group) => group.batches.length > 0)
    .map((group): KitchenRow => {
      const section = sectionOf(group.batches);
      const editBatch = firstToUse(group.batches);
      // Role 2: explain the batch that needs attention, not just the one used first.
      const explainer = section === "use-soon" ? (attentionBatch(group.batches) ?? editBatch) : editBatch;
      const detail = detailOf(section, explainer, today);
      return {
        key: group.ingredient_id ?? `free:${group.name}`,
        name: group.name,
        section,
        detail: detail.text,
        detailIsWarning: detail.warning,
        amount: amountOf(group),
        inFreezer: group.batches.some((b) => b.storage === "freezer"),
        editBatch,
        batchCount: group.batches.length,
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
