import type { Schemas } from "../../api/client";

type DraftItem = Schemas["DraftItem"];

/** "Eggs · 6" for counted items, just the name otherwise. */
export function draftLabel(item: DraftItem): string {
  if (item.count === null) return item.display_name;
  const amount = item.unit && item.unit !== "pcs" ? `${item.count} ${item.unit}` : `${item.count}`;
  return `${item.display_name} · ${amount}`;
}

/** What a reviewed draft becomes when it is saved. Just bought, so there is enough; unknown amounts stay unknown. */
export function toInventoryItems(draft: DraftItem[]): Schemas["InventoryItemCreate"][] {
  return draft.map((item) => ({
    ingredient_id: item.ingredient_id,
    display_name: item.display_name,
    count: item.count,
    unit: item.count === null ? null : item.unit,
    remaining_state: "enough",
    storage: item.storage,
  }));
}
