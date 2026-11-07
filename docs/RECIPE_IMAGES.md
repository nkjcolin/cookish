# Recipe images

The 48 seeded recipes use 45 AI-generated serving illustrations. Each recipe has
the same image on its Cook suggestion, recipe preview/detail, and Buy meal card.
These are illustrations based on the recipe ingredients and preparation, not
photographs of meals cooked or tested by the project team.

Images were generated on 7 November 2026 using OpenAI's built-in `image_gen` tool,
then resized to 960 pixels wide and saved as WebP at quality 82. They are hosted
with the frontend, so displaying a recipe needs no external image service or
runtime image generation. The files are in `frontend/public/recipes/`.

`frontend/src/data/recipeImages.ts` maps stable recipe UUIDs to images and alt
text. Only the three less-oil variants share their parent's image: cabbage and
tofu stir-fry, ginger chicken rice, and tomato and egg stir-fry. Variants that
change the protein, vegetables, or preparation have separate illustrations.

The [prompt manifest](recipe-image-prompts.json) records the prompt, output file,
dimensions, size and recipe IDs for every asset. When adding or changing a recipe,
check its picture against the ingredients and steps, add or update the UUID map,
and run `pnpm test` from `frontend`. The catalogue test checks that every seed UUID
has a map entry and that every referenced WebP exists. Unknown recipes and failed
image loads show a neutral fallback instead of a different dish.
