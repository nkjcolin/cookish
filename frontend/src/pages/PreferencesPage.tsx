import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import type { Schemas } from "../api/client";
import { useMe, useSavePreferences } from "../api/queries";
import { BottomBar } from "../components/BottomBar";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { Icon, type IconName } from "../components/Icon";
import {
  ALLERGEN_LABELS,
  CUISINE_LABELS,
  DIET_LABELS,
  EQUIPMENT_LABELS,
  summarise,
  toggled,
} from "../lib/labels";

// Every field is sent on save, so none of them is optional here.
type Update = Required<Schemas["PreferencesUpdate"]>;
type Row = "people" | "equipment" | "time";

const DEFAULTS: Update = {
  allergens: [],
  diets: [],
  equipment: [],
  cuisines: [],
  disliked_ingredient_ids: [],
  max_cook_minutes: null,
  max_difficulty: null,
  household_size: 2,
};
const TIME_LIMITS = [15, 30, 45, 60];
const sectionTitle = "text-[12px] font-bold tracking-[0.72px] text-ink-muted uppercase";
const card = "rounded-lg border border-border bg-surface";

function keys<K extends string>(labels: Record<K, string>): K[] {
  return Object.keys(labels) as K[];
}

export function PreferencesPage() {
  const me = useMe();
  const save = useSavePreferences();
  const [editingRules, setEditingRules] = useState(false);
  const [openRow, setOpenRow] = useState<Row | null>(null);
  const [draft, setDraft] = useState<Update | null>(null);
  const [saved, setSaved] = useState(false);

  const stored = me.data?.preferences;
  const prefs: Update = draft ?? (stored
    ? {
        allergens: stored.allergens,
        diets: stored.diets,
        equipment: stored.equipment,
        cuisines: stored.cuisines,
        disliked_ingredient_ids: stored.disliked_ingredient_ids,
        max_cook_minutes: stored.max_cook_minutes,
        max_difficulty: stored.max_difficulty,
        household_size: stored.household_size,
      }
    : DEFAULTS);

  function change(patch: Partial<Update>) {
    setDraft((current) => ({ ...(current ?? prefs), ...patch }));
    setSaved(false);
  }

  function persist() {
    if (!draft) return;
    save.mutate(draft, { onSuccess: () => { setDraft(null); setSaved(true); } });
  }
  const toggleRow = (row: Row) => setOpenRow((open) => (open === row ? null : row));
  const rules = [...prefs.diets.map((d) => DIET_LABELS[d]), ...prefs.allergens.map((a) => ALLERGEN_LABELS[a])];

  return (
    <div className="flex flex-col gap-[16px] pb-[40px]">
      <div className="flex items-center justify-between">
        <Link
          to="/more"
          aria-label="Back"
          className="flex size-[40px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface"
        >
          <Icon name="chevron-left" />
        </Link>
        <h1 className="text-[16px] font-bold whitespace-nowrap">Preferences</h1>
        <span className="size-[40px]" />
      </div>

      {me.isPending && <p className="text-[14px] text-ink-muted">Loading…</p>}
      {(me.isError || save.isError) && (
        <p role="alert" className="text-[13px] text-danger">
          {(me.error ?? save.error)?.message}
        </p>
      )}

      {me.data && (
        <fieldset disabled={save.isPending} className="flex min-w-0 flex-col gap-[16px] disabled:opacity-70">
          <h2 className={sectionTitle}>Hard rules</h2>
          <section className={`${card} flex flex-col gap-[12px] p-[16px]`}>
            <div className="flex items-center gap-[8px]">
              <Icon name="lock" />
              <p className="min-w-px flex-1 text-[13px] font-semibold text-ink-muted">
                Never broken, never relaxed automatically
              </p>
              <button
                type="button"
                onClick={() => setEditingRules((editing) => !editing)}
                className="text-[13px] font-bold whitespace-nowrap text-primary"
              >
                {editingRules ? "Done" : "Edit"}
              </button>
            </div>
            {editingRules ? (
              <>
                <ChipGroup label="Diet">
                  {keys(DIET_LABELS).map((diet) => (
                    <Chip
                      key={diet}
                      selected={prefs.diets.includes(diet)}
                      onClick={() => change({ diets: toggled(prefs.diets, diet) })}
                    >
                      {DIET_LABELS[diet]}
                    </Chip>
                  ))}
                </ChipGroup>
                <ChipGroup label="Allergies">
                  {keys(ALLERGEN_LABELS).map((allergen) => (
                    <Chip
                      key={allergen}
                      selected={prefs.allergens.includes(allergen)}
                      onClick={() => change({ allergens: toggled(prefs.allergens, allergen) })}
                    >
                      {ALLERGEN_LABELS[allergen]}
                    </Chip>
                  ))}
                </ChipGroup>
              </>
            ) : rules.length > 0 ? (
              <div className="flex flex-wrap content-start items-start gap-[8px]">
                {rules.map((rule) => (
                  <span
                    key={rule}
                    className="rounded-pill bg-dark px-[14px] py-[8px] text-[13px] font-semibold whitespace-nowrap text-surface"
                  >
                    {rule}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-[13px] text-ink-muted">No diet rules or allergies set.</p>
            )}
          </section>

          <section className={`${card} flex flex-col px-[14px] py-[2px]`}>
            <SettingRow
              icon="users"
              title="Cooking for"
              value={`${prefs.household_size} ${prefs.household_size === 1 ? "person" : "people"}`}
              open={openRow === "people"}
              onToggle={() => toggleRow("people")}
            >
              <div className="flex items-center gap-[16px]">
                <RoundButton
                  label="One fewer"
                  disabled={prefs.household_size <= 1}
                  onClick={() => change({ household_size: prefs.household_size - 1 })}
                >
                  −
                </RoundButton>
                <p className="text-[15px] font-bold" aria-live="polite">
                  {prefs.household_size}
                </p>
                <RoundButton
                  label="One more"
                  disabled={prefs.household_size >= 12}
                  onClick={() => change({ household_size: prefs.household_size + 1 })}
                >
                  +
                </RoundButton>
              </div>
            </SettingRow>
            <SettingRow
              icon="pot-ink"
              title="Equipment"
              value={summarise(prefs.equipment.map((e) => EQUIPMENT_LABELS[e]))}
              open={openRow === "equipment"}
              onToggle={() => toggleRow("equipment")}
            >
              <div className="flex flex-wrap gap-[8px]">
                {keys(EQUIPMENT_LABELS).map((equipment) => (
                  <Chip
                    key={equipment}
                    selected={prefs.equipment.includes(equipment)}
                    onClick={() => change({ equipment: toggled(prefs.equipment, equipment) })}
                  >
                    {EQUIPMENT_LABELS[equipment]}
                  </Chip>
                ))}
              </div>
            </SettingRow>
            <SettingRow
              icon="clock"
              title="Time limit"
              value={prefs.max_cook_minutes ? `Up to ${prefs.max_cook_minutes} min` : "No limit"}
              open={openRow === "time"}
              onToggle={() => toggleRow("time")}
            >
              <div className="flex flex-wrap gap-[8px]">
                {TIME_LIMITS.map((minutes) => (
                  <Chip
                    key={minutes}
                    selected={prefs.max_cook_minutes === minutes}
                    onClick={() => change({ max_cook_minutes: minutes })}
                  >
                    {minutes} min
                  </Chip>
                ))}
                <Chip selected={prefs.max_cook_minutes === null} onClick={() => change({ max_cook_minutes: null })}>
                  No limit
                </Chip>
              </div>
            </SettingRow>
          </section>

          <h2 className={sectionTitle}>Cuisines you like</h2>
          <section className={`${card} flex flex-wrap content-start items-start gap-[8px] p-[16px]`}>
            {keys(CUISINE_LABELS).map((cuisine) => (
              <Chip
                key={cuisine}
                selected={prefs.cuisines.includes(cuisine)}
                onClick={() => change({ cuisines: toggled(prefs.cuisines, cuisine) })}
              >
                {CUISINE_LABELS[cuisine]}
              </Chip>
            ))}
          </section>
        </fieldset>
      )}
      {me.data && (
        <BottomBar>
          <div className="flex flex-col gap-[8px]">
            {draft ? (
              <p className="text-[12px] text-ink-muted">Unsaved changes. Saving refreshes Cook and Buy and clears shopping-list ticks.</p>
            ) : saved ? (
              <p role="status" className="text-[12px] text-fresh">Preferences saved.</p>
            ) : null}
            <Button className="w-full" onClick={persist} disabled={!draft || save.isPending}>
              {save.isPending ? "Saving…" : "Save preferences"}
            </Button>
          </div>
        </BottomBar>
      )}
    </div>
  );
}

function ChipGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="group" aria-label={label} className="flex flex-col gap-[8px]">
      <p className="text-[13px] font-bold">{label}</p>
      <div className="flex flex-wrap content-start items-start gap-[8px]">{children}</div>
    </div>
  );
}

type SettingRowProps = {
  icon: IconName;
  title: string;
  value: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
};

function SettingRow({ icon, title, value, open, onToggle, children }: SettingRowProps) {
  return (
    <div className="border-b border-border last:border-b-0">
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="flex w-full items-center gap-[12px] py-[13px] text-left"
      >
        <span className="flex w-[18px] shrink-0 justify-center">
          <Icon name={icon} />
        </span>
        <span className="min-w-px flex-1 text-[14px] font-bold">{title}</span>
        <span className="text-[13px] whitespace-nowrap text-ink-muted">{value}</span>
        <Icon name="chevron-right-sm" />
      </button>
      {open && <div className="pb-[13px]">{children}</div>}
    </div>
  );
}

function RoundButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="flex size-[36px] items-center justify-center rounded-pill border border-border bg-surface text-[18px] font-bold disabled:opacity-40"
    >
      {children}
    </button>
  );
}
