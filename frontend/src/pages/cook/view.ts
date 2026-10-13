import type { Schemas } from "../../api/client";

type Suggestion = Schemas["Suggestion"];

export const COOK_TAG_LABELS: Record<Schemas["CookTag"], string> = {
  quicker: "Quicker",
  easier: "Easier",
  less_oil: "Less oil",
  more_protein: "More protein",
  more_vegetables: "More vegetables",
};

export const TASTE_TAG_LABELS: Record<Schemas["TasteTag"], string> = {
  light: "Light",
  rich: "Rich",
  spicy: "Spicy",
  soupy: "Soupy",
  low_oil: "Low oil",
  high_protein: "High protein",
  vegetable_rich: "Lots of vegetables",
};

const DIFFICULTY_LABELS = ["Easy", "Medium", "Involved"];

export function difficultyLabel(difficulty: number): string {
  return DIFFICULTY_LABELS[Math.min(Math.max(difficulty, 1), 3) - 1]!;
}

export function mealName(now: Date): "breakfast" | "lunch" | "dinner" {
  const hour = now.getHours();
  if (hour < 10) return "breakfast";
  if (hour < 15) return "lunch";
  return "dinner";
}

export type IngredientLine = { tone: "ok" | "ask"; text: string };

/**
 * The short stock summary under a suggestion. Staples are assumed and not listed;
 * anything uncertain is said plainly so the user is not surprised at the stove.
 */
export function ingredientLines(suggestion: Suggestion): IngredientLine[] {
  const names = (status: Schemas["IngredientStatus"]) =>
    suggestion.ingredients.filter((i) => i.status === status).map((i) => i.name);
  const lines: IngredientLine[] = [];
  const add = (tone: IngredientLine["tone"], label: string, list: string[], suffix = "") => {
    if (list.length > 0) lines.push({ tone, text: `${label}: ${list.join(", ")}${suffix}` });
  };
  add("ok", "Have", names("have"));
  add("ask", "Running low", names("low"));
  add("ask", "Need to buy", names("missing"));
  add("ask", "Not sure", names("unknown"), " — we’ll ask");
  add("ask", "Check first", names("check"));
  return lines;
}
