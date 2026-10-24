# Synthetic recipe receipt scenarios

This is the published snapshot. The gallery links to `../receipt/generated/`
instead of storing duplicate images here. The original working directory and
revision archives remain local under `ai/dataset/work/archive_20261024/`.
Generation records retain their historical paths for provenance.

This is a synthetic development set generated with the built-in image generation
tool, using the reference images now in `ai/dataset/receipt/`. It is not the formal
human-labelled real-receipt evaluation set. No school API calls or AWS deployments
are needed to create or browse it.

The current `realistic_v2` revision uses the `FAIRPRICE XTRA / JEM HYPERMART`
heading and address from `ai/dataset/receipt/fairprice-receipt.jpeg`, compact thermal
printing, paper creases and ordinary checkout formatting. All generated images
are shared in `ai/dataset/receipt/generated/`; this gallery links to those files.
These are generated fixtures, not actual transactions at that store. Their
synthetic status is kept in these files rather than a large banner on each image.

Ten recipes were sampled without replacement from the 48 YAML files in
`backend/seed/recipes/`, using seed `20261024`. Selection is by file, so related
recipe variants may both occur. Every selected recipe uses its original two servings.
`cases.json` records source paths and SHA-256 hashes, recipe requirements, purchase
amounts, missing ingredients, coverage, intended receipt text and generation prompts.
The backend files are read only.

## The three scenarios

1. `enough`: every listed non-water ingredient is present, including optional
   ingredients, with at least the quantity required by the recipe.
2. `missing_some`: one or two essential ingredients are absent; at least half of
   the essential ingredients remain. Present ingredients have sufficient amounts.
3. `below_half`: strictly fewer than half the essential ingredients are present.
   It is also fewer than half of all listed non-water ingredients. This means
   ingredient coverage, **not** insufficient quantities of otherwise present foods.

Assume an empty starting inventory except for tap water. Salt, oil, sauces and
spices must appear on a receipt to be available. No substitutions or serving
rescaling are assumed. Water is excluded from coverage counts even where the
recipe gives it a measured amount.

The revised receipts use ordinary retail pack descriptions and separate purchased
package counts, such as `2X$2.55/Unit`. A `280G` suffix describes one package's
contents; it is not the purchased count. In `cases.json`, `purchase_count` and
`purchase_unit` describe that receipt-level count. `count` and `unit` describe
the total available contents used for recipe comparison. For example, two 280 g
broccoli packs provide 560 g, and two 210 g cooked-rice trays provide 420 g.

Cooked rice and dry rice remain different ingredients. Chickpeas have 400 g net
per can and a conservative 240 g drained edible amount, so two cans satisfy the
recipe's 300 g drained requirement. One chosen cabbage head is labelled 1 kg;
the price source lists one head without a fixed weight. Contents-to-inventory
conversion is recorded for these fixtures. The current AI returns total amounts
in the original printed unit, without kg/L conversion. The externally sourced 240 g drained chickpea
amount is not printed on these receipts: the model must not infer it from the
400 g net label. Extracted net contents are not the recipe's drained amount.
Recipe scenario design amounts and image-supported extraction labels therefore
differ here; backend preparation-basis mapping still needs review.

`PRICES.md` and `price_catalog.json` record the price and pack references checked
on 2026-10-24. Prices for 27 products are based on FairPrice online listings;
the loose lemon price is an explicitly marked estimate. Online listings, their
promotions and marketplace products do not guarantee the named branch's current
prices or stock. Prices remain image context, not new fields in AI responses.

## Browse and test

Open `index.html` to browse the generated images and recipe comparisons. The
`../receipt/generated/` directory contains one PNG per case. `prompts.md` records the prompt set;
`generation.json` records the actual generation inputs and output provenance.
The receipts are generated from the FairPrice photo's visual style; the Giant
photo was also inspected during reference selection. The store title and public
address are reused at the user's request. The earlier fictional-shop version and
its metadata are retained in the local working folder's `revisions/original_v1/`.

For one image, edit the existing prompt-file test block in `ai/laas.py`:

```python
image_path = script_dir / "dataset/receipt/generated/01_steamed-egg__enough.png"
prompt_name = "receipt.md"
print(ask_image_with_prompt_file(image_path, prompt_name))
```

Then, from the repository root:

```bash
conda run -n cookish python ai/laas.py
```

The school call consumes quota. Changing the image path is all that is needed to
try another scenario. The generic helper prints model text; it does not enforce
the application's schema or cleanup. Use `scripts/test_local.py` against the
running app when testing the complete API pipeline instead.

The intended purchases are specifications from recipe files, independent of the
model being tested. Generated image text must be checked against those
specifications before treating it as an extraction label. These images are
synthetic and have not been human-labelled. `manifest.json` deliberately leaves
`expected` null; `intended_labels.json` contains the intended purchase labels for
review. These v2 design labels retain the historical retail package counts, not
their contents; they are not suitable for scoring the new total-amount contract.
Human review must establish image-supported totals before any formal evaluation.
They do not replace the deferred formal evaluation.

`ocr_review.json` records an independent, local macOS Vision OCR check. OCR may
miss a visibly printed line, so flags also need visual inspection. Assistant
visual checks are recorded separately in `generation.json` and are not human
ground truth. The OCR helpers now live in [dataset/tools](../tools/README.md)
and can repeat the check on local working inputs on macOS without school API calls.

Coverage labels describe the intended available ingredients. They do not promise
specific backend recommendation rankings, stock conversions or inventory writes.
Test those separately after reviewing and confirming the extracted drafts.

This shared snapshot is intended for Git and excluded from Docker builds.
Local working data under `ai/eval/data/` and run outputs remain ignored by Git.
The generated receipts are replaced when revising the set. Original reference
receipts, school credentials, saved extraction outputs and app prompts are untouched.
See `REVIEW.md` for completed artifact checks and the local OCR flags inspected.
