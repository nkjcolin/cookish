import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { forgetImagePreview, rememberImagePreview } from "../lib/imagePreview";
import type { ReviewState } from "./add/draft";
import { ReviewDraftPage } from "./ReviewDraftPage";

const jobId = "33333333-3333-4333-8333-333333333333";
const originalURL = URL;
const item = { raw_text: "6 EGGS", display_name: "Eggs", count: 6, unit: "pcs", storage: "fridge" as const, confidence: 0.9 };

beforeEach(() => {
  vi.stubGlobal("URL", class extends originalURL {
    static createObjectURL = vi.fn(() => "blob:local-photo-preview");
    static revokeObjectURL = vi.fn();
  });
});
afterEach(() => {
  cleanup();
  forgetImagePreview(jobId);
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function setup(source: "photo" | "receipt", preview = true) {
  if (preview) rememberImagePreview(jobId, "image/jpeg", btoa("uploaded-image"));
  const state: ReviewState = { source, items: [item], imageJobId: jobId };
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[{ pathname: "/review", state }]}>
        <Routes>
          <Route path="/review" element={<ReviewDraftPage />} />
          <Route path="/more/kitchen" element={<p>Kitchen destination</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("uploaded photo review", () => {
  it.each(["photo", "receipt"] as const)("shows a %s thumbnail before enlarging and retains it after closing", (source) => {
    setup(source);
    const trigger = screen.getByRole("button", { name: source === "receipt" ? "Your receipt" : "Your photo" });
    const thumbnail = screen.getByRole("img", {
      name: source === "receipt" ? "Uploaded receipt thumbnail" : "Uploaded grocery photo thumbnail",
    });
    expect(thumbnail).toBeVisible();
    expect(thumbnail).toHaveAttribute("src", "blob:local-photo-preview");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    trigger.focus();
    fireEvent.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "Uploaded photo preview" });
    const image = screen.getByRole("img", { name: "Uploaded receipt or grocery photo" });
    expect(image).toHaveAttribute("src", "blob:local-photo-preview");
    fireEvent.click(image);
    expect(dialog).toBeInTheDocument();
    fireEvent.click(dialog);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(thumbnail).toBeVisible();
    expect(trigger).toHaveFocus();
  });

  it("supports Escape and keeps keyboard focus inside the preview", () => {
    setup("photo");
    fireEvent.click(screen.getByRole("button", { name: "Your photo" }));
    const close = screen.getByRole("button", { name: "Close photo preview" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(close).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(document.body.style.overflow).not.toBe("hidden");
  });

  it("keeps review usable when a reload has cleared the tab's preview", () => {
    setup("receipt", false);
    expect(screen.getByRole("button", { name: "Your receipt" })).toBeDisabled();
    expect(screen.queryByRole("img", { name: "Uploaded receipt thumbnail" })).not.toBeInTheDocument();
    expect(screen.getByText(/Preview unavailable/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add 1 item to kitchen" })).toBeEnabled();
  });

  it("releases the photo after successful confirmation and saves only the draft", async () => {
    const post = vi.spyOn(api, "POST").mockResolvedValue({ data: { items: [] } } as never);
    setup("photo");
    fireEvent.click(screen.getByRole("button", { name: "Add 1 item to kitchen" }));
    await screen.findByText("Kitchen destination");
    await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:local-photo-preview"));
    const options = (post.mock.calls as unknown as [string, { body: unknown }][])[0]![1];
    expect(options.body).toEqual({
      source: "photo",
      items: [{ display_name: "Eggs", count: 6, unit: "pcs", remaining_state: "enough", storage: "fridge" }],
    });
  });
});
