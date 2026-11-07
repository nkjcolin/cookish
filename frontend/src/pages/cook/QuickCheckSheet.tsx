import { useRef, useState, type ReactNode } from "react";

import type { Schemas } from "../../api/client";
import { useRecipe } from "../../api/cook";
import { useUpdateInventoryItem } from "../../api/queries";
import { Button } from "../../components/Button";
import { CountInput, readCount } from "../../components/CountInput";
import { Icon, type IconName } from "../../components/Icon";
import { Segmented } from "../../components/Segmented";
import { Sheet } from "../../components/Sheet";
import { SheetHeader } from "../../components/SheetHeader";
import { FRESHNESS_REASONS } from "./view";

type StockAnswer = "enough" | "low" | "out";
type FreshAnswer = "fine" | "discard";
type Item = Schemas["InventoryItem"];
type Changes = Omit<Schemas["InventoryItemUpdate"], "revision">;

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
  const [counts, setCounts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const savedItems = useRef<Record<string, { signature: string; revision: number }>>({});
  const hasCountedItems = [...stockChecks, ...freshChecks].some(({ item }) => item.countable);
  const recipe = useRecipe(hasCountedItems ? suggestion.recipe.id : undefined);
  const updateItem = useUpdateInventoryItem();
  const count = stockChecks.length + freshChecks.length;
  const failure = updateItem.error;
  const unitFor = (item: Item) => recipe.data?.ingredients.find((line) => line.ingredient_id === item.ingredient_id)?.unit;
  const countText = (item: Item) => counts[item.id] ?? (item.count !== null && item.unit === unitFor(item) ? String(item.count) : "");
  const checkedCount = (item: Item) => unitFor(item) ? readCount(countText(item)) : null;
  const needsFreshCount = (item: Item) => item.countable && (item.count === null || item.unit !== unitFor(item) || item.remaining_state === "unknown");
  const ready = stockChecks.every(({ item }) => item.countable ? checkedCount(item) !== null : Boolean(stock[item.id])) &&
    freshChecks.every(({ item }) => fresh[item.id] && (fresh[item.id] === "discard" || !needsFreshCount(item) || checkedCount(item) !== null));

  function countedChanges(item: Item): Changes {
    const amount = checkedCount(item)!;
    return { count: amount, unit: unitFor(item), remaining_state: amount === 0 ? "out" : "enough" };
  }

  function amountInput(item: Item) {
    const unit = unitFor(item);
    if (!unit) return <p className="text-[13px] text-ink-muted">Waiting for the recipe’s amount unit.</p>;
    return <CountInput name={item.display_name} unit={unit} category={item.category} value={countText(item)} onChange={(value) => setCounts((current) => ({ ...current, [item.id]: value }))} />;
  }

  // Each answer updates the batch the question was about.
  async function save() {
    if (!ready || saving) return;
    setSaving(true);
    const updates = new Map<string, { item: Item; changes: Changes }>();
    for (const { item } of stockChecks) {
      updates.set(item.id, { item, changes: item.countable ? countedChanges(item) : { remaining_state: stock[item.id] } });
    }
    for (const { item } of freshChecks) {
      const changes: Changes = fresh[item.id] === "fine"
        ? { ...(needsFreshCount(item) ? countedChanges(item) : {}), freshness_confirmed: true }
        : { remaining_state: "out", ...(item.countable ? { count: 0 } : {}) };
      updates.set(item.id, {
        item, changes: { ...updates.get(item.id)?.changes, ...changes },
      });
    }
    try {
      for (const { item, changes } of updates.values()) {
        const previous = savedItems.current[item.id];
        const signature = JSON.stringify(changes);
        if (previous?.signature === signature) continue;
        const result = await updateItem.mutateAsync({ itemId: item.id, body: { revision: previous?.revision ?? item.revision, ...changes } });
        const updated = result.items.find((batch) => batch.id === item.id);
        savedItems.current[item.id] = { signature, revision: updated?.revision ?? item.revision + 1 };
      }
      const missing = [...updates.values()].some(({ changes }) => changes.remaining_state === "out");
      if (missing) onUnavailable();
      else onProceed();
    } catch {
      // Show the mutation error and retain answers; a retry skips already-saved batches.
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet labelledBy={TITLE_ID} onClose={() => { if (!saving) onClose(); }}>
      <SheetHeader id={TITLE_ID} title="Quick check" onClose={() => { if (!saving) onClose(); }} />
      <p className="text-[14px] leading-[1.45] text-ink-muted">
        {suggestion.recipe.title} needs {count} {count === 1 ? "thing" : "things"} we’re not sure about.
      </p>

      {hasCountedItems && recipe.isError && (
        <div role="alert" className="text-[13px] text-danger">
          Could not load the recipe’s amounts. <button type="button" className="font-semibold underline" onClick={() => void recipe.refetch()}>Try again</button>
        </div>
      )}
      <fieldset disabled={saving} className="flex min-w-0 flex-col gap-[16px]">
      {stockChecks.map(({ item }) => (
        <CheckCard key={item.id} icon="box" tint="bg-info-soft" name={item.display_name} detail="Not sure if you still have it">
          {item.countable ? amountInput(item) : <Segmented
            label={`Do you have ${item.display_name}?`}
            options={STOCK_OPTIONS}
            value={stock[item.id] ?? null}
            onChange={(answer) => setStock({ ...stock, [item.id]: answer })}
          />}
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
          {fresh[item.id] === "fine" && needsFreshCount(item) && amountInput(item)}
        </CheckCard>
      ))}
      </fieldset>

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

      <Button className="w-full shrink-0" onClick={() => void save()} disabled={saving || !ready}>
        {saving ? "Saving…" : "Show recipe"}
      </Button>
      <button type="button" onClick={onClose} disabled={saving} className="text-center text-[14px] font-semibold text-ink-muted">
        Check later
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
