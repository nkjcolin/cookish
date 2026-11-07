import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import type { Schemas } from "../../api/client";
import { AdjustBasketSheet } from "./AdjustBasketSheet";

const basket: Schemas["Basket"] = {
  id: "basket", session_id: "session", people: 2, meals: 3, status: "suggested", planned_meals: [], items: [],
  applied_tags: ["more_vegetables"], requested_recipe_ids: [],
};

afterEach(cleanup);

it("sends an explicit empty replacement when the last keyword is removed", () => {
  const apply = vi.fn();
  render(<AdjustBasketSheet basket={basket} onApply={apply} onClose={() => {}} />);
  fireEvent.click(screen.getByRole("button", { name: "More vegetables" }));
  fireEvent.click(screen.getByRole("button", { name: "Update list" }));
  expect(apply).toHaveBeenCalledWith({ tags: [], replace_tags: true });
});

it("replaces a removed keyword with the selected one and submits portion edits", () => {
  const apply = vi.fn();
  render(<AdjustBasketSheet basket={basket} onApply={apply} onClose={() => {}} />);
  fireEvent.click(screen.getByRole("button", { name: "More vegetables" }));
  fireEvent.click(screen.getByRole("button", { name: "Longer lasting" }));
  fireEvent.click(screen.getByRole("button", { name: "One more" }));
  fireEvent.click(screen.getByRole("button", { name: "Update list" }));
  expect(apply).toHaveBeenCalledWith({ tags: ["longer_lasting"], replace_tags: true, people: 3 });
});

it("does not reapply keywords when only people change", () => {
  const apply = vi.fn();
  render(<AdjustBasketSheet basket={basket} onApply={apply} onClose={() => {}} />);
  fireEvent.click(screen.getByRole("button", { name: "One more" }));
  fireEvent.click(screen.getByRole("button", { name: "Update list" }));
  expect(apply).toHaveBeenCalledWith({ people: 3 });
});
