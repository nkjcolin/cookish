import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import type { Schemas } from "../api/client";
import { useSavePreferences } from "../api/queries";
import { Button } from "../components/Button";
import { Chip } from "../components/Chip";
import { Icon, type IconName } from "../components/Icon";
import { Tag } from "../components/Tag";
import { ALLERGEN_NAMES, CUISINE_LABELS, DIET_LABELS, EQUIPMENT_LABELS, toggled } from "../lib/labels";

type Preferences = Required<Schemas["PreferencesUpdate"]>;

const displayFont = { fontVariationSettings: '"SOFT" 0, "WONK" 1' };
const previewImage = {
  backgroundImage: "linear-gradient(135deg, rgb(214, 237, 204) 0%, rgb(92, 153, 102) 83.333%)",
};
const TIME_OPTIONS = [
  { minutes: 15, label: "15 min" },
  { minutes: 30, label: "30 min" },
  { minutes: 45, label: "45 min" },
  { minutes: 60, label: "1 hr+" },
];
const START: Preferences = {
  allergens: [],
  diets: [],
  equipment: ["stove"],
  cuisines: [],
  disliked_ingredient_ids: [],
  max_cook_minutes: 30,
  max_difficulty: null,
  household_size: 2,
};

function keys<K extends string>(labels: Record<K, string>): K[] {
  return Object.keys(labels) as K[];
}

/** First launch: a welcome, then two short questions. Everything can be changed later. */
export function OnboardingPage() {
  const navigate = useNavigate();
  const save = useSavePreferences();
  const [step, setStep] = useState<0 | 1 | 2>(0);
  const [prefs, setPrefs] = useState<Preferences>(START);
  const set = (patch: Partial<Preferences>) => setPrefs((current) => ({ ...current, ...patch }));

  return (
    <div className="mx-auto flex min-h-dvh max-w-[390px] flex-col bg-bg px-[20px] pb-[36px]">
      {step === 0 && <Welcome onStart={() => setStep(1)} />}

      {step === 1 && (
        <Step number={1} onBack={() => setStep(0)}>
          <StepTitle title="Anything you never eat?">
            These are hard rules. Cookish will never suggest a recipe that breaks them.
          </StepTitle>

          <ChipGroup title="Diet">
            <Chip selected={prefs.diets.length === 0} onClick={() => set({ diets: [] })}>
              None
            </Chip>
            {keys(DIET_LABELS).map((diet) => (
              <Chip key={diet} selected={prefs.diets.includes(diet)} onClick={() => set({ diets: toggled(prefs.diets, diet) })}>
                {DIET_LABELS[diet]}
              </Chip>
            ))}
          </ChipGroup>

          <ChipGroup title="Allergies & intolerances">
            {keys(ALLERGEN_NAMES).map((allergen) => (
              <Chip
                key={allergen}
                selected={prefs.allergens.includes(allergen)}
                onClick={() => set({ allergens: toggled(prefs.allergens, allergen) })}
              >
                {ALLERGEN_NAMES[allergen]}
              </Chip>
            ))}
          </ChipGroup>

          <div className="flex items-center gap-[12px] rounded-lg border border-border bg-surface px-[16px] py-[14px]">
            <div className="flex min-w-px flex-1 flex-col gap-[2px]">
              <p className="text-[15px] font-bold">Cooking for</p>
              <p className="text-[13px] text-ink-muted">Portions & basket size</p>
            </div>
            <div className="flex shrink-0 items-center gap-[14px]">
              <button
                type="button"
                aria-label="One fewer"
                disabled={prefs.household_size <= 1}
                onClick={() => set({ household_size: prefs.household_size - 1 })}
                className="flex size-[40px] items-center justify-center rounded-pill border border-border bg-surface disabled:opacity-40"
              >
                <Icon name="minus" />
              </button>
              <p className="text-[18px] font-bold whitespace-nowrap" aria-live="polite">
                {prefs.household_size}
              </p>
              <button
                type="button"
                aria-label="One more"
                disabled={prefs.household_size >= 12}
                onClick={() => set({ household_size: prefs.household_size + 1 })}
                className="flex size-[40px] items-center justify-center rounded-pill bg-dark disabled:opacity-40"
              >
                <Icon name="plus-white" />
              </button>
            </div>
          </div>

          <Note icon="lock-fresh" tone="fresh">
            Soft tastes (like “less spicy”) are learned later — you don’t need to list them.
          </Note>

          <span className="min-h-px flex-1" />
          <Button className="w-full shrink-0" onClick={() => setStep(2)}>
            Continue
          </Button>
        </Step>
      )}

      {step === 2 && (
        <Step number={2} onBack={() => setStep(1)}>
          <StepTitle title="How do you usually cook?">
            A rough answer is fine. You can change any of this later in More › Preferences.
          </StepTitle>

          <div className="flex flex-col gap-[10px]">
            <p className="text-[15px] font-bold">Weeknight cooking time</p>
            <div role="radiogroup" aria-label="Weeknight cooking time" className="flex gap-[4px] rounded-md bg-surface-sunken p-[4px]">
              {TIME_OPTIONS.map((option) => {
                const selected = prefs.max_cook_minutes === option.minutes;
                return (
                  <button
                    key={option.minutes}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => set({ max_cook_minutes: option.minutes })}
                    className={`flex min-w-px flex-1 items-center justify-center rounded-[10px] py-[10px] text-[14px] whitespace-nowrap ${
                      selected ? "bg-surface font-bold text-ink shadow-[0px_1px_3px_0px_rgba(0,0,0,0.08)]" : "font-medium text-ink-muted"
                    }`}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          </div>

          <ChipGroup title="What’s in your kitchen?">
            {keys(EQUIPMENT_LABELS).map((equipment) => (
              <Chip
                key={equipment}
                selected={prefs.equipment.includes(equipment)}
                onClick={() => set({ equipment: toggled(prefs.equipment, equipment) })}
              >
                {EQUIPMENT_LABELS[equipment]}
              </Chip>
            ))}
          </ChipGroup>

          <ChipGroup title="Cuisines you enjoy" hint="Optional — just a starting point">
            {keys(CUISINE_LABELS).map((cuisine) => (
              <Chip
                key={cuisine}
                selected={prefs.cuisines.includes(cuisine)}
                onClick={() => set({ cuisines: toggled(prefs.cuisines, cuisine) })}
              >
                {CUISINE_LABELS[cuisine]}
              </Chip>
            ))}
          </ChipGroup>

          <Note icon="sparkle-lg" tone="primary">
            Cookish learns the rest from how you rate what you cook.
          </Note>

          {save.isError && (
            <p role="alert" className="text-[13px] text-danger">
              Could not save: {save.error.message}
            </p>
          )}
          <span className="min-h-px flex-1" />
          <Button
            className="w-full shrink-0"
            disabled={save.isPending}
            onClick={() => save.mutate(prefs, { onSuccess: () => navigate("/cook", { replace: true }) })}
          >
            Start cooking
          </Button>
        </Step>
      )}
    </div>
  );
}

function Welcome({ onStart }: { onStart: () => void }) {
  return (
    <div className="flex flex-1 flex-col gap-[28px] pt-[40px]">
      <div className="flex items-center gap-[10px]">
        <span className="flex size-[44px] items-center justify-center rounded-md bg-primary">
          <Icon name="pot-white" />
        </span>
        <p className="font-display text-[28px] font-semibold whitespace-nowrap" style={displayFont}>
          Cookish
        </p>
      </div>

      <div className="flex flex-col gap-[10px]">
        <h1 className="font-display text-[40px] leading-[1.1] font-semibold" style={displayFont}>
          Dinner, decided.
        </h1>
        <p className="text-[16px] leading-[1.5] text-ink-muted">
          Tell us roughly what’s in your kitchen. We’ll tell you what to cook tonight — and what to pick up on the way
          home.
        </p>
      </div>

      {/* A picture of the product, not a control: nothing in it can be pressed. */}
      <div className="relative h-[210px] w-full" aria-hidden>
        <div className="absolute top-[10px] left-[32px] h-[120px] w-[300px] rotate-4 rounded-lg border border-border bg-surface opacity-55" />
        <div className="absolute top-[30px] left-[10px] flex h-[170px] w-[330px] flex-col gap-[12px] rounded-lg border border-border bg-surface p-[14px] shadow-[0px_10px_28px_0px_rgba(89,51,26,0.12)]">
          <div className="flex items-center gap-[14px]">
            <span className="flex size-[84px] shrink-0 items-center justify-center rounded-[14px]" style={previewImage}>
              <span className="opacity-92">
                <Icon name="leaf-white" />
              </span>
            </span>
            <div className="flex min-w-px flex-1 flex-col gap-[6px]">
              <p className="text-[11px] font-bold tracking-[0.88px] text-primary">TONIGHT</p>
              <p className="text-[17px] leading-[1.25] font-bold">Garlic kai lan & egg tofu</p>
              <div className="flex items-start gap-[6px]">
                <Tag>
                  <Icon name="clock-sm" />
                  20 min
                </Tag>
                <Tag tone="fresh">
                  <Icon name="check-fresh-sm" />3 in stock
                </Tag>
              </div>
            </div>
          </div>
          <div className="flex gap-[8px]">
            <span className="flex h-[40px] min-w-px flex-1 items-center justify-center rounded-md border border-border bg-surface text-[15px] font-bold">
              Not tonight
            </span>
            <span className="flex h-[40px] min-w-px flex-1 items-center justify-center rounded-md bg-primary text-[15px] font-bold text-white">
              Cook this
            </span>
          </div>
        </div>
      </div>

      <ul className="flex flex-col gap-[14px]">
        <Benefit icon="sparkle" tint="bg-primary-soft">
          Learns what you like from how you rate meals
        </Benefit>
        <Benefit icon="leaf-fresh" tint="bg-fresh-soft">
          “Running low on cabbage” is precise enough
        </Benefit>
        <Benefit icon="cart-info" tint="bg-info-soft">
          One suggestion, not another meal plan
        </Benefit>
      </ul>

      <span className="min-h-px flex-1" />
      <div className="flex flex-col items-center gap-[10px]">
        <Button className="w-full" onClick={onStart}>
          Get started
        </Button>
        <Link to="/cook" className="text-[14px] font-semibold whitespace-nowrap text-ink-muted">
          I already have an account
        </Link>
      </div>
    </div>
  );
}

function Benefit({ icon, tint, children }: { icon: IconName; tint: string; children: ReactNode }) {
  return (
    <li className="flex items-center gap-[12px]">
      <span className={`flex size-[32px] shrink-0 items-center justify-center rounded-pill ${tint}`}>
        <Icon name={icon} />
      </span>
      <p className="text-[14px] font-medium">{children}</p>
    </li>
  );
}

function Step({ number, onBack, children }: { number: 1 | 2; onBack: () => void; children: ReactNode }) {
  return (
    <div className="flex flex-1 flex-col gap-[24px] pt-[16px]">
      <div className="flex items-center gap-[12px]">
        <button
          type="button"
          aria-label="Back"
          onClick={onBack}
          className="flex size-[40px] shrink-0 items-center justify-center rounded-pill border border-border bg-surface"
        >
          <Icon name="chevron-left" />
        </button>
        <div className="flex min-w-px flex-1 gap-[6px]" aria-hidden>
          <span className="h-[6px] min-w-px flex-1 rounded-[3px] bg-primary" />
          <span className={`h-[6px] min-w-px flex-1 rounded-[3px] ${number === 2 ? "bg-primary" : "bg-border"}`} />
        </div>
        <p className="text-[13px] font-semibold whitespace-nowrap text-ink-muted">
          <span className="sr-only">Step </span>
          {number} / 2
        </p>
      </div>
      {children}
    </div>
  );
}

function StepTitle({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-[8px]">
      <h1 className="font-display text-[30px] leading-[1.15] font-semibold" style={displayFont}>
        {title}
      </h1>
      <p className="text-[15px] leading-[1.5] text-ink-muted">{children}</p>
    </div>
  );
}

function ChipGroup({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <div role="group" aria-label={title} className="flex flex-col gap-[10px]">
      <p className="text-[15px] font-bold">{title}</p>
      {hint && <p className="text-[13px] text-ink-muted">{hint}</p>}
      <div className="flex flex-wrap content-start items-start gap-[8px]">{children}</div>
    </div>
  );
}

function Note({ icon, tone, children }: { icon: IconName; tone: "fresh" | "primary"; children: ReactNode }) {
  return (
    <div
      className={`flex items-center gap-[10px] rounded-md px-[14px] py-[12px] ${
        tone === "fresh" ? "bg-fresh-soft text-fresh" : "bg-primary-soft text-primary"
      }`}
    >
      <Icon name={icon} />
      <p className={`min-w-px flex-1 text-[13px] ${tone === "fresh" ? "font-medium" : "font-semibold"}`}>{children}</p>
    </div>
  );
}
