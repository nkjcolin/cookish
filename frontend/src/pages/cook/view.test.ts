import { describe, expect, it } from "vitest";

import type { Schemas } from "../../api/client";
import { describeAdjust, difficultyLabel, ingredientLines, mealName } from "./view";

function suggestion(statuses: [string, Schemas["IngredientStatus"]][]): Schemas["Suggestion"] {
  return {
    session_id: "s",
    recipe: { id: "r", title: "Dish", cuisine: "chinese", total_minutes: 20, difficulty: 1, servings: 2, taste_tags: [], starred: false },
    people: 2,
    ingredients: statuses.map(([name, status]) => ({ ingredient_id: name, name, amount: "", essential: true, status })),
    needs_check: [],
    freshness_check: [],
    has_previous: false,
    applied_constraints: { tags: [], max_minutes: null, max_difficulty: null },
  };
}

describe("ingredientLines", () => {
  it("lists what is on hand and leaves staples out", () => {
    const lines = ingredientLines(suggestion([["egg", "have"], ["tomato", "have"], ["soy sauce", "staple"]]));

    expect(lines).toEqual([{ tone: "ok", text: "Have: egg, tomato" }]);
  });

  it("says plainly what is uncertain, low, missing or needs a freshness check", () => {
    const lines = ingredientLines(
      suggestion([["rice", "unknown"], ["cabbage", "low"], ["tofu", "missing"], ["chicken thigh", "check"]]),
    );

    expect(lines.map((line) => line.text)).toEqual([
      "Running low: cabbage",
      "Need to buy: tofu",
      "Not sure: rice — we’ll ask",
      "Check first: chicken thigh",
    ]);
    expect(lines.every((line) => line.tone === "ask")).toBe(true);
  });
});

describe("labels", () => {
  it("names the three difficulty levels", () => {
    expect([1, 2, 3].map(difficultyLabel)).toEqual(["Easy", "Medium", "Involved"]);
  });

  it("picks the meal from the time of day", () => {
    expect(mealName(new Date(2026, 9, 13, 8))).toBe("breakfast");
    expect(mealName(new Date(2026, 9, 13, 12))).toBe("lunch");
    expect(mealName(new Date(2026, 9, 13, 18))).toBe("dinner");
  });
});

describe("describeAdjust", () => {
  it("lists what a request was understood as", () => {
    expect(describeAdjust({ tags: ["quicker", "less_oil"], max_minutes: 20 })).toBe("+ Quicker · + Less oil · ≤ 20 min");
  });

  it("admits when nothing was understood", () => {
    expect(describeAdjust({ tags: [] })).toBe("nothing we can change");
  });
});
