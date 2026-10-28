# Curated receipt images

This directory contains four provided reference photos and 30 selected synthetic
receipt images. All existing generated receipts were retained during the folder
reorganisation. Reference photos stay at this directory's root and synthetic PNGs
stay in `generated/`, preserving their existing filenames, paths and bytes.

`manifest.json` identifies every curated image, its SHA-256 hash and synthetic
status. Synthetic entries also record their source batch, scenario and recipe.
The manifest is an image/provenance index, not a formal evaluation dataset;
`expected` remains null until labels are independently reviewed.

The synthetic set covers ten recipes with three scenarios each: enough
ingredients, some missing, and fewer than half present. These are generated
FairPrice-style development fixtures, not actual store transactions. Package
counts differ from package contents; the API returns total contents in the
original measurement unit. Numeric extraction and backend stock conversion still
require review. Historical package-design labels are not current API ground truth.

Use a curated image with the local HTTP API:

```bash
python3 ai/scripts/test_local.py --image ai/dataset/receipt/generated/01_steamed-egg__enough.png
```

For standalone school tests, edit the existing prompt-file block in `ai/laas.py`:

```python
image_path = script_dir / "dataset/receipt/generated/01_steamed-egg__enough.png"
prompt_name = "receipt.md"
print(ask_image_with_prompt_file(image_path, prompt_name))
```

Future generated batches and galleries belong in `../work/receipts/<batch-id>/`,
which is ignored by Git. Publish only chosen synthetic images in `generated/` and their selected
metadata in `manifest.json`; keep full run records in the working area. Current
local batch records and gallery are at `../work/receipts/20261024/`.
