import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type Schemas } from "../api/client";
import { COOK_RECORD_KEY, SUGGESTION_KEY } from "../api/cook";
import { CookPage } from "./CookPage";
import { RecipePage } from "./RecipePage";

const recipe: Schemas["Recipe"] = {
  id: "719b4fca-2889-4389-a4f7-8605dee34c48",
  title: "Chickpea salad",
  cuisine: "other",
  difficulty: 1,
  total_minutes: 15,
  active_minutes: 15,
  servings: 2,
  starred: false,
  taste_tags: ["light"],
  base_recipe_id: null,
  variant_label: null,
  equipment: [],
  ingredients: [
    { ingredient_id: "chickpea", name: "Chickpeas", quantity: 200, unit: "g", coarse_amount: null, prep_note: null, essential: true },
  ],
  steps: ["Mix the chickpeas with the vegetables."],
};

function suggestion(status: Schemas["IngredientStatus"]): Schemas["Suggestion"] {
  return {
    session_id: "session",
    recipe,
    people: 4,
    ingredients: [{ ingredient_id: "chickpea", name: "Chickpeas", amount: "400 g", essential: true, status }],
    applied_constraints: { max_minutes: 30, max_difficulty: null, tags: [] },
    has_previous: false,
    needs_check: [],
    freshness_check: [],
  };
}

const selected: Schemas["CookRecord"] = {
  id: "record",
  session_id: "session",
  recipe,
  people: 4,
  proposed_consumption: [],
  status: "selected",
  rating: null,
};

function setup(current: Schemas["Suggestion"], selectResult: unknown = { data: selected }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(SUGGESTION_KEY, current);
  // A previous selection must never turn a preview into confirmation for the old dish.
  client.setQueryData(COOK_RECORD_KEY, { ...selected, id: "older-record", recipe: { ...recipe, id: "older", title: "Old dish" } });
  const get = vi.spyOn(api, "GET").mockResolvedValue({ data: recipe } as never);
  const post = vi.spyOn(api, "POST").mockResolvedValue(selectResult as never);
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/cook"]}>
        <Routes>
          <Route path="/cook" element={<CookPage />} />
          <Route path="/cook/preview" element={<RecipePage preview />} />
          <Route path="/cook/recipe" element={<RecipePage />} />
          <Route path="/buy" element={<h1>Shopping list</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { client, get, post };
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("recipe browsing and cooking", () => {
  it("lets an empty kitchen read the recipe and go shopping without selecting or confirming a meal", async () => {
    const { client, get, post } = setup(suggestion("missing"));
    const suggestedImage = screen.getByRole("img", { name: /illustrative serving of cucumber/i }).getAttribute("src");

    expect(screen.queryByRole("button", { name: "Cook this" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "View recipe" }));

    expect(await screen.findByText(recipe.steps[0]!)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: recipe.title })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /illustrative serving of cucumber/i })).toHaveAttribute("src", suggestedImage);
    expect(screen.getByText("400 g")).toBeInTheDocument();
    expect(screen.getByText("Serves 4")).toBeInTheDocument();
    expect(screen.getByText("Need to buy")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "I cooked this" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Update kitchen" })).toHaveAttribute("href", "/more/kitchen");
    expect(get).toHaveBeenCalledWith("/api/recipes/{recipe_id}", { params: { path: { recipe_id: recipe.id } } });
    expect(post).not.toHaveBeenCalled();
    expect(client.getQueryData<Schemas["CookRecord"]>(COOK_RECORD_KEY)?.id).toBe("older-record");

    fireEvent.click(screen.getByRole("button", { name: "Go to Buy" }));
    expect(await screen.findByRole("heading", { name: "Shopping list" })).toBeInTheDocument();
  });

  it("also allows stocked recipes to be previewed without creating a cook record", async () => {
    const { post } = setup(suggestion("have"));
    fireEvent.click(screen.getByRole("button", { name: "View recipe" }));
    expect(await screen.findByText(recipe.steps[0]!)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "I cooked this" })).not.toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Back to suggestion" }));
    expect(await screen.findByRole("button", { name: "Cook this" })).toBeInTheDocument();
  });

  it("still selects a stocked recipe before offering the cooking confirmation", async () => {
    const { post } = setup(suggestion("have"));
    const suggestedImage = screen.getByRole("img", { name: /illustrative serving of cucumber/i }).getAttribute("src");
    fireEvent.click(screen.getByRole("button", { name: "Cook this" }));
    const confirm = await screen.findByRole("button", { name: "I cooked this" });
    expect(screen.getByRole("img", { name: /illustrative serving of cucumber/i })).toHaveAttribute("src", suggestedImage);
    fireEvent.click(confirm);
    expect(await screen.findByRole("heading", { name: "Nice! What’s left?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Update kitchen" })).toBeInTheDocument();
    expect(post).toHaveBeenCalledExactlyOnceWith("/api/cook/sessions/{session_id}/select", {
      params: { path: { session_id: "session" } },
    });
  });

  it("keeps the user on the suggestion if stock has changed and selection is rejected", async () => {
    const { post } = setup(suggestion("have"), {
      error: { error: { code: "CONFLICT", message: "Check or replenish essential ingredients before cooking", details: {} } },
    });
    fireEvent.click(screen.getByRole("button", { name: "Cook this" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Check or replenish"));
    expect(screen.getByRole("button", { name: "Cook this" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "I cooked this" })).not.toBeInTheDocument();
    expect(post).toHaveBeenCalledTimes(1);
  });
});
