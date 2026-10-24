# Artifact verification

Current revision: `realistic_v2`. The former fictional-shop images and records
are retained in `revisions/original_v1/`.

- 30 distinct PNG files: 10 randomly selected recipes, with all three scenarios
  for each. All images are below 3 MiB and within the API dimension limits.
- Recipe source hashes still match the backend files read during preparation.
- Every present ingredient's available package contents are at least the original two-serving requirement.
  Enough cases include all non-water ingredients. Missing-some cases retain at
  least half the essential ingredients. Below-half cases retain strictly fewer
  than half the essential and all listed non-water ingredients.
- The assistant visually inspected the reference store heading, retail product
  descriptions, package counts, prices, totals, cash and change. Prices and pack
  references are recorded in `PRICES.md` and `price_catalog.json`.
  These are assistant checks of synthetic fixtures, not human-labelled real data.
- Independent local macOS Vision OCR checked all 30 files. Its raw results are in
  `ocr_review.json`. It flagged one line which is visibly present:
  - `R02-ENOUGH`: `1X$0.45/Unit` appears immediately below `FP FINE SALT 500G`.
  This is an OCR miss rather than a reason to change the intended purchase label.
  OCR substring checks alone do not establish correct item-to-quantity association.
- All 30 gallery image references and local links resolve. Both manifest files
  pass the existing evaluation runner's manifest validation. The default manifest
  remains unlabelled (`expected: null`); intended labels are separate for review.
  Intended extraction labels now use purchased package counts. Available contents
  are separate fields in the scenario specifications; no app stock conversion
  was introduced. All 30 files in `ai/eval/data/receipt/generated/` match the gallery copies
  byte for byte. Line-price multiplication, totals and cash/change arithmetic
  passed deterministic checks, and scenario ingredient-presence labels are unchanged.
- No school-model recognition run or end-to-end inventory/recommendation test was
  performed. No AWS resources, backend files, original receipts or app prompts
  were changed. The built-in image tool generated the images; actual prompts and
  reference paths are recorded in `generation.json` and `prompts.md`.

The store title/address are taken from the user's photo. The till, time and cash
details are fabricated for image realism; branch-specific tax and cash-rounding
behavior are not validated. Online prices and marketplace availability are not
guaranteed at the named physical branch. Lemon price and cabbage pack weight are
explicit fixture assumptions.
