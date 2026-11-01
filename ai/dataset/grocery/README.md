# Curated grocery dataset

The actual curated set contains **10 selected synthetic JPEGs** in `generated/`
and the two unchanged provided reference photos at this directory's root.
The previous three clean soba preview images were removed at the user's request;
they are not part of this dataset or its manifest.

Open [the image gallery](index.html) to compare all ten photographs. Full file
hashes, selected status, scene contexts, observed food candidates, visibility
notes and recipe references are in [manifest.json](manifest.json).

## Selected images

The mix is three meal-sized scenes, three one-to-two-day hauls and four
weekly/restock scenes. These categories describe the intended shopping context;
they do not claim nutritional completeness or a guaranteed number of days of food.

| Image | Shopping context | Overlap | Scene |
|---|---|---|---|
| [01_meal_egg_rice](generated/01_meal_egg_rice.jpg) | A meal | light overlap | Egg-and-rice dinner ingredients |
| [02_meal_soba_overlap](generated/02_meal_soba_overlap.jpg) | A meal | moderate overlap | Soba ingredients with a partial vegetable view |
| [03_meal_family_four](generated/03_meal_family_four.jpg) | A meal | moderate overlap | Larger tofu-and-broccoli family dinner |
| [04_two_days_fish_greens](generated/04_two_days_fish_greens.jpg) | 1–2 days | moderate overlap | Fish, eggs, noodles and greens top-up |
| [05_two_days_vegetarian](generated/05_two_days_vegetarian.jpg) | 1–2 days | strong overlap | Vegetarian groceries with stacked packages |
| [06_two_days_breakfast_dinner](generated/06_two_days_breakfast_dinner.jpg) | 1–2 days | moderate overlap | Breakfast and dinner supplies with hidden eggs |
| [07_weekly_family](generated/07_weekly_family.jpg) | Weekly / restock | strong overlap | Larger family haul with mixed food and household goods |
| [08_weekly_vegetarian_bulk](generated/08_weekly_vegetarian_bulk.jpg) | Weekly / restock | strong overlap | Vegetarian pantry and produce restock |
| [09_weekly_mixed_chilled](generated/09_weekly_mixed_chilled.jpg) | Weekly / restock | strong overlap | Mixed chilled and frozen groceries in bags |
| [10_weekly_small_household](generated/10_weekly_small_household.jpg) | Weekly / restock | moderate overlap | Small-household restock with different package sizes |

## What makes these useful for extraction testing

- Bags, foliage and stacked packages partially hide food and labels. A food must
  have exposed visual evidence; the generation plan is not permission to invent
  wholly hidden food or its quantity.
- Loose produce has no guessed gram weights. Unreadable pack contents, obscured
  egg counts and ambiguous printed units remain unknown until reviewed.
- The breakfast/dinner scene has a readable `10 EGGS` carton label even though
  fewer eggs are visible. A clear total label can establish the purchased count.
- The family restock includes different package counts, two `1 L` milk cartons,
  two labelled `700 g` chicken packs and a household kitchen-roll pack to exclude.
- The small-household scene contains whole and low-fat milk cartons of different
  sizes. The smaller volume text is ambiguous after generation/export; do not
  force the planned `500 ml`. Tofu, lentil, noodle and egg package sizes vary
  across scenes.
- The vegetarian restock's rendered coconut-milk labels include `100 ml` and
  `200 ml`, rather than uniformly following the generation prompt. Its can cluster
  has uncertain package totals. Canned net contents never imply drained mass.
- Food subtypes follow the rendered packaging: some scenes contain silken tofu;
  the family dinner has two corrected firm-tofu trays. Unlabelled white fish
  cannot be asserted to be cod just because the prompt requested cod.

The first meal scene supports the standard two portions of
[steamed egg with rice](../../../backend/seed/recipes/steamed-egg.yaml) using
visible counts/labels. The family dinner supports four portions of
[tofu and broccoli stir-fry](../../../backend/seed/recipes/tofu-broccoli-stir-fry.yaml):
900 g firm tofu across two 450 g trays, 600 g pretrimmed broccoli florets,
100 g garlic, 100 g ginger, 660 ml soy sauce, 500 ml canola oil and 1 kg rice.
These exceed the scaled four-serving requirements; kitchen tap water is assumed
available. Other scenes do not acquire portion guarantees from their appearance.
The soba scene shows the ingredient types but its loose-produce masses and
sesame-oil volume cannot establish complete quantity coverage.

## Provenance and evaluation status

Generated on 2026-11-01 with the built-in image generation tool. One targeted
image edit corrected a silken/firm-tofu mismatch in the family dinner. Commercial
packaging and labels are synthetic and are not verified authentic SKU designs,
current retailer availability or actual purchases.

The selected JPEGs use quality 85 with original pixels retained, a longest edge
at most 1500 pixels and less than 3 MiB each. Total size is about **5.7 MiB**,
roughly **78% smaller** than the generated PNG originals. PNGs remain only in the
image tool's default local output; no PNG originals are added to this dataset.

The assistant visually reviewed the rendered images and used local macOS Vision
OCR to check printed evidence. Those notes are review aids, not independent
human-labelled ground truth. `expected: null` remains until extraction labels
are reviewed. All ten images are selected and included in this actual dataset. A subsequent
live school-model comparison is recorded below; independent human labels remain pending.

Full prompts, export records, visual review notes, OCR and preview-removal records
stay under ignored `ai/dataset/work/groceries/realistic_20261101/`. Selected image
files, the manifest, this README and the gallery are eligible for Git. No code
or recipe files outside `ai/` were changed.

To test an image against your configured local service:

```bash
python3 ai/scripts/test_local.py \
  --image ai/dataset/grocery/generated/07_weekly_family.jpg \
  --kind photo --timeout 100
```

Use `kind: "photo"`. A school-backed service consumes school quota; local timing
and extraction quality must be measured separately from image generation.

## School-model comparison (2026-11-01)

All ten images were tested through `POST /ai/parse-image` with `kind: "photo"`
and the unchanged grocery prompt, using `qwen3-vl:32b`. Initial availability was
9/10; one upstream HTTP 503 was preserved and a single separate recovery call
succeeded. Total model POSTs: 11.

Against the pre-call assistant image observations, all **101/101 broad food-category
instances** matched when similar names and grouped duplicates were accepted. This
is not exact SKU/subtype accuracy. On **40 predeclared readable quantity totals,
36 were correct (90%)**. Confirmed errors: eggs 4 → 5, milk 2 L → 1 L, chicken
1,400 g → 700 g, and tempeh 340 g → 170 g. Later visual checks additionally found
garlic 4 → 5 and carrots 2 → 3, outside that fixed denominator. Unknown occluded
amounts remain unscored; the 90% figure is not accuracy over every returned count.

Raw replies, private model factors, usage/cost headers and the
[side-by-side comparison](../../output/eval/grocery_realistic_20261101/report.html)
are local under ignored `ai/output/eval/grocery_realistic_20261101/`. Successful
call durations were 7.81–29.57 seconds, median 13.33 seconds, using a 110-second
provider timeout and 120-second local request budget. One call exceeded the
normal 27-second Lambda request budget. No inference/prompt/image tuning was
performed during testing and these results do not establish formal acceptance.

### Per-package experiment

An opt-in application mode (`SOCLAAS_PHOTO_QUANTITY_MODE=instances`) was tested
on these same JPEGs. The initial live trial produced 7/10 usable API responses;
strict quantity validation rejected three otherwise useful replies. The
corrected parser accepts purchase units such as `loaf`, keeps uncertain quantities
null, and preserves the printed measurement scale. Replaying **only each first
saved reply** through the corrected API route produced 40/40 correct fixed
quantity totals, versus 36/40 before. This is an offline replay of real replies,
not a fresh live run or formal acceptance.

The extra garlic check improved from 5 to 4. Carrots in image 09 still returned
3 instead of 2, and image 07 newly included a kitchen towel. All 101 expected
broad food categories were present, plus that one non-food extra. The actual
live trial needed 14 provider POSTs including repairs and had higher latency
and token usage. The trial originally kept `factors` as the default. Subsequently,
on 2026-11-01, the user selected `instances` as the application default; the saved
trial and replay results remain unchanged. The previous method can still be
selected explicitly with `SOCLAAS_PHOTO_QUANTITY_MODE=factors`.

Accuracy summary (updated 2026-11-02): the corrected replay passed 40/40 primary
quantity checks and 1/2 supplemental checks, giving **41/42 (97.6%)** across the
checked quantities. Broad food-category recall was 101/101 (100%) and precision
was 101/102 (99.02%) including the kitchen towel. This does not score every
returned count or establish exact product-subtype accuracy. The later fresh live
check of image 01 scored 3/4 quantities (75%), returning 5 eggs against the
comparison label of 4, in 12.518 seconds with one model call. One image cannot
establish overall accuracy; the earlier replay and its labels remain unchanged.

The [paired report](../../output/eval/grocery_instances_20261101/final_report.html),
original live responses, frozen scoring targets and corrected replay results
are in ignored `ai/output/eval/grocery_instances_20261101/`. No image or expected
label was altered to improve the score; `expected: null` remains appropriate
until independent human labels are supplied.
