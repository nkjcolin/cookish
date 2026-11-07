import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type Schemas } from "../api/client";
import { AddIngredientsPage } from "./AddIngredientsPage";

const onion: Schemas["DraftItem"] = {
  raw_text: "2 onions",
  display_name: "Onion",
  count: 2,
  unit: "pcs",
  storage: "pantry",
  confidence: 0.95,
};

function setup() {
  const post = vi.spyOn(api, "POST").mockResolvedValue({ data: { items: [onion] } } as never);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <AddIngredientsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  const parseCalls = () =>
    (post.mock.calls as unknown as [string, unknown][]).filter(([path]) => path === "/ai/parse-items");
  return { post, parseCalls };
}

const input = () => screen.getByLabelText("Or just type it");
const checkButton = () => screen.getByRole("button", { name: "Check" });

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AddIngredientsPage typed items", () => {
  it("reads the text only when Check is tapped, then offers to add the result", async () => {
    const { parseCalls } = setup();

    fireEvent.change(input(), { target: { value: "2 onions" } });
    await new Promise((resolve) => setTimeout(resolve, 700));
    expect(parseCalls()).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /^Add/ })).not.toBeInTheDocument();

    fireEvent.click(checkButton());
    await screen.findByRole("button", { name: "Add 1 item" });
    expect(parseCalls()).toHaveLength(1);
    expect(parseCalls()[0]![1]).toEqual({ body: { text: "2 onions", source: "typed" } });
    expect(screen.getByText("Onion · 2")).toBeInTheDocument();
    // Nothing new to read until the text changes.
    expect(checkButton()).toBeDisabled();
  });

  it("drops a result once the text it came from is edited", async () => {
    const { parseCalls } = setup();
    fireEvent.change(input(), { target: { value: "2 onions" } });
    fireEvent.click(checkButton());
    await screen.findByRole("button", { name: "Add 1 item" });

    fireEvent.change(input(), { target: { value: "2 onions, garlic" } });
    expect(screen.queryByRole("button", { name: /^Add/ })).not.toBeInTheDocument();
    await waitFor(() => expect(checkButton()).toBeEnabled());
    expect(parseCalls()).toHaveLength(1);
  });

  it("cannot check an empty box", () => {
    setup();
    expect(checkButton()).toBeDisabled();
  });
});
