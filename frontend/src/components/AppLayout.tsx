import { Outlet } from "react-router-dom";

import { TabBar } from "./TabBar";

/** The phone-width column every screen sits in, with the tab bar pinned to the bottom. */
export function AppLayout() {
  return (
    <div className="mx-auto min-h-dvh max-w-[390px] bg-bg">
      <main className="px-[20px] pt-[16px] pb-[112px]">
        <Outlet />
      </main>
      <TabBar />
    </div>
  );
}
