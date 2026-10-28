# Dataset preparation and local batch tools

Curated inputs are published in `../receipt/`. All generated batches, galleries,
price snapshots, OCR reports and historical scenario blueprints belong in the
ignored `../work/receipts/` area. Evaluation tooling remains in `ai/eval/`.

| Tool | Current purpose |
|---|---|
| `prepare.py` | Historical ten-recipe baseline; outputs `work/receipts/draft_20261024/` |
| `prepare_realistic.py` | Historical retail revision; outputs `work/receipts/realistic_v2/` and needs the local original blueprint |
| `promote_realistic.py` | Validate/finalise that revision into an ignored batch; never automatically publish all images |
| `finish.py` | Validate a local batch and rebuild its gallery and manifests |
| `check_text.py` | Run macOS Vision OCR and save the report in a local batch |
| `inspect_text.swift` | macOS OCR helper |
| `validate_ingredient_catalog.py` | Offline validation of retail facts, ingredient coverage and unchanged recipe hashes |

The receipt-generation helpers remain historical. Their fixed scenario/product
logic is not yet wired to the new shared catalogue. The separate catalogue
validator reads `../catalogs/ingridients.json` without scraping or writing files:

```bash
python3 ai/dataset/tools/validate_ingredient_catalog.py
```

Run from the repository root; the full checkout supplies the source recipe files
for hash verification. Catalogue details and quantity caveats are documented in
[the catalogue guide](../catalogs/README.md).

## Preserved local inputs

The original batch records, rendered images and blueprint are retained under
`work/receipts/20261024/`. They are not available after a fresh clone. The curated
images and their provenance index remain available without those local records.

To validate/rebuild the existing local gallery, from the repository root:

```bash
python3 ai/dataset/tools/finish.py
python3 ai/dataset/tools/check_text.py
```

Both tools accept `--batch ai/dataset/work/receipts/<batch-id>`. OCR requires the
macOS Swift toolchain. Its compiler cache remains under ignored `ai/output/`.

## Historical revision workflow

```bash
python3 ai/dataset/tools/prepare_realistic.py
```

This needs `work/receipts/20261024/original_cases.json` and refuses to reset an
existing prepared revision. Render its prompts with an image-generation tool,
saving images and actual generation records in that revision. Python does not
render receipt pixels.

Finalise a rendered revision into another ignored local batch:

```bash
python3 ai/dataset/tools/promote_realistic.py \
  --revision ai/dataset/work/receipts/realistic_v2 \
  --output ai/dataset/work/receipts/realistic_v2_final
```

An existing destination is rejected. Finalisation copies images and batch
records only into `work/`, then builds that local gallery. Select images for
`receipt/generated/` explicitly; full batch records stay local. Selection automation
and configuration-driven generation using the shared catalogue remain future work.

The tools do not create human-reviewed extraction labels or choose the formal
evaluation dataset. They make no school model or AWS calls.
