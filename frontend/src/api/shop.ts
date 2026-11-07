import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, idempotencyKey, isNotFound, unwrap, type Schemas } from "./client";
import { BASKET_KEY, CART_KEY, CART_REVIEW_KEY, EMPTY_REVIEW, invalidateAfterStockChange, type CartReview } from "./stockCache";

type Basket = Schemas["Basket"];

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
    mutationFn: async (body: Schemas["ShopAdjust"]): Promise<Basket> => {
      try {
        return unwrap(
          await api.POST("/api/shop/sessions/{session_id}/adjust", { params: { path: { session_id: sessionId! } }, body }),
        );
      } catch (error) {
        // The session has expired: start a new one held to the same conditions.
        const current = queryClient.getQueryData<Basket>(BASKET_KEY);
        if (!isNotFound(error) || !current) throw error;
        const people = body.people ?? current.people;
        const addsMeal = body.tags?.includes("cover_more_meals") &&
          (!body.replace_tags || !current.applied_tags.includes("cover_more_meals"));
        const meals = body.meals ?? Math.min(7, current.meals + (addsMeal ? 1 : 0));
        const fresh = unwrap(await api.POST("/api/shop/sessions", {
          body: { people, meals, recipe_ids: current.requested_recipe_ids ?? [] },
        }));
        const tags = body.replace_tags ? (body.tags ?? []) : [...new Set([...current.applied_tags, ...(body.tags ?? [])])];
        if (tags.length === 0) return fresh;
        return unwrap(
          await api.POST("/api/shop/sessions/{session_id}/adjust", {
            params: { path: { session_id: fresh.session_id } },
            // Meal count is already resolved above; replaying a saved keyword must not add one.
            body: { tags, replace_tags: true, meals },
          }),
        );
      }
    },
    onSuccess: (basket) => {
      const previous = queryClient.getQueryData<Basket>(BASKET_KEY);
      const cart = queryClient.getQueryData<string[]>(CART_KEY) ?? [];
      const review = queryClient.getQueryData<CartReview>(CART_REVIEW_KEY) ?? EMPTY_REVIEW;
      const selected = new Map(previous?.items.filter((item) => cart.includes(item.id)).map((item) => [item.ingredient_id, item]));
      const kept = basket.items.filter((item) => selected.has(item.ingredient_id));
      queryClient.setQueryData(CART_KEY, kept.map((item) => item.id));
      queryClient.setQueryData<CartReview>(CART_REVIEW_KEY, {
        hasMadeSelection: review.hasMadeSelection || cart.length > 0,
        quantityReviewIds: kept.filter((item) => {
          const old = selected.get(item.ingredient_id)!;
          return item.countable && (
            review.quantityReviewIds.includes(old.id) || item.amount !== old.amount ||
            item.suggested_packs !== old.suggested_packs || item.purchase_unit !== old.purchase_unit ||
            item.purchase_unit_size !== old.purchase_unit_size || item.purchase_unit_measure !== old.purchase_unit_measure
          );
        }).map((item) => item.id),
      });
      queryClient.setQueryData(BASKET_KEY, basket);
    },
  });
}

/**
 * Items ticked off while walking round the shop. Kept in the cache rather than in a
 * component so that the list and the confirm screen see the same ticks.
 */
export function useCart(): { inCart: string[]; toggle: (itemId: string) => void } & CartReview {
  const queryClient = useQueryClient();
  const { data } = useQuery<string[]>({
    queryKey: CART_KEY,
    queryFn: () => [],
    initialData: [],
    staleTime: Infinity,
    gcTime: Infinity,
  });
  const { data: review } = useQuery<CartReview>({
    queryKey: CART_REVIEW_KEY,
    queryFn: () => EMPTY_REVIEW,
    initialData: EMPTY_REVIEW,
    staleTime: Infinity,
    gcTime: Infinity,
  });
  return {
    inCart: data,
    ...review,
    // Existing selections also cover a cart populated before review metadata existed.
    hasMadeSelection: review.hasMadeSelection || data.length > 0,
    toggle: (itemId) => {
      queryClient.setQueryData<CartReview>(CART_REVIEW_KEY, (current = EMPTY_REVIEW) => ({ ...current, hasMadeSelection: true }));
      queryClient.setQueryData<string[]>(CART_KEY, (current = []) =>
        current.includes(itemId) ? current.filter((id) => id !== itemId) : [...current, itemId],
      );
    },
  };
}

/**
 * "Go to Buy" from a recipe: a new basket that includes it, replacing the current one, so the
 * list holds what this dish still needs.
 */
export function useShopForRecipe() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ recipeId, people }: { recipeId: string; people: number }) =>
      unwrap(await api.POST("/api/shop/sessions", { body: { recipe_ids: [recipeId], people } })),
    onSuccess: (basket) => {
      queryClient.setQueryData(BASKET_KEY, basket);
      queryClient.setQueryData(CART_KEY, []);
      queryClient.setQueryData(CART_REVIEW_KEY, EMPTY_REVIEW);
    },
  });
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
    onSuccess: () => invalidateAfterStockChange(queryClient),
  });
}

/** After a purchase is confirmed: empty the cart so the next visit builds a new basket. */
export function useFinishShopping() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.setQueryData(CART_KEY, []);
    queryClient.setQueryData(CART_REVIEW_KEY, EMPTY_REVIEW);
    queryClient.removeQueries({ queryKey: BASKET_KEY });
  };
}
