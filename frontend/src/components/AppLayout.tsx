import { NavLink, Outlet } from "react-router-dom";

const tabs = [
  { to: "/kitchen", label: "Kitchen" },
  { to: "/cook", label: "Cook" },
  { to: "/shop", label: "Shop" },
  { to: "/activity", label: "Activity" },
];

export function AppLayout() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col bg-white text-neutral-900">
      <main className="flex-1 px-4 pt-6 pb-20">
        <Outlet />
      </main>
      <nav className="fixed inset-x-0 bottom-0 mx-auto flex max-w-md border-t border-neutral-200 bg-white">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              `flex-1 py-3 text-center text-sm ${isActive ? "font-semibold text-neutral-900" : "text-neutral-500"}`
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
