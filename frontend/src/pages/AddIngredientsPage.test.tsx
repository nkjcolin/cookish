import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type Schemas } from "../api/client";
import * as image from "../lib/image";
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
  sessionStorage.clear();
  vi.restoreAllMocks();
});

function ReviewDestination() {
  return <pre data-testid="review">{JSON.stringify(useLocation().state)}</pre>;
}

describe("AddIngredientsPage image jobs", () => {
  it("sends groceries to a job and opens review only after processing completes", async () => {
    const id = "d041df63-1dc7-4f26-a88b-9b25757b0037";
    const queued = { job_id: id, kind: "photo", status: "queued", poll_after_seconds: 2 };
    vi.spyOn(image, "compressImage").mockResolvedValue("compressed");
    const post = vi.spyOn(api, "POST").mockResolvedValue({ data: queued } as never);
    let finish: (value: unknown) => void;
    vi.spyOn(api, "GET").mockImplementation((() => new Promise((resolve) => { finish = resolve; })) as never);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={["/more/add"]}>
          <Routes>
            <Route path="/more/add" element={<AddIngredientsPage />} />
            <Route path="/more/add/review" element={<ReviewDestination />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByLabelText("Photo of groceries or fridge", { selector: "input" }), {
      target: { files: [new File(["image"], "groceries.jpg", { type: "image/jpeg" })] },
    });
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post.mock.calls[0]?.[0]).toBe("/ai/image-jobs");
    expect(screen.queryByTestId("review")).not.toBeInTheDocument();
    await waitFor(() => expect(finish!).toBeTypeOf("function"));
    finish!({ data: { ...queued, status: "completed", result: { items: [onion] } } });
    const review = await screen.findByTestId("review");
    expect(JSON.parse(review.textContent!)).toEqual({ items: [onion], source: "photo" });
    const calls = post.mock.calls as unknown as [string, unknown][];
    expect(calls.some(([path]) => path === "/api/inventory/items")).toBe(false);
    expect(sessionStorage.getItem("cookish.pending-image-job")).toBeNull();
  });

  it("shows image compression errors without an unhandled rejection", async () => {
    vi.spyOn(image, "compressImage").mockRejectedValue(new Error("Invalid image"));
    const post = vi.spyOn(api, "POST");
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter><AddIngredientsPage /></MemoryRouter>
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByLabelText("Receipt photo"), {
      target: { files: [new File(["bad"], "bad.jpg", { type: "image/jpeg" })] },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid image");
    expect(post).not.toHaveBeenCalled();
  });
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
