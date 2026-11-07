import { describe, expect, it } from "vitest";

import type { Schemas } from "../../api/client";
import { groupByAisle } from "./view";

function item(name: string, category: Schemas["IngredientCategory"]): Schemas["BasketItem"] {
  return {
    id: name, ingredient_id: name, name, category, amount: "1", suggested_packs: null, needs_check: false,
    countable: false, purchase_unit: null, purchase_unit_size: null, purchase_unit_measure: null,
  };
}

describe("groupByAisle", () => {
  it("groups items in shop order and leaves out empty aisles", () => {
    const aisles = groupByAisle([item("rice", "grain"), item("salmon", "seafood"), item("cabbage", "produce"), item("pork", "meat")]);

    expect(aisles.map((a) => [a.title, a.items.map((i) => i.name)])).toEqual([
      ["Produce", ["cabbage"]],
      ["Meat & fish", ["salmon", "pork"]],
      ["Dry & pantry", ["rice"]],
    ]);
  });
});
