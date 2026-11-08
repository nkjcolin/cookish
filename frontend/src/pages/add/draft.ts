import type { Schemas } from "../../api/client";

type DraftItem = Schemas["DraftItem"];

/** "Eggs · 6" for counted items, just the name otherwise. */
export function draftLabel(item: DraftItem): string {
  if (item.count === null) return item.display_name;
  const amount = item.unit && item.unit !== "pcs" ? `${item.count} ${item.unit}` : `${item.count}`;
  return `${item.display_name} · ${amount}`;
}

/**
 * What a reviewed draft becomes when it is saved. Just bought, so there is enough; unknown amounts stay unknown.
 * The backend matches the name to the catalogue.
 */
export function toInventoryItems(draft: DraftItem[]): Schemas["InventoryItemCreate"][] {
  return draft.map((item) => ({
    display_name: item.display_name,
    count: item.count,
    unit: item.count === null ? null : item.unit,
    remaining_state: "enough",
    storage: item.storage,
  }));
}

/** Handed from Add Ingredients to the review screen through router state. */
export type ReviewState = {
  items: DraftItem[];
  source: Schemas["ItemSource"];
  /** References a tab-local preview; photo bytes are never put into router history. */
  imageJobId?: string;
};

/** Below this confidence the user is asked instead of trusted to notice. */
const ASK_BELOW_CONFIDENCE = 0.6;

export function isUncertain(item: DraftItem): boolean {
  return item.confidence < ASK_BELOW_CONFIDENCE;
}
