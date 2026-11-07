import type { Schemas } from "../api/client";

type Counted = Pick<Schemas["InventoryItem"], "category" | "unit">;

/**
 * How far one tap of − or + moves a count. Produce kept in pieces is used a quarter at a time
 * (recipes take ¼ of a cabbage), so it steps by quarters; eggs and anything else by whole ones.
 */
export function countStep(item: Counted): number {
  return item.category === "produce" && item.unit === "pcs" ? 0.25 : 1;
}

/** One step up or down, kept on the step and never below zero. */
export function stepCount(count: number, step: number, direction: 1 | -1): number {
  return Math.max(0, Math.round((count + direction * step) / step) * step);
}

const QUARTERS = ["", "¼", "½", "¾"];

/** 0.25 → "¼", 1.5 → "1½"; anything that is not a whole quarter is shown as a decimal. */
export function formatCount(count: number): string {
  const quarters = count * 4;
  if (!Number.isInteger(quarters)) return `${Number(count.toFixed(2))}`;
  const whole = Math.floor(quarters / 4);
  const part = QUARTERS[quarters % 4]!;
  if (part === "") return `${whole}`;
  return whole === 0 ? part : `${whole}${part}`;
}
