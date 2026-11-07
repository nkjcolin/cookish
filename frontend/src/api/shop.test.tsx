import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { ConfirmPurchasePage } from "../pages/ConfirmPurchasePage";
import { BuyPage } from "../pages/BuyPage";
import { api, type Schemas } from "./client";
import { useAdjustBasket } from "./shop";
import { BASKET_KEY, CART_KEY } from "./stockCache";

function item(id: string, ingredient = "tomato", packs = 2): Schemas["BasketItem"] {
  return { id, ingredient_id: ingredient, name: ingredient, category: "produce", amount: `${packs} pieces`, countable: true,
    suggested_packs: packs, needs_check: false, purchase_unit: "piece", purchase_unit_size: 1, purchase_unit_measure: "pcs" };
}

function basket(id = "old", items = [item(`${id}-tomato`)]): Schemas["Basket"] {
  return { id, session_id: id, people: 2, meals: 3, status: "suggested", planned_meals: [], applied_tags: [],
    requested_recipe_ids: ["requested-dish"], items };
}

function setup(current = basket(), cart = ["old-tomato"]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  client.setQueryData(BASKET_KEY, current);
  client.setQueryData(CART_KEY, cart);
  const post = vi.spyOn(api, "POST");
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const hook = renderHook(() => useAdjustBasket(current.session_id), { wrapper });
  const confirm = () => render(
    <QueryClientProvider client={client}><MemoryRouter initialEntries={["/buy/confirm"]}><Routes>
      <Route path="/buy/confirm" element={<ConfirmPurchasePage />} />
      <Route path="/more/kitchen" element={<h1>Kitchen</h1>} />
    </Routes></MemoryRouter></QueryClientProvider>,
  );
  return { client, post, hook, confirm };
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("waits for an adjustment before allowing another change or purchase confirmation", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(BASKET_KEY, basket());
  client.setQueryData(CART_KEY, ["old-tomato"]);
  let finish!: (value: unknown) => void;
  const pending = new Promise((resolve) => { finish = resolve; });
  const post = vi.spyOn(api, "POST").mockImplementation(() => pending as never);
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/buy"]}><Routes>
    <Route path="/buy" element={<BuyPage />} />
    <Route path="/buy/confirm" element={<ConfirmPurchasePage />} />
  </Routes></MemoryRouter></QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "More vegetables" }));
  const updating = await screen.findByRole("button", { name: "Updating list…" });
  expect(updating).toBeDisabled();
  expect(screen.getByRole("button", { name: "Adjust basket" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Longer lasting" })).toBeDisabled();
  fireEvent.click(updating);
  expect(screen.queryByRole("heading", { name: "What’s in your bag?" })).not.toBeInTheDocument();
  await act(async () => { finish({ data: basket("new") }); await pending; });
  await waitFor(() => expect(screen.getByRole("button", { name: "I’m done shopping" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "I’m done shopping" }));
  expect(await screen.findByRole("checkbox", { name: /tomato/ })).toBeChecked();
  expect(post).toHaveBeenCalledTimes(1);
});

it("keeps checked ingredients under the replacement basket item IDs", async () => {
  const { client, post, hook, confirm } = setup();
  post.mockResolvedValue({ data: basket("new") } as never);
  await act(async () => { await hook.result.current.mutateAsync({ people: 3 }); });
  expect(client.getQueryData(CART_KEY)).toEqual(["new-tomato"]);
  confirm();
  expect(screen.getByRole("checkbox", { name: /tomato/ })).toBeChecked();
  expect(screen.getByRole("button", { name: "Add 1 item to kitchen" })).toBeEnabled();
});

it("requires the actual bought count when a checked ingredient's suggested amount changes", async () => {
  const { post, hook, confirm } = setup();
  post.mockResolvedValue({ data: basket("new", [item("new-tomato", "tomato", 5)]) } as never);
  await act(async () => { await hook.result.current.mutateAsync({ people: 5 }); });
  confirm();
  expect(screen.getByRole("checkbox", { name: /tomato/ })).toBeChecked();
  expect(screen.getByText("Your list changed. Enter the amounts you already put in your cart.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Add 1 item to kitchen" })).toBeDisabled();
  fireEvent.change(screen.getByRole("spinbutton", { name: "Actual piece count for tomato" }), { target: { value: "2" } });
  post.mockResolvedValue({ data: { event: { id: "purchase" }, items: [], basket_id: "new" } } as never);
  fireEvent.click(screen.getByRole("button", { name: "Add 1 item to kitchen" }));
  await screen.findByRole("heading", { name: "Kitchen" });
  expect(post).toHaveBeenCalledWith("/api/shop/baskets/{basket_id}/confirm", expect.objectContaining({
    body: { lines: [{ basket_item_id: "new-tomato", bought: true, packs: 2 }] },
  }));
});

it("does not assume every replacement item was bought when all checked ingredients disappear", async () => {
  const { client, post, hook, confirm } = setup();
  post.mockResolvedValue({ data: basket("new", [item("new-cucumber", "cucumber")]) } as never);
  await act(async () => { await hook.result.current.mutateAsync({ tags: ["longer_lasting"] }); });
  expect(client.getQueryData(CART_KEY)).toEqual([]);
  confirm();
  expect(screen.getByRole("checkbox", { name: /cucumber/ })).not.toBeChecked();
  expect(screen.getByRole("button", { name: "Add 0 items to kitchen" })).toBeDisabled();
});

it("keeps quantity review required through later adjustments", async () => {
  const { post, hook, confirm } = setup();
  post.mockResolvedValueOnce({ data: basket("new", [item("new-tomato", "tomato", 5)]) } as never)
    .mockResolvedValueOnce({ data: basket("again", [item("again-tomato", "tomato", 5)]) } as never);
  await act(async () => { await hook.result.current.mutateAsync({ people: 5 }); });
  await act(async () => { await hook.result.current.mutateAsync({ tags: ["more_vegetables"] }); });
  confirm();
  expect(screen.getByRole("spinbutton", { name: "Actual piece count for tomato" })).toHaveValue(null);
  expect(screen.getByRole("button", { name: "Add 1 item to kitchen" })).toBeDisabled();
});

it("preserves requested dishes and existing meal count when an expired session is restored", async () => {
  const current = { ...basket(), meals: 4, applied_tags: ["cover_more_meals", "more_vegetables"] as Schemas["ShopTag"][] };
  const { post, hook } = setup(current);
  post.mockResolvedValueOnce({ error: { error: { code: "NOT_FOUND", message: "Expired" } } } as never)
    .mockResolvedValueOnce({ data: basket("new") } as never)
    .mockResolvedValueOnce({ data: basket("new") } as never);
  await act(async () => { await hook.result.current.mutateAsync({ people: 3 }); });
  expect(post).toHaveBeenNthCalledWith(2, "/api/shop/sessions", { body: { people: 3, meals: 4, recipe_ids: ["requested-dish"] } });
  expect(post).toHaveBeenLastCalledWith("/api/shop/sessions/{session_id}/adjust", {
    params: { path: { session_id: "new" } },
    body: { tags: ["cover_more_meals", "more_vegetables"], replace_tags: true, meals: 4 },
  });
});

it("keeps keyword removal when restarting an expired session", async () => {
  const current = { ...basket(), applied_tags: ["more_vegetables"] as Schemas["ShopTag"][] };
  const { post, hook } = setup(current);
  post.mockResolvedValueOnce({ error: { error: { code: "NOT_FOUND", message: "Expired" } } } as never)
    .mockResolvedValueOnce({ data: basket("new") } as never);
  await act(async () => { await hook.result.current.mutateAsync({ tags: [], replace_tags: true }); });
  expect(post).toHaveBeenCalledTimes(2);
  expect(post).toHaveBeenLastCalledWith("/api/shop/sessions", { body: { people: 2, meals: 3, recipe_ids: ["requested-dish"] } });
});
