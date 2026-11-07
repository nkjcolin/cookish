import type { QueryClient } from "@tanstack/react-query";

import { SUGGESTION_KEY } from "./cook";

// Shop's cache keys live here so this module and shop.ts need not import each other.
export const BASKET_KEY = ["shop", "basket"];
export const CART_KEY = ["shop", "cart"];

/**
 * Refresh availability on the next Cook visit, without replacing an active Quick Check session.
 * A basket nobody has ticked anything in yet is replanned on the next Buy visit, against the
 * changed kitchen; one being shopped from is kept, so the list never changes mid-shop.
 */
export function invalidateAfterStockChange(queryClient: QueryClient) {
  const shopping = (queryClient.getQueryData<string[]>(CART_KEY) ?? []).length > 0;
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ["inventory"] }),
    queryClient.invalidateQueries({ queryKey: SUGGESTION_KEY, refetchType: "none" }),
    shopping ? null : queryClient.invalidateQueries({ queryKey: BASKET_KEY, refetchType: "none" }),
  ]);
}
