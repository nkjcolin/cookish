import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { BASKET_KEY, CART_KEY, CART_REVIEW_KEY, invalidateAfterStockChange } from "./stockCache";

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

  it("keeps an explicitly reviewed empty cart instead of silently replacing its basket", async () => {
    const client = clientWith([]);
    client.setQueryData(CART_REVIEW_KEY, { hasMadeSelection: true, quantityReviewIds: [] });
    await invalidateAfterStockChange(client);
    expect(client.getQueryState(BASKET_KEY)?.isInvalidated).toBe(false);
  });

  it("refreshes history along with inventory after a correction, removal or undo", async () => {
    const client = clientWith([]);
    client.setQueryData(["inventory"], { groups: [] });
    client.setQueryData(["stock-events"], { events: [] });
    await invalidateAfterStockChange(client);
    expect(client.getQueryState(["inventory"])?.isInvalidated).toBe(true);
    expect(client.getQueryState(["stock-events"])?.isInvalidated).toBe(true);
  });
});
