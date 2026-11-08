import type { Schemas } from "../api/client";

export function kitchenBatch(overrides: Partial<Schemas["InventoryItem"]> = {}): Schemas["InventoryItem"] {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    ingredient_id: "22222222-2222-4222-8222-222222222222",
    display_name: "Eggs", category: "egg", countable: true, count: 8, unit: "pcs",
    remaining_state: "enough", storage: "fridge", source: "receipt", revision: 3,
    acquired_at: "2026-11-08", label_date: null, label_date_kind: null,
    est_use_first_date: null, freshness_status: "ok", freshness_confirmed_at: null,
    last_confirmed_at: new Date().toISOString(),
    ...overrides,
  };
}

export function kitchenInventory(batches: Schemas["InventoryItem"][]): Schemas["Inventory"] {
  const groups = new Map<string, Schemas["InventoryGroup"]>();
  for (const batch of batches) {
    const key = batch.ingredient_id ?? batch.display_name;
    const group = groups.get(key);
    if (group) group.batches.push(batch);
    else groups.set(key, {
      ingredient_id: batch.ingredient_id, name: batch.display_name,
      category: batch.category, countable: batch.countable, batches: [batch],
    });
  }
  return { groups: [...groups.values()] };
}
