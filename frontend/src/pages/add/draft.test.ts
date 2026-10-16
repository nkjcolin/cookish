import { describe, expect, it } from "vitest";

import type { Schemas } from "../../api/client";
import { draftLabel, isUncertain, toInventoryItems } from "./draft";

function draft(overrides: Partial<Schemas["DraftItem"]> = {}): Schemas["DraftItem"] {
  return {
    raw_text: null,
    ingredient_id: "egg",
    display_name: "Eggs",
    count: 6,
    unit: "pcs",
    storage: "fridge",
    confidence: 0.9,
    ...overrides,
  };
}

describe("draftLabel", () => {
  it("shows a plain count for pieces and keeps other units", () => {
    expect(draftLabel(draft())).toBe("Eggs · 6");
    expect(draftLabel(draft({ display_name: "Tofu", count: 2, unit: "pack" }))).toBe("Tofu · 2 pack");
  });

  it("shows only the name when the amount is unknown", () => {
    expect(draftLabel(draft({ display_name: "Cabbage", count: null, unit: null }))).toBe("Cabbage");
  });
});

describe("toInventoryItems", () => {
  it("keeps an unknown amount unknown instead of inventing one", () => {
    const [item] = toInventoryItems([draft({ count: null, unit: "pcs" })]);

    expect(item).toMatchObject({ count: null, unit: null });
  });

  it("keeps free-text items that matched nothing in the catalogue", () => {
    const [item] = toInventoryItems([draft({ ingredient_id: null, display_name: "Sambal", storage: null })]);

    expect(item).toEqual({
      ingredient_id: null,
      display_name: "Sambal",
      count: 6,
      unit: "pcs",
      remaining_state: "enough",
      storage: null,
    });
  });
});

describe("isUncertain", () => {
  it("flags only low-confidence readings", () => {
    expect(isUncertain(draft({ confidence: 0.41 }))).toBe(true);
    expect(isUncertain(draft({ confidence: 0.88 }))).toBe(false);
  });
});
