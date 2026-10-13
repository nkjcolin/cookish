import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, idempotencyKey, unwrap, type Schemas } from "./client";

type Basket = Schemas["Basket"];

const BASKET_KEY = ["shop", "basket"];
const CART_KEY = ["shop", "cart"];

/** The current Shop session's basket. Starts on first visit, then stays in the cache. */
export function useBasket() {
  return useQuery({
    queryKey: BASKET_KEY,
    queryFn: async () => unwrap(await api.POST("/api/shop/sessions", { body: {} })),
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
  });
}

export function useAdjustBasket(sessionId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: Schemas["ShopAdjust"]): Promise<Basket> =>
      unwrap(
        await api.POST("/api/shop/sessions/{session_id}/adjust", {
          params: { path: { session_id: sessionId! } },
          body,
        }),
      ),
    onSuccess: (basket) => queryClient.setQueryData(BASKET_KEY, basket),
  });
}

/**
 * Items ticked off while walking round the shop. Kept in the cache rather than in a
 * component so that the list and the confirm screen see the same ticks.
 */
export function useCart(): { inCart: string[]; toggle: (itemId: string) => void } {
  const queryClient = useQueryClient();
  const { data } = useQuery<string[]>({
    queryKey: CART_KEY,
    queryFn: () => [],
    initialData: [],
    staleTime: Infinity,
    gcTime: Infinity,
  });
  return {
    inCart: data,
    toggle: (itemId) =>
      queryClient.setQueryData<string[]>(CART_KEY, (current = []) =>
        current.includes(itemId) ? current.filter((id) => id !== itemId) : [...current, itemId],
      ),
  };
}

/** Adds what was actually bought to the kitchen. */
export function useConfirmBasket(basketId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (lines: Schemas["BoughtLine"][]) =>
      unwrap(
        await api.POST("/api/shop/baskets/{basket_id}/confirm", {
          params: { path: { basket_id: basketId! }, header: idempotencyKey() },
          body: { lines },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["inventory"] }),
  });
}

/** After a purchase is confirmed: empty the cart so the next visit builds a new basket. */
export function useFinishShopping() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.setQueryData(CART_KEY, []);
    queryClient.removeQueries({ queryKey: BASKET_KEY });
  };
}
