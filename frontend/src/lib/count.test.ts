import { describe, expect, it } from "vitest";

import { countStep, formatCount, stepCount } from "./count";

describe("countStep", () => {
  it("steps produce kept in pieces by quarters, everything else by ones", () => {
    expect(countStep({ category: "produce", unit: "pcs" })).toBe(0.25);
    expect(countStep({ category: "egg", unit: "pcs" })).toBe(1);
    expect(countStep({ category: "produce", unit: null })).toBe(1);
  });
});

describe("stepCount", () => {
  it("moves by one step and never below zero", () => {
    expect(stepCount(0.5, 0.25, -1)).toBe(0.25);
    expect(stepCount(0.25, 0.25, -1)).toBe(0);
    expect(stepCount(0, 0.25, -1)).toBe(0);
    expect(stepCount(0.5, 1, -1)).toBe(0);
    expect(stepCount(2, 1, 1)).toBe(3);
  });

  it("lands back on the step when the count was off it", () => {
    expect(stepCount(0.3, 0.25, 1)).toBe(0.5);
  });
});

describe("formatCount", () => {
  it("shows quarters as fractions", () => {
    expect(formatCount(0.25)).toBe("¼");
    expect(formatCount(0.5)).toBe("½");
    expect(formatCount(1.75)).toBe("1¾");
    expect(formatCount(3)).toBe("3");
    expect(formatCount(0)).toBe("0");
  });

  it("falls back to a short decimal", () => {
    expect(formatCount(0.333333)).toBe("0.33");
  });
});
