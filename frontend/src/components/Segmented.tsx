type SegmentedProps<T extends string> = {
  label: string;
  options: { value: T; label: string }[];
  value: T | null;
  onChange: (value: T) => void;
};

/** A row of equal pills where exactly one can be chosen. */
export function Segmented<T extends string>({ label, options, value, onChange }: SegmentedProps<T>) {
  return (
    <div role="radiogroup" aria-label={label} className="flex gap-[6px]">
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={`flex min-w-px flex-1 items-center justify-center rounded-pill py-[9px] text-[13px] font-bold whitespace-nowrap ${
              selected ? "bg-dark text-surface" : "border border-border bg-surface text-ink"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
