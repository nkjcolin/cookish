import type { Schemas } from "../../api/client";

type BasketItem = Schemas["BasketItem"];
type Category = Schemas["IngredientCategory"];

export const SHOP_TAG_LABELS: Record<Schemas["ShopTag"], string> = {
  more_vegetables: "More vegetables",
  longer_lasting: "Longer lasting",
  cover_more_meals: "Cover more meals",
};

// Aisles in the order most shops are walked.
const AISLES: { title: string; categories: Category[] }[] = [
  { title: "Produce", categories: ["produce"] },
  { title: "Meat & fish", categories: ["meat", "seafood"] },
  { title: "Chilled & frozen", categories: ["dairy", "egg", "frozen"] },
  { title: "Dry & pantry", categories: ["grain", "pantry", "condiment", "other"] },
];

export type Aisle = { title: string; items: BasketItem[] };

export function groupByAisle(items: BasketItem[]): Aisle[] {
  return AISLES.map(({ title, categories }) => ({
    title,
    items: items.filter((item) => categories.includes(item.category)),
  })).filter((aisle) => aisle.items.length > 0);
}
