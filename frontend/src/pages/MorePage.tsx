import { useMemo } from "react";
import { Link } from "react-router-dom";

import { useInventory, useMe } from "../api/queries";
import { Icon, type IconName } from "../components/Icon";
import { buildKitchenView } from "./kitchen/view";

const displayTitle = { fontVariationSettings: '"SOFT" 0, "WONK" 1' };

export function MorePage() {
  const me = useMe();
  const inventory = useInventory();
  const kitchen = useMemo(
    () => (inventory.data ? buildKitchenView(inventory.data, new Date()) : null),
    [inventory.data],
  );

  return (
    <div className="flex flex-col gap-[18px]">
      <h1 className="font-display text-[30px] leading-[1.2] font-semibold" style={displayTitle}>
        More
      </h1>

      {me.data && <HouseholdCard name={me.data.household.name} user={me.data.user} />}

      <div className="flex gap-[12px]">
        <Link to="/more/add" className="flex min-w-px flex-1 flex-col gap-[14px] rounded-lg bg-primary p-[16px]">
          <span className="flex size-[44px] items-center justify-center rounded-[14px] bg-white">
            <Icon name="plus" />
          </span>
          <span className="text-[17px] leading-[1.2] font-bold text-surface">Add Ingredients</span>
          <span className="text-[12px] text-surface">Receipt, photo or type</span>
        </Link>
        <Link
          to="/more/kitchen"
          className="flex min-w-px flex-1 flex-col gap-[14px] rounded-lg border border-border bg-surface p-[16px]"
        >
          <span className="flex size-[44px] items-center justify-center rounded-[14px] bg-fresh-soft">
            <Icon name="fridge" />
          </span>
          <span className="text-[17px] leading-[1.2] font-bold">My Kitchen</span>
          <span className="text-[12px] text-ink-muted">
            {kitchen
              ? `${kitchen.counts.all} ${kitchen.counts.all === 1 ? "item" : "items"} · ${kitchen.counts["use-soon"]} use soon`
              : " "}
          </span>
        </Link>
      </div>

      <nav aria-label="Settings" className="flex flex-col rounded-lg border border-border bg-surface px-[14px] py-[2px]">
        <SettingsRow
          to="/more/preferences"
          icon="sliders"
          tint="bg-info-soft"
          title="Preferences"
          detail="Diet, allergies, time, equipment, tastes"
        />
        <SettingsRow
          to="/more/history"
          icon="undo"
          tint="bg-fresh-soft"
          title="Kitchen history & undo"
          detail="Every purchase and meal, reversible"
        />
      </nav>
    </div>
  );
}

function HouseholdCard({ name, user }: { name: string; user: { email: string; display_name: string | null } }) {
  const initial = (user.display_name ?? user.email).charAt(0).toUpperCase();
  return (
    <div className="flex items-center gap-[12px] rounded-lg border border-border bg-surface p-[14px]">
      <span
        className="flex size-[40px] shrink-0 items-center justify-center rounded-pill border-2 border-surface bg-primary text-[15px] font-bold text-surface"
        aria-hidden
      >
        {initial}
      </span>
      <div className="flex min-w-px flex-1 flex-col gap-px">
        <p className="truncate text-[15px] font-bold">{name}</p>
        <p className="truncate text-[12px] text-ink-muted">{user.email}</p>
      </div>
    </div>
  );
}

type SettingsRowProps = {
  to: string;
  icon: IconName;
  tint: string;
  title: string;
  detail: string;
};

function SettingsRow({ to, icon, tint, title, detail }: SettingsRowProps) {
  return (
    <Link to={to} className="flex items-center gap-[12px] border-b border-border py-[12px] last:border-b-0">
      <span className={`flex size-[36px] shrink-0 items-center justify-center rounded-[12px] ${tint}`}>
        <Icon name={icon} />
      </span>
      <span className="flex min-w-px flex-1 flex-col gap-px">
        <span className="text-[15px] font-bold">{title}</span>
        <span className="text-[12px] text-ink-muted">{detail}</span>
      </span>
      <Icon name="chevron-right" />
    </Link>
  );
}
