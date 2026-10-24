# Shared AI development dataset

This folder is intended for GitHub. It contains copies of the existing receipt
and grocery images from `ai/eval/data/`; those local working copies are retained.
The images and dataset metadata are excluded from Docker builds.

| Path | Contents |
|---|---|
| `receipt/` | Four reference receipt images |
| `receipt/generated/` | Thirty synthetic receipts: ten recipes with three ingredient-coverage scenarios each |
| `grocery/` | Two grocery photos |
| `recipe_receipts_20261024/` | Current scenario specifications, recipe snapshots, price references, generation records and gallery |
| `tools/` | Synthetic-data preparation, publication and OCR helpers with their original scenario blueprint |

The shared set contains 36 images. Generated receipts reuse the FairPrice
reference's visual style; they are synthetic development fixtures, not actual
store transactions. Existing reference images are included as provided for local
testing. No school-model extraction outputs or API credentials are stored here.

Open [the scenario gallery](recipe_receipts_20261024/index.html) to compare recipes
and receipts. Its images link to `receipt/generated/`, avoiding duplicate image
archives. Generation records retain historical paths for provenance.

## Use the images

From the repository root:

```bash
cd ai
uv sync --frozen
uv run python laas.py
```

Configure the required school settings in your ignored `ai/.env` first; see the
comments in `laas.py`. Its selected grocery image and receipt-batch defaults now
use this shared dataset. Edit `main()` to choose a different image or prompt.

The smoke manifest at `ai/eval/manifest.smoke.json` also references these images.
See [the evaluation guide](../eval/README.md) for running the API-based evaluator.

## Label status

These inputs are not the completed formal human-labelled evaluation set.
The synthetic scenario `manifest.json` deliberately has `expected: null`.
`intended_labels.json` preserves historical retail-package design counts; those
are not ground truth for the current total-quantity API. Review readable amounts
and original units against each image before preparing evaluation labels.
Generated receipts do not replace the required real-image/voice evaluation.

Dataset preparation and OCR helpers are published in [dataset/tools](tools/README.md).
Local working data, generation archives and run outputs remain ignored under
`ai/eval/data/`, `ai/eval/results/`, `ai/output/` and `ai/dataset/work/`.
