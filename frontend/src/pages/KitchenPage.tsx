import { useInventory } from "../api/queries";

// Placeholder: proves the path browser → typed client → backend. Replaced by the real design.
export function KitchenPage() {
  const inventory = useInventory();

  if (inventory.isPending) return <p className="text-neutral-500">Loading…</p>;
  if (inventory.isError) return <p role="alert">Could not load your kitchen: {inventory.error.message}</p>;

  return (
    <section>
      <h1 className="text-xl font-semibold">Kitchen</h1>
      <ul className="mt-4 divide-y divide-neutral-200">
        {inventory.data.groups.map((group) => (
          <li key={group.ingredient_id ?? group.name} className="py-3">
            <p className="font-medium">{group.name}</p>
            {group.batches.map((batch) => (
              <p key={batch.id} className="text-sm text-neutral-600">
                {batch.count !== null ? `${batch.count} ${batch.unit ?? ""}` : batch.remaining_state}
                {" · "}
                {batch.storage}
                {" · "}
                {batch.freshness_status}
              </p>
            ))}
          </li>
        ))}
      </ul>
    </section>
  );
}
