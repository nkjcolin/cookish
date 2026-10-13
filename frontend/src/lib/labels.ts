import type { Schemas } from "../api/client";

// Display names for the contract's closed vocabularies (backend app/schemas/common.py).
export const ALLERGEN_LABELS: Record<Schemas["Allergen"], string> = {
  peanut: "Peanut allergy",
  tree_nut: "Tree nut allergy",
  milk: "Milk allergy",
  egg: "Egg allergy",
  fish: "Fish allergy",
  shellfish: "Shellfish allergy",
  soy: "Soy allergy",
  gluten: "Gluten-free",
  sesame: "Sesame allergy",
};

export const DIET_LABELS: Record<Schemas["Diet"], string> = {
  vegetarian: "Vegetarian",
  vegan: "Vegan",
  pescatarian: "Pescatarian",
  halal: "Halal",
  no_pork: "No pork",
  no_beef: "No beef",
};

export const EQUIPMENT_LABELS: Record<Schemas["Equipment"], string> = {
  stove: "Stove",
  oven: "Oven",
  microwave: "Microwave",
  rice_cooker: "Rice cooker",
  air_fryer: "Air fryer",
  steamer: "Steamer",
  blender: "Blender",
};

export const CUISINE_LABELS: Record<Schemas["Cuisine"], string> = {
  chinese: "Chinese",
  malay: "Malay",
  indian: "Indian",
  western: "Western",
  japanese: "Japanese",
  korean: "Korean",
  thai: "Thai",
  other: "Other",
};

/** "Stove, rice cooker +2": the first few names, lower-cased after the first, then a count. */
export function summarise(names: string[], shown = 2): string {
  if (names.length === 0) return "None";
  const head = names.slice(0, shown).map((name, index) => (index === 0 ? name : name.toLowerCase()));
  const rest = names.length - head.length;
  return rest > 0 ? `${head.join(", ")} +${rest}` : head.join(", ");
}

export function toggled<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}
