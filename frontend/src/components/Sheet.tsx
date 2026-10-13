import { useEffect, type ReactNode } from "react";

type SheetProps = {
  /** id of the element that titles the sheet. */
  labelledBy: string;
  onClose: () => void;
  children: ReactNode;
};

/** Bottom sheet over the current screen. Closes on Escape or a tap outside. */
export function Sheet({ labelledBy, onClose, children }: SheetProps) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-20">
      <div className="absolute inset-0 bg-dark/40" onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        className="absolute inset-x-0 bottom-0 mx-auto flex max-h-[92dvh] max-w-[390px] flex-col gap-[16px] overflow-y-auto rounded-t-[24px] bg-surface px-[20px] pt-[10px] pb-[34px]"
      >
        <div className="flex shrink-0 justify-center" aria-hidden>
          <span className="h-[5px] w-[40px] rounded-[3px] bg-border" />
        </div>
        {children}
      </div>
    </div>
  );
}
