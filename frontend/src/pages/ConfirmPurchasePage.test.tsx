import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type Schemas } from "../api/client";
import { ConfirmPurchasePage } from "./ConfirmPurchasePage";

function item(id: string, name: string, suggestedPacks: number | null): Schemas["BasketItem"] {
  return {
    id,
    ingredient_id: `ingredient-${id}`,
    name,
    category: "produce",
    amount: suggestedPacks === null ? "Buy as needed" : `${suggestedPacks} packs`,
    suggested_packs: suggestedPacks,
    needs_check: false,
    countable: suggestedPacks !== null,
    purchase_unit: "pack",
    purchase_unit_size: 300,
    purchase_unit_measure: "g",
  };
}

function setup(items: Schemas["BasketItem"][]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const basket: Schemas["Basket"] = {
    id: "basket",
    session_id: "session",
    people: 2,
    meals: 1,
    status: "suggested",
    items,
    planned_meals: [],
    applied_tags: [],
  };
  client.setQueryData(["shop", "basket"], basket);
  const post = vi.spyOn(api, "POST").mockResolvedValue({
    data: { basket_id: "basket", event: { id: "purchase-event" }, items: [] },
  } as never);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/buy/confirm"]}>
        <Routes>
          <Route path="/buy/confirm" element={<ConfirmPurchasePage />} />
          <Route path="/more/kitchen" element={<h1>Kitchen</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return post;
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("purchase confirmation amounts", () => {
  it("submits the displayed suggested count when the user accepts it unchanged", async () => {
    const post = setup([item("tofu", "Firm tofu", 2)]);
    expect(screen.getByText("× 2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add 1 item to kitchen" }));
    expect(await screen.findByRole("heading", { name: "Kitchen" })).toBeInTheDocument();
    expect(post).toHaveBeenCalledWith("/api/shop/baskets/{basket_id}/confirm", {
      params: { path: { basket_id: "basket" }, header: { "Idempotency-Key": expect.any(String) } },
      body: { lines: [{ basket_item_id: "tofu", bought: true, packs: 2 }] },
    });
  });

  it("submits an edited count and respects the API limit of fifty units", async () => {
    const post = setup([item("tofu", "Firm tofu", 49)]);
    fireEvent.click(screen.getByRole("button", { name: "One pack more of Firm tofu" }));
    expect(screen.getByText("× 50")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "One pack more of Firm tofu" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Add 1 item to kitchen" }));
    await screen.findByRole("heading", { name: "Kitchen" });
    expect(post).toHaveBeenCalledWith("/api/shop/baskets/{basket_id}/confirm", expect.objectContaining({ body: { lines: [{ basket_item_id: "tofu", bought: true, packs: 50 }] } }));
  });

  it("omits counts for unticked and state-tracked items", async () => {
    const post = setup([item("tofu", "Firm tofu", 2), item("cabbage", "Cabbage", null)]);
    fireEvent.click(screen.getByRole("button", { name: "One pack more of Firm tofu" }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Firm tofu/ }));
    expect(screen.queryByRole("button", { name: "One pack more of Cabbage" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Add 1 item to kitchen" }));
    await screen.findByRole("heading", { name: "Kitchen" });
    expect(post).toHaveBeenCalledWith("/api/shop/baskets/{basket_id}/confirm", expect.objectContaining({ body: { lines: [
      { basket_item_id: "tofu", bought: false },
      { basket_item_id: "cabbage", bought: true },
    ] } }));
  });

  it("asks for an actual pack count when recipe weights cannot determine a counted purchase", async () => {
    const post = setup([{
      ...item("carrot", "Carrots", null),
      countable: true,
      needs_check: true,
      amount: "300 g; check quantity and purchase units",
      purchase_unit_size: 4,
      purchase_unit_measure: "pcs",
    }]);
    const quantity = screen.getByRole("spinbutton", { name: "Actual pack count for Carrots" });
    expect(quantity).toHaveValue(null);
    expect(screen.getByText("Per pack: 4 pieces")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add 1 item to kitchen" })).toBeDisabled();
    expect(post).not.toHaveBeenCalled();

    fireEvent.change(quantity, { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Add 1 item to kitchen" }));
    await screen.findByRole("heading", { name: "Kitchen" });
    expect(post).toHaveBeenCalledWith("/api/shop/baskets/{basket_id}/confirm", expect.objectContaining({ body: { lines: [{ basket_item_id: "carrot", bought: true, packs: 2 }] } }));
  });

  it("labels purchases sold individually as pieces and blocks invalid counts", async () => {
    const post = setup([{
      ...item("cucumber", "Cucumber", null),
      countable: true,
      needs_check: true,
      amount: "200 g; check quantity and purchase units",
      purchase_unit: "piece",
      purchase_unit_size: 1,
      purchase_unit_measure: "pcs",
    }]);
    const quantity = screen.getByRole("spinbutton", { name: "Actual piece count for Cucumber" });
    expect(screen.getByText("How many pieces did you buy?")).toBeInTheDocument();
    for (const value of ["0", "-1", "1.5", "51", ""]) {
      fireEvent.change(quantity, { target: { value } });
      expect(screen.getByRole("button", { name: "Add 1 item to kitchen" })).toBeDisabled();
    }
    expect(post).not.toHaveBeenCalled();
    fireEvent.change(quantity, { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Add 1 item to kitchen" }));
    await screen.findByRole("heading", { name: "Kitchen" });
    expect(post).toHaveBeenCalledWith("/api/shop/baskets/{basket_id}/confirm", expect.objectContaining({ body: { lines: [{ basket_item_id: "cucumber", bought: true, packs: 3 }] } }));
  });

  it("does not require a quantity for a counted item the user did not buy", async () => {
    const post = setup([
      { ...item("carrot", "Carrots", null), countable: true, needs_check: true },
      item("cabbage", "Cabbage", null),
    ]);
    fireEvent.click(screen.getByRole("checkbox", { name: /Carrots/ }));
    fireEvent.click(screen.getByRole("button", { name: "Add 1 item to kitchen" }));
    await screen.findByRole("heading", { name: "Kitchen" });
    expect(post).toHaveBeenCalledWith("/api/shop/baskets/{basket_id}/confirm", expect.objectContaining({ body: { lines: [
      { basket_item_id: "carrot", bought: false },
      { basket_item_id: "cabbage", bought: true },
    ] } }));
  });

  it("does not invent a pack size when the purchase definition is missing", () => {
    const post = setup([{
      ...item("carrot", "Carrots", null),
      countable: true,
      needs_check: true,
      purchase_unit: null,
      purchase_unit_size: null,
      purchase_unit_measure: null,
    }]);
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "add it separately" })).toHaveAttribute("href", "/more/add");
    expect(screen.getByRole("button", { name: "Add 1 item to kitchen" })).toBeDisabled();
    expect(post).not.toHaveBeenCalled();
  });

  it("asks for a refresh when a browser-cached basket lacks the new metadata", () => {
    const legacy = { ...item("carrot", "Carrots", null), countable: undefined } as unknown as Schemas["BasketItem"];
    const post = setup([legacy]);
    expect(screen.getByText("Refresh your shopping list before confirming this item.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add 1 item to kitchen" })).toBeDisabled();
    expect(post).not.toHaveBeenCalled();
  });
});
