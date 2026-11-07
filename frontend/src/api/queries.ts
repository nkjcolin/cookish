import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, idempotencyKey, unwrap, type Schemas } from "./client";
import { invalidateAfterStockChange, resetAfterPreferencesChange } from "./stockCache";

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
    onSuccess: () => invalidateAfterStockChange(queryClient),
  });
}

/** Reads a typed or spoken list. Only when the user asks: typing alone never calls the model. */
export function useParseItems() {
  return useMutation({
    mutationFn: async (body: Schemas["ParseItemsRequest"]) =>
      unwrap(await api.POST("/ai/parse-items", { body })),
  });
}

export function useParseImage() {
  return useMutation({
    mutationFn: async (body: Schemas["ParseImageRequest"]) =>
      unwrap(await api.POST("/ai/parse-image", { body })),
  });
}

export function useAddInventoryItems() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["InventoryItemsCreate"]) =>
      unwrap(await api.POST("/api/inventory/items", { params: { header: idempotencyKey() }, body })),
    onSuccess: () => invalidateAfterStockChange(queryClient),
  });
}

export function useSavePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["PreferencesUpdate"]) =>
      unwrap(await api.PUT("/api/household/preferences", { body })),
    onSuccess: async (preferences) => {
      queryClient.setQueryData<Schemas["Me"]>(["me"], (me) => (me ? { ...me, preferences } : me));
      await resetAfterPreferencesChange(queryClient);
    },
  });
}

/** Resolve metadata by ID, never by a fuzzy name match, before asking for a counted amount. */
export function useInventoryIngredient(item: Schemas["InventoryItem"]) {
  return useQuery({
    queryKey: ["ingredient", item.ingredient_id],
    queryFn: async () => {
      const result = unwrap(await api.GET("/api/ingredients", {
        params: { query: { q: item.display_name.slice(0, 50), ingredient_id: item.ingredient_id!, limit: 1 } },
      }));
      return result.items.find((ingredient) => ingredient.id === item.ingredient_id) ?? null;
    },
    enabled: item.countable && item.ingredient_id !== null,
    staleTime: Infinity,
  });
}

export function useUndoStockEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (eventId: string) =>
      unwrap(
        await api.POST("/api/stock-events/{event_id}/undo", {
          params: { path: { event_id: eventId }, header: idempotencyKey() },
        }),
      ),
    onSuccess: () => invalidateAfterStockChange(queryClient),
  });
}
