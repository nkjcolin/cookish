import type { Schemas } from "../api/client";

type RemainingState = Schemas["RemainingState"];

// The four states of the contract, drawn with the design's level bars.
const filled: Record<RemainingState, number> = { enough: 4, low: 2, out: 1, unknown: 0 };
const bar: Record<RemainingState, string> = { enough: "bg-fresh", low: "bg-warn", out: "bg-danger", unknown: "" };
const text: Record<RemainingState, string> = {
  enough: "text-fresh",
  low: "text-warn",
  out: "text-danger",
  unknown: "text-ink-muted",
};

export const LEVEL_LABELS: Record<RemainingState, string> = {
  enough: "Enough",
  low: "Running low",
  out: "Out",
  unknown: "Not sure",
};

/** Coarse stock level. Cookish never converts these into grams. */
export function Level({ state }: { state: RemainingState }) {
  return (
    <div className="flex shrink-0 items-center gap-[8px]">
      <div className="flex items-start gap-[3px]" aria-hidden>
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={`h-[6px] w-[10px] rounded-[3px] ${
              state === "unknown"
                ? "border border-dashed border-ink-subtle"
                : i < filled[state]
                  ? bar[state]
                  : "bg-border"
            }`}
          />
        ))}
      </div>
      <p className={`text-[12px] font-semibold whitespace-nowrap ${text[state]}`}>{LEVEL_LABELS[state]}</p>
    </div>
  );
}
