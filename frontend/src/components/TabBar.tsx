import { NavLink } from "react-router-dom";

import { Icon, type IconName } from "./Icon";

const tabs: { to: string; label: string; icon: IconName; activeIcon: IconName }[] = [
  { to: "/cook", label: "Cook", icon: "pot", activeIcon: "pot-active" },
  { to: "/buy", label: "Buy", icon: "cart", activeIcon: "cart-active" },
  { to: "/more", label: "More", icon: "grid", activeIcon: "grid-active" },
];

export function TabBar() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-10 mx-auto flex h-[84px] max-w-[390px] items-start justify-between border-t border-border bg-surface px-[36px] pt-[10px] pb-[28px]">
      {tabs.map((tab) => (
        <NavLink key={tab.to} to={tab.to} className="flex w-[84px] flex-col items-center gap-[4px]">
          {({ isActive }) => (
            <>
              <span className={`flex rounded-pill px-[18px] py-[4px] ${isActive ? "bg-primary-soft" : ""}`}>
                <Icon name={isActive ? tab.activeIcon : tab.icon} />
              </span>
              <span
                className={`text-[12px] whitespace-nowrap ${
                  isActive ? "font-bold text-primary" : "font-medium text-ink-subtle"
                }`}
              >
                {tab.label}
              </span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
