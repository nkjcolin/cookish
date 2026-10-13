import { useState, type ReactNode } from "react";

import type { Schemas } from "../../api/client";
import { useAddInventoryItems, useUpdateInventoryItem } from "../../api/queries";
import { Button } from "../../components/Button";
import { Icon, type IconName } from "../../components/Icon";
import { Segmented } from "../../components/Segmented";
import { Sheet } from "../../components/Sheet";
import { SheetHeader } from "../../components/SheetHeader";
import { FRESHNESS_REASONS } from "./view";

type StockAnswer = "enough" | "low" | "out";
type FreshAnswer = "fine" | "discard";

const STOCK_OPTIONS: { value: StockAnswer; label: string }[] = [
  { value: "enough", label: "Have it" },
  { value: "low", label: "Running low" },
  { value: "out", label: "No" },
];
const FRESH_OPTIONS: { value: FreshAnswer; label: string }[] = [
  { value: "fine", label: "It’s fine" },
  { value: "discard", label: "Throw away" },
];
const TITLE_ID = "quick-check-title";

type QuickCheckSheetProps = {
  suggestion: Schemas["Suggestion"];
  /** Everything needed is there: carry on to the recipe. */
  onProceed: () => void;
  /** Something essential turned out to be missing: look for another dish. */
  onUnavailable: () => void;
  onClose: () => void;
};

/**
 * Asked only when it matters: before cooking a dish whose essential ingredients are of
 * unknown stock or past their date. The answers are recorded in the inventory.
 */
export function QuickCheckSheet({ suggestion, onProceed, onUnavailable, onClose }: QuickCheckSheetProps) {
  const { needs_check: stockChecks, freshness_check: freshChecks } = suggestion;
  const [stock, setStock] = useState<Record<string, StockAnswer>>({});
  const [fresh, setFresh] = useState<Record<string, FreshAnswer>>({});
  const addItems = useAddInventoryItems();
  const updateItem = useUpdateInventoryItem();
  const count = stockChecks.length + freshChecks.length;
  const saving = addItems.isPending || updateItem.isPending;
  const failure = addItems.error ?? updateItem.error;

  async function save() {
    const answered = stockChecks.filter((check) => stock[check.ingredient_id]);
    if (answered.length > 0) {
      await addItems.mutateAsync({
        source: "manual",
        items: answered.map((check) => ({
          ingredient_id: check.ingredient_id,
          remaining_state: stock[check.ingredient_id]!,
        })),
      });
    }
    for (const { item } of freshChecks) {
      const answer = fresh[item.id];
      if (!answer) continue;
      await updateItem.mutateAsync({
        itemId: item.id,
        body:
          answer === "fine"
            ? { revision: item.revision, freshness_confirmed: true }
            : { revision: item.revision, remaining_state: "out" },
      });
    }
    const missing = Object.values(stock).includes("out") || Object.values(fresh).includes("discard");
    if (missing) onUnavailable();
    else onProceed();
  }

  return (
    <Sheet labelledBy={TITLE_ID} onClose={onClose}>
      <SheetHeader id={TITLE_ID} title="Quick check" onClose={onClose} />
      <p className="text-[14px] leading-[1.45] text-ink-muted">
        {suggestion.recipe.title} needs {count} {count === 1 ? "thing" : "things"} we’re not sure about.
      </p>

      {stockChecks.map((check) => (
        <CheckCard key={check.ingredient_id} icon="box" tint="bg-info-soft" name={check.name} detail="Not sure if you still have it">
          <Segmented
            label={`Do you have ${check.name}?`}
            options={STOCK_OPTIONS}
            value={stock[check.ingredient_id] ?? null}
            onChange={(answer) => setStock({ ...stock, [check.ingredient_id]: answer })}
          />
        </CheckCard>
      ))}

      {freshChecks.map(({ item, reason }) => (
        <CheckCard key={item.id} icon="leaf" tint="bg-warn-soft" name={item.display_name} detail={FRESHNESS_REASONS[reason]}>
          <Segmented
            label={`Is the ${item.display_name} still good?`}
            options={FRESH_OPTIONS}
            value={fresh[item.id] ?? null}
            onChange={(answer) => setFresh({ ...fresh, [item.id]: answer })}
          />
        </CheckCard>
      ))}

      {freshChecks.length > 0 && (
        <p className="text-[12px] text-ink-muted">
          Check the package date and how it was stored. Our dates are estimates and cannot tell you food is safe.
        </p>
      )}
      {failure && (
        <p role="alert" className="text-[13px] text-danger">
          Could not save your answers: {failure.message}
        </p>
      )}

      <Button className="w-full shrink-0" onClick={() => void save()} disabled={saving}>
        Show recipe
      </Button>
      <button type="button" onClick={onProceed} disabled={saving} className="text-center text-[14px] font-semibold text-ink-muted">
        Skip — I’ll figure it out
      </button>
    </Sheet>
  );
}

type CheckCardProps = {
  icon: IconName;
  tint: string;
  name: string;
  detail: string;
  children: ReactNode;
};

function CheckCard({ icon, tint, name, detail, children }: CheckCardProps) {
  return (
    <div className="flex flex-col gap-[12px] rounded-md border border-border bg-surface p-[14px]">
      <div className="flex items-center gap-[12px]">
        <span className={`flex size-[40px] shrink-0 items-center justify-center rounded-[12px] ${tint}`}>
          <Icon name={icon} />
        </span>
        <div className="flex min-w-px flex-1 flex-col gap-px">
          <p className="text-[15px] font-bold first-letter:uppercase">{name}</p>
          <p className="text-[12px] text-ink-muted">{detail}</p>
        </div>
      </div>
      {children}
    </div>
  );
}
