export type LevelName = "plenty" | "some" | "a-bit" | "almost-out" | "unsure";

const filled = { plenty: 4, some: 3, "a-bit": 2, "almost-out": 1, unsure: 0 } as const;
const label = { plenty: "Plenty", some: "Some", "a-bit": "A bit", "almost-out": "Almost out", unsure: "Not sure" } as const;
const bar = { plenty: "bg-fresh", some: "bg-fresh", "a-bit": "bg-warn", "almost-out": "bg-danger", unsure: "" } as const;
const text = {
  plenty: "text-fresh",
  some: "text-fresh",
  "a-bit": "text-warn",
  "almost-out": "text-danger",
  unsure: "text-ink-muted",
} as const;

/** Coarse stock level. Cookish never converts these into grams. */
export function Level({ level }: { level: LevelName }) {
  return (
    <div className="flex shrink-0 items-center gap-[8px]">
      <div className="flex items-start gap-[3px]" aria-hidden>
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={`h-[6px] w-[10px] rounded-[3px] ${
              level === "unsure"
                ? "border border-dashed border-ink-subtle"
                : i < filled[level]
                  ? bar[level]
                  : "bg-border"
            }`}
          />
        ))}
      </div>
      <p className={`text-[12px] font-semibold whitespace-nowrap ${text[level]}`}>{label[level]}</p>
    </div>
  );
}
