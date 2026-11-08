import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { kitchenBatch, kitchenInventory } from "../test-fixtures/kitchen";
import { KitchenPage } from "./KitchenPage";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

async function setup() {
  const rice = kitchenBatch({
    id: "rice-batch", ingredient_id: "rice", display_name: "Rice",
    countable: false, count: 1, unit: "kg", category: "grain", storage: "pantry",
  });
  const peas = kitchenBatch({
    id: "peas-batch", ingredient_id: "peas", display_name: "Frozen peas",
    countable: false, category: "produce", storage: "freezer",
  });
  vi.spyOn(api, "GET").mockResolvedValue({ data: kitchenInventory([kitchenBatch(), rice, peas]) } as never);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter><KitchenPage /></MemoryRouter>
    </QueryClientProvider>,
  );
  await screen.findByText("Rice");
}

describe("My Kitchen search", () => {
  it("opens a focused search box, matches partial names regardless of case, and clears", async () => {
    await setup();
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    const input = screen.getByRole("searchbox", { name: "Search kitchen" });
    expect(input).toHaveFocus();
    fireEvent.change(input, { target: { value: "ＲＩＣ" } });
    expect(screen.getByText("Rice")).toBeInTheDocument();
    expect(screen.queryByText("Eggs")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(screen.getByText("Eggs")).toBeInTheDocument();
    expect(input).toHaveFocus();
  });

  it("combines search with storage filters and shows an empty-search result", async () => {
    await setup();
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "rice" } });
    fireEvent.click(screen.getByRole("button", { name: "Freezer" }));
    expect(screen.getByRole("status")).toHaveTextContent("No matching ingredients");
    expect(screen.queryByText("Rice")).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "peas" } });
    expect(screen.getByText("Frozen peas")).toBeInTheDocument();
    expect(screen.queryByText("Rice")).not.toBeInTheDocument();
  });

  it("closes with Escape, clears the query and returns focus to Search", async () => {
    await setup();
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "rice" } });
    fireEvent.keyDown(screen.getByRole("searchbox"), { key: "Escape" });
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search" })).toHaveFocus();
    expect(screen.getByText("Eggs")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(screen.getByRole("searchbox")).toHaveValue("");
  });
});
