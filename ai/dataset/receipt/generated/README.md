# Selected generated receipt images

This directory contains 30 selected synthetic JPEGs from the 2026-10-29 batch:
`short-01.jpg` to `short-10.jpg`, `medium-01.jpg` to `medium-10.jpg` and
`long-01.jpg` to `long-10.jpg`. They are byte-for-byte copies of the tested JPEGs
from the ignored working batch, with a longest edge of at most 1500 pixels.
The previous 30 PNGs are preserved in `../old/`. The four provided reference
photos remain one directory above, at the `receipt/` root.

Every medium receipt covers at least one target recipe; every long receipt
covers at least two distinct recipe families with sufficient combined as-sold
quantities. Non-food purchases are included to test exclusion. These are FairPrice-style
development fixtures, not actual store transactions or human-labelled evaluation
data. Package counts and package contents are separate; measured extraction
quantities and backend inventory conversion still require review.

The published [curated manifest](../manifest.json) records selected-image hashes,
synthetic status, receipt lengths and target recipe provenance. Detailed batch
records and the gallery remain local under ignored
`../../work/receipts/eval_lengths_20261029/`, with the original `images/` copies.
Selection was explicitly requested for the development dataset; it is not a pass
of the original frozen benchmark gate or formal human-labelled acceptance.

Future generation runs stay under `dataset/work/receipts/<batch-id>/`. Copy only
chosen receipt images into this directory and record them in the curated manifest.
See [receipt testing instructions](../README.md).
