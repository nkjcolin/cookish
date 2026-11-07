import { describe, expect, it } from "vitest";

import type { Schemas } from "../../api/client";
import { buildKitchenView, filterRows, freshnessNote } from "./view";

type Batch = Schemas["InventoryItem"];

const TODAY = new Date(2026, 9, 12); // Monday 12 October 2026

function batch(overrides: Partial<Batch> = {}): Batch {
  return {
    id: crypto.randomUUID(),
    ingredient_id: "ingredient",
    display_name: "Thing",
    category: "produce",
    countable: false,
    count: null,
    unit: null,
    remaining_state: "enough",
    storage: "fridge",
    source: "manual",
    acquired_at: "2026-10-10",
    label_date: null,
    label_date_kind: null,
    est_use_first_date: null,
    freshness_status: "ok",
    freshness_confirmed_at: null,
    last_confirmed_at: "2026-10-11T08:00:00Z",
    revision: 1,
    ...overrides,
  };
}

function group(name: string, batches: Batch[], countable = false): Schemas["InventoryGroup"] {
  return { ingredient_id: name, name, category: "produce", countable, batches };
}

function rowFor(batches: Batch[], countable = false) {
  return buildKitchenView({ groups: [group("Thing", batches, countable)] }, TODAY).rows[0]!;
}

describe("buildKitchenView", () => {
  it("adds up the batches of a countable ingredient", () => {
    const row = rowFor([batch({ count: 2, unit: "pcs" }), batch({ count: 6, unit: "pcs" })], true);

    expect(row.amount).toEqual({ kind: "count", text: "8 pcs" });
  });

  it("shows part pieces as fractions", () => {
    const row = rowFor([batch({ count: 0.5, unit: "pcs" }), batch({ count: 1.25, unit: "pcs" })], true);

    expect(row.amount).toEqual({ kind: "count", text: "1¾ pcs" });
  });

  it("leaves out used-up batches, and the ingredient once all of it is used up", () => {
    const usedUp = batch({ count: 0, unit: "pcs", remaining_state: "out" });
    const row = rowFor([usedUp, batch({ count: 2, unit: "pcs" })], true);

    expect(row.amount).toEqual({ kind: "count", text: "2 pcs" });
    expect(row.batchCount).toBe(1);
    expect(buildKitchenView({ groups: [group("Cabbage", [usedUp], true)] }, TODAY).rows).toEqual([]);
  });

  it("shows a level, never a number, when any batch has no count", () => {
    const row = rowFor([batch({ count: 2, unit: "pcs" }), batch({ remaining_state: "low" })], true);

    expect(row.amount.kind).toBe("level");
  });

  it("describes the batch that should be used first", () => {
    const soonest = batch({ est_use_first_date: "2026-10-14", freshness_status: "use_soon" });
    const row = rowFor([batch({ est_use_first_date: "2026-10-26", freshness_status: "ok" }), soonest]);

    expect(row.editBatch).toBe(soonest);
    expect(row.batchCount).toBe(2);

    expect(row.section).toBe("use-soon");
    expect(row.detail).toBe("Fridge · ~2 days");
    expect(row.detailIsWarning).toBe(false);
  });

  it("highlights a date printed on the package", () => {
    const row = rowFor([
      batch({
        est_use_first_date: "2026-10-15",
        label_date: "2026-10-15",
        label_date_kind: "best_before",
        freshness_status: "use_soon",
      }),
    ]);

    expect(row.detail).toBe("Fridge · best by Thu");
    expect(row.detailIsWarning).toBe(true);
  });

  it("asks for a check instead of counting down past the estimate", () => {
    const row = rowFor([batch({ est_use_first_date: "2026-10-11", freshness_status: "check" })]);

    expect(row.detail).toBe("Fridge · check before using");
    expect(row.detailIsWarning).toBe(true);
  });

  it("puts ingredients of unknown stock under Not sure", () => {
    const row = rowFor([batch({ remaining_state: "unknown", last_confirmed_at: "2026-10-03T08:00:00Z" })]);

    expect(row.section).toBe("not-sure");
    expect(row.detail).toBe("Last confirmed 9 days ago");
    expect(row.amount).toEqual({ kind: "level", state: "unknown" });
  });

  it("counts rows per filter and measures time since the latest confirmation", () => {
    const view = buildKitchenView(
      {
        groups: [
          group("Chicken", [batch({ freshness_status: "use_soon", est_use_first_date: "2026-10-13" })]),
          group("Rice", [batch({ remaining_state: "unknown", last_confirmed_at: "2026-10-01T08:00:00Z" })]),
          group("Peas", [batch({ storage: "freezer", last_confirmed_at: "2026-10-08T08:00:00Z" })]),
        ],
      },
      TODAY,
    );

    expect(view.counts).toEqual({ all: 3, "use-soon": 1, "not-sure": 1 });
    expect(view.daysSinceUpdate).toBe(1);
    expect(filterRows(view.rows, "freezer").map((r) => r.name)).toEqual(["Peas"]);
    expect(filterRows(view.rows, "not-sure").map((r) => r.name)).toEqual(["Rice"]);
  });

  it("reports no update time for an empty kitchen", () => {
    expect(buildKitchenView({ groups: [] }, TODAY).daysSinceUpdate).toBeNull();
  });
});

describe("freshnessNote", () => {
  it("labels an estimate as an estimate", () => {
    expect(freshnessNote(batch({ est_use_first_date: "2026-10-15" }), TODAY)).toBe(
      "Use within ~3 days — an estimate from storage type, not a food-safety date.",
    );
  });

  it("quotes a package date as a package date", () => {
    const labelled = batch({ est_use_first_date: "2026-10-15", label_date: "2026-10-15", label_date_kind: "use_by" });

    expect(freshnessNote(labelled, TODAY)).toBe("Use by Thu 15 Oct — the date on the package.");
  });

  it("asks for a check once the estimate has passed", () => {
    expect(freshnessNote(batch({ est_use_first_date: "2026-10-10" }), TODAY)).toMatch(/^Past its estimated/);
  });

  it("says nothing when there is no date", () => {
    expect(freshnessNote(batch(), TODAY)).toBeNull();
  });
});
