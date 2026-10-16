import type { ReactNode } from "react";

type ChipProps = {
  selected?: boolean;
  /** A one-tap suggestion rather than a state: tinted instead of outlined. */
  suggested?: boolean;
  onClick?: () => void;
  children: ReactNode;
};

export function Chip({ selected = false, suggested = false, onClick, children }: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      onClick={onClick}
      className={`flex shrink-0 items-center rounded-pill px-[14px] py-[8px] text-[13px] font-semibold whitespace-nowrap ${
        selected
          ? "bg-dark text-surface"
          : suggested
            ? "bg-primary-soft text-primary"
            : "border border-border bg-surface text-ink"
      }`}
    >
      {children}
    </button>
  );
}
