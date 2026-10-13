import { useState } from "react";

import type { Schemas } from "../../api/client";
import { Button } from "../../components/Button";
import { Chip } from "../../components/Chip";
import { Segmented } from "../../components/Segmented";
import { Sheet } from "../../components/Sheet";
import { SheetHeader } from "../../components/SheetHeader";
import { toggled } from "../../lib/labels";
import { SHOP_TAG_LABELS } from "./view";

type ShopTag = Schemas["ShopTag"];
type ShopAdjust = Schemas["ShopAdjust"];

const MEAL_OPTIONS = ["3", "4", "5"].map((value) => ({ value, label: value }));
const TITLE_ID = "adjust-basket-title";

type AdjustBasketSheetProps = {
  basket: Schemas["Basket"];
  onApply: (adjust: ShopAdjust) => void;
  onClose: () => void;
};

export function AdjustBasketSheet({ basket, onApply, onClose }: AdjustBasketSheetProps) {
  const [meals, setMeals] = useState(basket.meals);
  const [people, setPeople] = useState(basket.people);
  const [tags, setTags] = useState<ShopTag[]>(basket.applied_tags);

  function apply() {
    // Adjustments accumulate on the server, so only what changed here is sent.
    const adjust: ShopAdjust = { tags: tags.filter((tag) => !basket.applied_tags.includes(tag)) };
    if (meals !== basket.meals) adjust.meals = meals;
    if (people !== basket.people) adjust.people = people;
    const changed = adjust.tags!.length > 0 || adjust.meals !== undefined || adjust.people !== undefined;
    if (changed) onApply(adjust);
    onClose();
  }

  return (
    <Sheet labelledBy={TITLE_ID} onClose={onClose}>
      <SheetHeader id={TITLE_ID} title="Adjust basket" onClose={onClose} />

      <div className="flex flex-col gap-[8px]">
        <p className="text-[15px] font-bold">How many meals?</p>
        <Segmented
          label="How many meals?"
          options={MEAL_OPTIONS}
          value={String(meals)}
          onChange={(value) => setMeals(Number(value))}
        />
      </div>

      <div className="flex flex-col gap-[8px]">
        <p className="text-[15px] font-bold">For how many people?</p>
        <div className="flex items-center gap-[16px]">
          <StepButton label="One fewer" disabled={people <= 1} onClick={() => setPeople(people - 1)}>
            −
          </StepButton>
          <p className="text-[15px] font-bold" aria-live="polite">
            {people} {people === 1 ? "person" : "people"}
          </p>
          <StepButton label="One more" disabled={people >= 12} onClick={() => setPeople(people + 1)}>
            +
          </StepButton>
        </div>
      </div>

      <div className="flex flex-col gap-[8px]">
        <p className="text-[15px] font-bold">Keywords</p>
        <div className="flex flex-wrap content-start items-start gap-[8px]">
          {(Object.keys(SHOP_TAG_LABELS) as ShopTag[]).map((tag) => (
            <Chip key={tag} selected={tags.includes(tag)} onClick={() => setTags(toggled(tags, tag))}>
              {SHOP_TAG_LABELS[tag]}
            </Chip>
          ))}
        </div>
      </div>

      <Button className="w-full shrink-0" onClick={apply}>
        Update list
      </Button>
    </Sheet>
  );
}

function StepButton({
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
