import { Outlet } from "react-router-dom";

import { TabBar } from "./TabBar";

/**
 * The phone-width column every screen sits in. Screens that end in their own action bar
 * (see BottomBar) are rendered without the tab bar.
 */
export function AppLayout({ tabBar = true }: { tabBar?: boolean }) {
  return (
    <div className="mx-auto min-h-dvh max-w-[390px] bg-bg">
      <main className={`px-[20px] pt-[16px] ${tabBar ? "pb-[112px]" : "pb-[120px]"}`}>
        <Outlet />
      </main>
      {tabBar && <TabBar />}
    </div>
  );
}
