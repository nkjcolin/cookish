import type { QueryClient } from "@tanstack/react-query";

import { SUGGESTION_KEY } from "./cook";

/** Refresh availability on the next Cook visit, without replacing an active Quick Check session. */
export function invalidateAfterStockChange(queryClient: QueryClient) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ["inventory"] }),
    queryClient.invalidateQueries({ queryKey: SUGGESTION_KEY, refetchType: "none" }),
  ]);
}
