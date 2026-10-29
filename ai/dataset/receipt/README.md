# Curated receipt images

This directory contains four provided reference photos, 30 active synthetic JPEGs
in `generated/` and 30 archived synthetic PNGs in `old/`. The active set is the
2026-10-29 length batch: 10 short, 10 medium and 10 long. The older 2026-10-24
recipe/scenario set was moved to `old/` without changing its filenames or bytes.

`manifest.json` identifies every curated image, its SHA-256 hash and synthetic
status. Active synthetic entries also record their source batch, length, receipt
layout/date, food/non-food entry counts and target recipes. `old/manifest.json`
preserves the previous scenario/recipe index with paths relative to that archive.
The manifest is an image/provenance index, not a formal evaluation dataset;
`expected` remains null until labels are independently reviewed.

Every active medium receipt covers at least one target recipe; every long receipt
covers at least two distinct recipe families with sufficient combined as-sold
quantities. The archive covers ten recipes with three scenarios each: enough
ingredients, some missing, and fewer than half present. Both sets are generated
FairPrice-style development fixtures, not actual store transactions. Package
counts differ from package contents; the API returns total contents in the
original measurement unit. Numeric extraction and backend stock conversion still
require review. Historical package-design labels are not current API ground truth.

Use a curated image with the local HTTP API:

```bash
python3 ai/scripts/test_local.py --image ai/dataset/receipt/generated/short-01.jpg
```

For standalone school tests, edit the existing prompt-file block in `ai/laas.py`:

```python
image_path = script_dir / "dataset/receipt/generated/short-01.jpg"
prompt_name = "receipt.md"
print(ask_image_with_prompt_file(image_path, prompt_name))
```

Future generated batches and galleries belong in `../work/receipts/<batch-id>/`,
which is ignored by Git. Publish only chosen synthetic images in `generated/` and their selected
metadata in `manifest.json`; keep full run records in the working area. Current
local batch records/gallery are at `../work/receipts/eval_lengths_20261029/`, and
archived batch records are at `../work/receipts/20261024/`.

Selection for development use does not mark the failed frozen evaluation gate as
passed. Known salt/ginger quantity errors and long-image response times remain;
formal human-reviewed evaluation labels are still to be determined.
