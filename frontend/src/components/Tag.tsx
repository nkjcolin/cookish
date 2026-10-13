import type { ReactNode } from "react";

const tones = {
  muted: "bg-surface-sunken text-ink-muted",
  primary: "bg-primary-soft text-primary",
  info: "bg-info-soft text-info",
} as const;

export function Tag({ tone = "muted", children }: { tone?: keyof typeof tones; children: ReactNode }) {
  return (
    <span
      className={`flex shrink-0 items-center gap-[4px] rounded-pill px-[9px] py-[4px] text-[11.5px] font-semibold whitespace-nowrap ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

/** Where an item is kept; the freezer stands out because frozen food lasts far longer. */
export function StorageTag({ storage }: { storage: "pantry" | "fridge" | "freezer" }) {
  return (
    <Tag tone={storage === "freezer" ? "info" : "muted"}>{storage.charAt(0).toUpperCase() + storage.slice(1)}</Tag>
  );
}
