import { describe, expect, it } from "vitest";

import { summarise, toggled } from "./labels";

describe("summarise", () => {
  it("lists a few names and counts the rest", () => {
    expect(summarise(["Stove", "Rice cooker", "Microwave", "Oven"])).toBe("Stove, rice cooker +2");
    expect(summarise(["Stove", "Oven"])).toBe("Stove, oven");
    expect(summarise([])).toBe("None");
  });
});

describe("toggled", () => {
  it("adds a missing value and removes a present one", () => {
    expect(toggled(["a"], "b")).toEqual(["a", "b"]);
    expect(toggled(["a", "b"], "a")).toEqual(["b"]);
  });
});
