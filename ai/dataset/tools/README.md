# Synthetic receipt dataset tools

These tools belong to dataset creation. The evaluator and future test-set
manifests remain in `ai/eval/`. All required existing inputs are included in this
repository: the shared images, current scenario metadata, original scenario
blueprint in `specs/original_cases.json`, and backend recipe files.

| Tool | Purpose |
|---|---|
| `prepare.py` | Reconstruct the fixed ten-recipe baseline using seed 20261024; writes a new draft under `dataset/work/draft_20261024/` |
| `prepare_realistic.py` | Use the bundled original blueprint to prepare retail-pack scenarios, prices and image-generation prompts under `dataset/work/realistic_v2/` |
| `promote_realistic.py` | Validate a rendered revision and publish it to `dataset/receipt/generated/` and `dataset/recipe_receipts_20261024/` |
| `finish.py` | Validate published image/source hashes and rebuild the current gallery and manifests |
| `check_text.py` | Run macOS Vision OCR on the published images and update `ocr_review.json` |
| `inspect_text.swift` | OCR helper used by `check_text.py` |

## Preparation and rendering

From the repository root:

```bash
python3 ai/dataset/tools/prepare_realistic.py
```

The tool writes cases and prompts into `ai/dataset/work/realistic_v2/`. It refuses
to overwrite an existing revision. `prepare.py` is the separate baseline-recipe
selection step, retained for reproducibility; the retail revision already has
its required original blueprint bundled in `specs/`.

Python does not generate the receipt pixels. Render the prepared prompts with
an image-generation tool, saving the 30 PNGs at the paths specified by the
revision's `cases.json`. Record the actual calls in its `generation.json`, using
the current published `generation.json` as a format reference. Generation
records need matching case IDs, prompts and visual-review notes; do not reuse
historical generation records as evidence for newly generated images.

After rendering, publish the completed revision explicitly:

```bash
python3 ai/dataset/tools/promote_realistic.py
```

This replaces the shared current images and metadata and rebuilds the gallery.
It validates against the bundled blueprint rather than requiring ignored image
archives. `dataset/work/` is ignored by Git and Docker; the previous local
generation archive is retained there as `archive_20261024/`.

## Review the existing shared snapshot

```bash
python3 ai/dataset/tools/finish.py
# macOS with the Swift toolchain:
python3 ai/dataset/tools/check_text.py
```

`finish.py` checks existing assets and regenerates metadata; it makes no model
calls. The OCR helper uses the shared metadata/images directly, so no private
working-data copy is required after cloning. Its compiler cache is kept under
the ignored `ai/output/dataset/` folder.

These scripts reproduce the historical synthetic scenarios and do not create
human-reviewed extraction labels or choose the formal evaluation dataset.
