import type { QueryClient } from "@tanstack/react-query";

import { COOK_RECORD_KEY, SUGGESTION_KEY } from "./cook";

// Shop's cache keys live here so this module and shop.ts need not import each other.
export const BASKET_KEY = ["shop", "basket"];
export const CART_KEY = ["shop", "cart"];
export type CartReview = { hasMadeSelection: boolean; quantityReviewIds: string[] };
export const CART_REVIEW_KEY = ["shop", "cart-review"];
export const EMPTY_REVIEW: CartReview = { hasMadeSelection: false, quantityReviewIds: [] };

/**
 * Refresh availability on the next Cook visit, without replacing an active Quick Check session.
 * A basket nobody has ticked anything in yet is replanned on the next Buy visit, against the
 * changed kitchen; one being shopped from is kept, so the list never changes mid-shop.
 */
export function invalidateAfterStockChange(queryClient: QueryClient) {
  const shopping = (queryClient.getQueryData<string[]>(CART_KEY) ?? []).length > 0 ||
    queryClient.getQueryData<CartReview>(CART_REVIEW_KEY)?.hasMadeSelection === true;
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ["inventory"] }),
    queryClient.invalidateQueries({ queryKey: ["stock-events"] }),
    queryClient.invalidateQueries({ queryKey: SUGGESTION_KEY, refetchType: "none" }),
    shopping ? null : queryClient.invalidateQueries({ queryKey: BASKET_KEY, refetchType: "none" }),
  ]);
}

/** Preference edits explicitly start new plans, including any list already being shopped from. */
export async function resetAfterPreferencesChange(queryClient: QueryClient) {
  // Do not allow an older in-flight plan to replace the new preference-based result.
  await Promise.all([
    queryClient.cancelQueries({ queryKey: SUGGESTION_KEY }),
    queryClient.cancelQueries({ queryKey: BASKET_KEY }),
  ]);
  queryClient.setQueryData(CART_KEY, []);
  queryClient.setQueryData(CART_REVIEW_KEY, EMPTY_REVIEW);
  queryClient.removeQueries({ queryKey: COOK_RECORD_KEY });
  await Promise.all([
    queryClient.resetQueries({ queryKey: SUGGESTION_KEY }),
    queryClient.resetQueries({ queryKey: BASKET_KEY }),
  ]);
}
