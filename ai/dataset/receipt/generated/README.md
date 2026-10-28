# Selected generated receipt images

All 30 existing synthetic receipt PNGs are retained in this directory with their
original filenames and bytes. The four provided reference photos remain one
directory above, at the `receipt/` root.

The set covers ten recipes with three scenarios each: enough ingredients, some
missing, and fewer than half present. These are generated FairPrice-style
development fixtures, not actual store transactions or human-labelled evaluation
data. Package counts and package contents are separate; measured extraction
quantities and backend inventory conversion still require review.

The published [curated manifest](../manifest.json) records selected-image hashes,
synthetic status and recipe/scenario provenance. Detailed historical batch
records and the gallery remain local under ignored
`../../work/receipts/20261024/`, with their own `images/` archive.

Future generation runs stay under `dataset/work/receipts/<batch-id>/`. Copy only
chosen receipt images into this directory and record them in the curated manifest.
See [receipt testing instructions](../README.md).
