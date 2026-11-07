import type { Schemas } from "../api/client";
import { countStep } from "../lib/count";

export function readCount(value: string): number | null {
  if (!value.trim()) return null;
  const count = Number(value);
  return Number.isFinite(count) && count >= 0 ? count : null;
}

/** Ask for an actual amount in a known unit; a missing amount never defaults to zero. */
export function CountInput({ name, unit, category, value, onChange }: {
  name: string;
  unit: string;
  category: Schemas["IngredientCategory"];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex flex-col gap-[6px] text-[13px] font-semibold">
      Amount of {name} left ({unit === "pcs" ? "pieces" : unit})
      <input
        type="number"
        aria-label={`Amount of ${name} left (${unit === "pcs" ? "pieces" : unit})`}
        min={0}
        step={countStep({ category, unit })}
        value={value}
        placeholder="Enter amount"
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-md border border-border bg-surface px-[12px] py-[10px] text-[15px]"
      />
      <span className="text-[12px] font-normal text-ink-muted">Enter what you have now, or 0 if none is left.</span>
    </label>
  );
}
