# Evaluation without fabricated ground truth

This folder contains the AI evaluator and example manifests. The formal test
dataset and human-reviewed labels have not yet been selected. The project
specification names the repository-root `eval/image_set/` for the final handoff;
current work stays inside `ai/`. No evaluator or test data enter the Lambda image.

The local layout is:

```text
ai/eval/
├── runner.py
├── manifest.example.json
├── manifest.smoke.json
├── manifest.template.json
├── data/                         # Local inputs, ignored by Git and Docker
│   ├── receipt/                  # Includes the generated/ receipt images
│   └── grocery/
└── results/                      # Local reports, ignored by Git and Docker
```

Image paths in manifests are relative to their manifest. The shared
repository-root `eval/` folder is separate from this AI-local folder.

Shared development inputs and synthetic-scenario metadata are published in
[dataset/](../dataset/README.md). The smoke/template manifests point there to
exercise the tooling after a fresh clone; those examples do not select the
formal test dataset. Local working data and run reports remain ignored.
Synthetic-data preparation and OCR scripts live separately in
[dataset/tools](../dataset/tools/README.md), alongside their required blueprint.

The provided example is **synthetic fake-provider plumbing**, not receipt accuracy.
The template has `expected: null` deliberately: unlabelled does not mean no food.
Do not generate ground truth from the same model you are evaluating.

## Run the plumbing example

From the repository root, build the development image and start a separate fake
service on port 8002 (do not accidentally run this example against the school API):

```bash
docker build -t cookish-ai:local ./ai
docker run --rm --name cookish-ai-evaluation -p 127.0.0.1:8002:8000 \
  -e AI_PROVIDER=fake cookish-ai:local
```

In another terminal:

```bash
python3 ai/scripts/evaluate.py ai/eval/manifest.example.json \
  --run --url http://127.0.0.1:8002 \
  --out ai/eval/results/plumbing.json
```

Choose a new output filename on each run; existing measurements are not overwritten.
`--run` explicitly permits HTTP/model requests and may consume school quota when
pointed at a school-backed service. Without it, scoring saved predictions is offline:

```bash
python3 ai/scripts/evaluate.py ai/eval/manifest.example.json \
  --predictions ai/eval/results/plumbing.json \
  --out ai/eval/results/rescored.json
```

## Prepare real labels

Copy `manifest.template.json` to a private/local manifest and replace the paths and
transcripts. Image paths are relative to that manifest. Supply human-reviewed
labels for at least 30 receipts, 20 grocery photos and 20 actual voice transcripts.
Include a long receipt and varied quantity layouts. The initial small experiment
can use 10 receipts and 5 photos, but cannot satisfy formal dataset coverage.

Each expected food is an object with `display_name`; optional `aliases` explicitly
lists equivalent names for scoring. Optional `count` and `unit` enable quantity
checks. Annotate expected API behavior, including receipt defaults of 1/pcs when
absent, without inventing a printed quantity. Unknown text/photo quantities stay
null. Use `expected: []` only when a human verified there are no food items.

`non_food_names` lists human-identified non-food names to measure known inclusions;
other false positives are not automatically classified as non-food. Optional
`correction_seconds` is a real, manually observed review time, never inferred.
Interpretation cases use `expected_adjust` instead of `expected`.

Run the same labelled manifest against each candidate model configuration, using
unique report filenames. Configure models on the server through `SOCLAAS_MODEL`
or per-task overrides and recreate its container between candidates. The browser
never chooses the model. The runner reports the actual provider/model headers.
Use repeatable `--case CASE_ID` options to rerun only selected examples without
spending quota on the full set again.

```bash
python3 ai/scripts/evaluate.py ai/eval/manifest.local.json \
  --run --url http://127.0.0.1:8001 \
  --out ai/eval/results/candidate-a.json --require-formal
```

## What the report means

- Food precision/recall use maximum one-to-one name/explicit-alias matching; duplicate
  predictions cannot match the same ground-truth item twice. Failed requests add
  false negatives for their labelled food items, rather than being silently dropped.
- Count/unit errors are measured on matched items only where those labels exist.
  See comparison counts as well as errors. No package-to-inventory conversion is done.
- Latency includes HTTP waiting. Both all-request and successful-request p95 are
  reported; failures are also reported separately. A tiny smoke run is not a p95
  benchmark or proof of the approximately 10-second project target.
- Confidence bins and Brier score measure identification calibration on labelled
  predictions. They do not automatically rewrite the model's confidence values.
- Usage is aggregated from API headers across attempts; unavailable usage remains
  unknown. Known token totals are partial if any cases lack usage. Cost remains
  null until school pricing or quota terms are supplied; do not present zero cost.
- Interpretation accuracy is separate from food identification metrics.
- `formal_dataset_complete` requires the full labelled set, non-synthetic input and
  the real school provider. It does not by itself mean the precision/latency targets
  passed. `--require-formal` fails on incomplete coverage; request failures also
  produce a nonzero exit code.

Outputs omit uploaded images, input transcripts and raw OCR text, but still contain
food labels and predictions. Keep real customer data private. `results/`, `data/`,
`private/` and local manifests are ignored and excluded from Docker contexts.

Formal dataset collection/evaluation was deferred by the user on 2026-10-23.
Current acceptance gap: no complete human-labelled dataset, model-quality
comparison, calibrated-confidence acceptance or school pricing/quota terms have
been provided. The runner is implemented; formal model acceptance is not complete.

## Ideas for when you resume

Start with a small pilot you can label yourself: five real local receipts, five
photos of groceries you arrange on a table, and ten spoken shopping lists. Cover
quantity before/after a description, quantity on another line, missing quantities,
compact units, non-food purchases, glare/blur and partly hidden groceries. Keep
retakes of the same receipt or grocery arrangement in the same tuning/test split
so repeated content does not inflate results. Remove personal/payment identifiers
before school uploads without obscuring the item/quantity evidence.

Label food names, accepted aliases, purchased count and unit by hand, including
the agreed defaults. Keep some examples untouched while tuning prompts. For voice,
record the intended list and actual browser transcript separately; this lets you
distinguish transcription failures from the AI parser's errors. Do not use model
predictions as their own ground truth.

Two supplementary public sources, not downloaded here:

- [CORD, from its creators](https://github.com/clovaai/cord): receipt images and
  semantic item/quantity labels (`menu.nm`, `menu.cnt`). Its Indonesian shop/restaurant
  domain differs from local grocery receipts, so adapt and review labels rather
  than treating it as a ready-made Cookish benchmark.
- [Grocery Store Dataset, from its creators](https://github.com/marcusklasson/GroceryStoreDataset):
  smartphone grocery images with food-class labels. Useful for recognition variety,
  but class labels do not supply the multi-item purchased quantities required by
  this app; add your own count/unit labels where needed.

Review the dataset licences and attribution instructions before reuse. Own local
examples are still needed for the app's receipt layouts, food names and voice flow.
