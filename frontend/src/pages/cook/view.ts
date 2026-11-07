import type { Schemas } from "../../api/client";

type Suggestion = Schemas["Suggestion"];

export const COOK_TAG_LABELS: Record<Schemas["CookTag"], string> = {
  quicker: "Quicker",
  easier: "Easier",
  less_oil: "Less oil",
  more_protein: "More protein",
  more_vegetables: "More vegetables",
};

/** Only advertise server-checked actions; relative nudges may be repeated. */
export function availableNudges(suggestion: Suggestion): Schemas["CookTag"][] {
  return (suggestion.available_nudges ?? []).filter(
    (tag) => tag === "quicker" || tag === "easier" || !suggestion.applied_constraints.tags.includes(tag),
  );
}

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

/** A known counted shortage cannot be confirmed as a cooked meal. */
export function needsRestock(line: Schemas["SuggestionIngredient"]): boolean {
  return line.essential && (line.status === "missing" || (line.status === "low" && line.countable !== false));
}

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

export const FRESHNESS_REASONS: Record<Schemas["FreshnessReason"], string> = {
  past_use_by: "Past its use-by date",
  past_best_before: "Past its best-before date",
  past_estimate: "Past our estimated date",
  no_date: "No date recorded",
};

/** "+ Quicker · ≤ 20 min": how a free-text request was understood, in the user's terms. */
export function describeAdjust(adjust: Schemas["CookAdjust"]): string {
  const parts = (adjust.tags ?? []).map((tag) => `+ ${COOK_TAG_LABELS[tag]}`);
  if (adjust.max_minutes != null) parts.push(`≤ ${adjust.max_minutes} min`);
  if (adjust.people != null) parts.push(`${adjust.people} ${adjust.people === 1 ? "person" : "people"}`);
  return parts.length > 0 ? parts.join(" · ") : "nothing we can change";
}

/** Handed from the recipe screen to Cook through router state once a meal is confirmed. */
export type CookedState = { recordId: string; title: string; eventId: string; itemCount: number };

/** Minutes added when the user agrees to relax the time limit. */
export const RELAX_MINUTES = 15;
