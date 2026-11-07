import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { getRecipeImage, RECIPE_IMAGES } from "./recipeImages";

describe("recipe image catalogue", () => {
  it("covers every seeded recipe UUID exactly once", () => {
    const directory = resolve(process.cwd(), "../backend/seed/recipes");
    const ids = readdirSync(directory).filter((name) => name.endsWith(".yaml")).map((name) => {
      const yaml = readFileSync(resolve(directory, name), "utf8");
      const id = /^id: ([0-9a-f-]+)\r?$/m.exec(yaml)?.[1];
      expect(id, name).toBeDefined();
      return id;
    });
    expect(Object.keys(RECIPE_IMAGES).sort()).toEqual(ids.sort());
  });

  it("ships an actual WebP asset for every mapped serving illustration", () => {
    const sources = new Set(Object.values(RECIPE_IMAGES).map((image) => image.src));
    for (const source of sources) {
      const file = readFileSync(resolve(process.cwd(), "public", source.slice(1)));
      expect(file.toString("ascii", 0, 4), source).toBe("RIFF");
      expect(file.toString("ascii", 8, 12), source).toBe("WEBP");
    }
  });

  it("shares only the less-oil dishes while keeping changed proteins and mixed rice distinct", () => {
    expect(getRecipeImage("45045a12-f142-4125-b594-34f486c75032")?.src)
      .toBe(getRecipeImage("645a8d38-bfae-47f2-b00e-3ca6828a964e")?.src);
    expect(getRecipeImage("79093e58-6ac3-46ab-adee-c948efc5b880")?.src)
      .toBe(getRecipeImage("2173bce1-8bbd-40ee-be78-e80627d8ba07")?.src);
    const imageCounts = Object.values(RECIPE_IMAGES).reduce<Record<string, number>>((counts, image) => {
      counts[image.src] = (counts[image.src] ?? 0) + 1;
      return counts;
    }, {});
    expect(Object.entries(imageCounts).filter(([, count]) => count > 1).map(([source]) => source).sort()).toEqual([
      "/recipes/cabbage-tofu-stir-fry.webp",
      "/recipes/ginger-chicken-rice.webp",
      "/recipes/tomato-egg-stir-fry.webp",
    ]);
    expect(getRecipeImage("23c3cd8d-ad33-4891-b2ec-6c10a93a43cb")?.src)
      .not.toBe(getRecipeImage("82837c0b-d649-4fe6-aa5b-196c64459b28")?.src);
    expect(getRecipeImage("not-in-catalogue")).toBeUndefined();
    expect(getRecipeImage("toString")).toBeUndefined();
  });
});
