import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { BASKET_KEY, CART_KEY, invalidateAfterStockChange } from "./stockCache";

function clientWith(cart: string[]) {
  const client = new QueryClient();
  client.setQueryData(BASKET_KEY, { id: "basket" });
  client.setQueryData(CART_KEY, cart);
  return client;
}

describe("invalidateAfterStockChange", () => {
  it("replans an untouched basket on the next Buy visit", async () => {
    const client = clientWith([]);
    await invalidateAfterStockChange(client);
    expect(client.getQueryState(BASKET_KEY)?.isInvalidated).toBe(true);
  });

  it("keeps a basket that is being shopped from", async () => {
    const client = clientWith(["item"]);
    await invalidateAfterStockChange(client);
    expect(client.getQueryState(BASKET_KEY)?.isInvalidated).toBe(false);
  });
});
