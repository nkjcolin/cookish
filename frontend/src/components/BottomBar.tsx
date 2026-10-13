import type { ReactNode } from "react";

/** Action bar pinned to the bottom of screens that have no tab bar. */
export function BottomBar({ children }: { children: ReactNode }) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-10 mx-auto flex max-w-[390px] flex-col border-t border-border bg-surface px-[20px] pt-[14px] pb-[30px]">
      {children}
    </div>
  );
}
