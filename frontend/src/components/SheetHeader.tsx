import { Icon } from "./Icon";

/** Title row of a bottom sheet, with the close button. */
export function SheetHeader({ id, title, onClose }: { id: string; title: string; onClose: () => void }) {
  return (
    <div className="flex items-center justify-between">
      <h2 id={id} className="font-display text-[24px] font-semibold" style={{ fontVariationSettings: '"SOFT" 0, "WONK" 1' }}>
        {title}
      </h2>
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="flex size-[36px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface"
      >
        <Icon name="x" />
      </button>
    </div>
  );
}
