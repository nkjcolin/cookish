import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import { Icon } from "./Icon";

/** The image alone keeps the overlay open; backdrop, Close and Escape dismiss it. */
export function PhotoPreviewDialog({ src, onClose }: { src: string; onClose: () => void }) {
  const closeButton = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButton.current?.focus();
    function keydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
      if (event.key === "Tab") {
        event.preventDefault();
        closeButton.current?.focus();
      }
    }
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, [onClose]);

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Uploaded photo preview"
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-dark/85 p-[20px]"
    >
      <button
        ref={closeButton}
        type="button"
        aria-label="Close photo preview"
        onClick={(event) => { event.stopPropagation(); onClose(); }}
        className="absolute top-[16px] right-[16px] flex size-[40px] items-center justify-center rounded-pill bg-surface"
      >
        <Icon name="x" />
      </button>
      <img
        src={src}
        alt="Uploaded receipt or grocery photo"
        onClick={(event) => event.stopPropagation()}
        className="max-h-[85dvh] max-w-full rounded-md object-contain"
      />
    </div>,
    document.body,
  );
}
