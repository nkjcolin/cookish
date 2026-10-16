import { useEffect, useRef, type ReactNode } from "react";

import { Icon } from "./Icon";

type ToastProps = {
  children: ReactNode;
  /** Label and handler of the single action, such as Undo. */
  action?: { label: string; onClick: () => void; disabled?: boolean };
  onDismiss: () => void;
  /** Sits above the tab bar by default; pass false on screens without one. */
  aboveTabBar?: boolean;
};

const VISIBLE_MS = 8000;

/** A short confirmation that goes away by itself. */
export function Toast({ children, action, onDismiss, aboveTabBar = true }: ToastProps) {
  // Callers pass a new function on every render; the timer must not restart because of it.
  const dismiss = useRef(onDismiss);
  useEffect(() => {
    dismiss.current = onDismiss;
  });
  useEffect(() => {
    const timer = setTimeout(() => dismiss.current(), VISIBLE_MS);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div
      role="status"
      className={`fixed inset-x-0 z-10 mx-auto flex max-w-[350px] items-center gap-[10px] rounded-[14px] bg-dark px-[16px] py-[12px] shadow-[0px_8px_20px_0px_rgba(0,0,0,0.18)] ${
        aboveTabBar ? "bottom-[96px]" : "bottom-[24px]"
      }`}
    >
      <Icon name="check-toast" />
      <p className="min-w-px flex-1 text-[14px] font-semibold text-surface">{children}</p>
      {action && (
        <button
          type="button"
          onClick={action.onClick}
          disabled={action.disabled}
          className="shrink-0 text-[14px] font-bold whitespace-nowrap text-[#ffb28f] disabled:opacity-50"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
