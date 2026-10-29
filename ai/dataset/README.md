# Shared AI development dataset

`receipt/` is the curated receipt set intended for GitHub. The active synthetic
set under `receipt/generated/` contains 10 short, 10 medium and 10 long receipts
from the 2026-10-29 batch. The previous 30 recipe/scenario images are preserved
under `receipt/old/`; the four original reference photos stay at the `receipt/`
root. New generation runs belong in the ignored `work/` directory.

| Path | Contents | Git |
|---|---|---|
| `receipt/` | Four reference photos, documentation and the curated index | Included |
| `receipt/generated/` | Thirty active synthetic JPEGs: 10 short, 10 medium, 10 long | Included |
| `receipt/manifest.json` | Active filenames, hashes, synthetic status, lengths and recipe provenance | Included |
| `receipt/old/` | Thirty previous recipe/scenario PNGs and their archive manifest | Included |
| `grocery/` | Two grocery photos | Included |
| `audio/` | Short synthetic ingredient-list recording | Included |
| `catalogs/` | Frozen one-time retail catalogue covering all recipe ingredient names | Included |
| `configs/` | Reserved for reusable generation configuration | Included |
| `tools/` | Existing preparation, batch validation and OCR helpers | Included |
| `work/receipts/<batch-id>/` | Generated images, prompts, price snapshots, cases, galleries and review records | Ignored |

The active shared set contains 36 images and one synthetic audio clip, plus 30
archived receipt images. Selection for publication is not a human-reviewed
extraction label. Both receipt indexes keep `expected: null`; they are not formal
evaluation manifests.

## Current and archived generation batches

The active selection is copied byte-for-byte from
`work/receipts/eval_lengths_20261029/images/`. Medium receipts cover at least one
target recipe; long receipts cover at least two distinct target recipe families
with sufficient combined as-sold quantities. The set includes non-food purchases
to exercise exclusion. Source plans, galleries, prompts and detailed evaluation
records remain in the ignored working/output directories.

These images were selected by the user for the curated development dataset.
The original frozen benchmark failed its gate; the subsequent non-food regression
does not establish formal acceptance. Nothing was promoted to
`dataset/generated/eval/`. Salt/ginger quantity errors and production latency
remain evaluation issues.

The former `recipe_receipts_20261024/` records now live locally under
`work/receipts/20261024/`, alongside a batch-local copy of each generated image
in `images/`. Its gallery is `work/receipts/20261024/index.html`. The historical
scenario blueprint is retained there as `original_cases.json`. These local
records are not included in a fresh clone. Original generation paths inside
provenance records describe the historical run and remain unchanged.

The former selected PNGs were moved unchanged into `receipt/old/`; filenames and
hashes are preserved in its own manifest. Those ten recipes have `enough`,
`missing_some` and `below_half` variants; the last means fewer than half the
required ingredients. Both batches resemble the FairPrice reference and are
synthetic fixtures, not actual transactions.
See [receipt/README.md](receipt/README.md) for interpretation and testing notes.

## Generation and selection boundary

Preparation, finalisation, OCR reports and galleries must write under `work/`.
Finalising a batch does not automatically copy its images into `receipt/generated/`.
Copy only selected generated images into `receipt/generated/` and record their provenance in its
manifest. Per-run files remain ignored even when adding the whole `ai/` folder
to Git; the curated image directory and manifest are the published selection.

The [retail catalogue](catalogs/README.md) now contains 41 FairPrice products for
all 42 ingredient names in the 48 backend recipes, with tap water excluded from
purchases. Prices and pack quantities were collected once on 2026-10-28, with
source URLs, stock-name provenance and quantity caveats. Validate it offline with
`python3 ai/dataset/tools/validate_ingredient_catalog.py` from the repository root.

Configuration-driven generation/selection automation remains a separate future
task. Existing historical generation helpers have not been switched to the new
catalogue. No new receipt images or model calls were made for catalogue creation.

## Test the curated inputs

From the repository root:

```bash
cd ai
uv sync --frozen
uv run python laas.py
```

Configure your ignored `ai/.env` and choose the test block in `laas.py` first.
Its receipt-batch helpers process the reference photos at the `receipt/` root.
The dedicated `ai/scripts/run_generated_receipts.py` runner processes the selected
images in `receipt/generated/`, now the selected 30-image length batch. Its resume
guard rejects outputs from a different input batch; preserve earlier results and
use a fresh output directory before starting a new batch run.

The evaluation smoke manifest still references the unchanged FairPrice photo.
See [the evaluation guide](../eval/README.md). Local evaluation inputs, extraction
outputs and working archives remain ignored and excluded from Docker images.
