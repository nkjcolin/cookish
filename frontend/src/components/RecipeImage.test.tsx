import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RecipeImage } from "./RecipeImage";

const TOMATO_EGG = "645a8d38-bfae-47f2-b00e-3ca6828a964e";
const TOFU = "2173bce1-8bbd-40ee-be78-e80627d8ba07";

afterEach(cleanup);

describe("RecipeImage", () => {
  it("switches images by recipe identity, even when the displayed title is unchanged", () => {
    const view = render(<RecipeImage recipeId={TOMATO_EGG} title="Tonight's meal" />);
    const first = screen.getByRole("img");
    expect(first).toHaveAttribute("src", "/recipes/tomato-egg-stir-fry.webp");

    view.rerender(<RecipeImage recipeId={TOFU} title="Tonight's meal" />);
    const next = screen.getByRole("img");
    expect(next).toHaveAttribute("src", "/recipes/cabbage-tofu-stir-fry.webp");
    expect(next).not.toBe(first);
  });

  it("uses an accessible neutral fallback for unknown recipes", () => {
    render(<RecipeImage recipeId="not-in-catalogue" title="New dish" />);
    expect(screen.getByRole("img", { name: "No image available for New dish" })).toBeInTheDocument();
    expect(screen.getByText("Recipe image unavailable")).toBeInTheDocument();
    expect(document.querySelector("img[src^='/recipes/']")).toBeNull();
  });

  it("handles a failed image without keeping that failure on the next recipe", () => {
    const view = render(<RecipeImage recipeId={TOMATO_EGG} title="Tomato and egg" />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByRole("img", { name: "No image available for Tomato and egg" })).toBeInTheDocument();

    view.rerender(<RecipeImage recipeId={TOFU} title="Cabbage and tofu" />);
    expect(screen.getByRole("img")).toHaveAttribute("src", "/recipes/cabbage-tofu-stir-fry.webp");
  });
});
