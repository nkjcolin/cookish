import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, idempotencyKey, unwrap, type Schemas } from "./client";

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => unwrap(await api.GET("/api/me")),
  });
}

export function useInventory() {
  return useQuery({
    queryKey: ["inventory"],
    queryFn: async () => unwrap(await api.GET("/api/inventory")),
  });
}

export function useUpdateInventoryItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ itemId, body }: { itemId: string; body: Schemas["InventoryItemUpdate"] }) =>
      unwrap(
        await api.PATCH("/api/inventory/items/{item_id}", {
          params: { path: { item_id: itemId }, header: idempotencyKey() },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inventory"] }),
  });
}
