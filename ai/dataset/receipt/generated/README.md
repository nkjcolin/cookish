# Generated receipt test images

The 30 PNGs are synthetic, realistic-looking test receipts based on the existing
FairPrice reference: `FAIRPRICE XTRA / JEM HYPERMART`. They are not actual store
transactions. Prices use online product references where available, with estimates
identified in the supporting data.

Each of 10 selected backend recipes has `enough`, `missing_some` and `below_half`
variants. Below half means fewer than half the required ingredients are present.
All recipes use two servings and assume only tap water is initially available.

Package counts and package contents are different: `2X$2.55/Unit` means two
packages, while `280G` in a product name is the size of one package. The scenario
comparison records the total usable contents separately. The current AI prompt
returns total contents in the receipt's original unit (including kg/g/l/ml/pcs), multiplying
package count by readable contents once. Unknown measured amounts remain null;
no drained yields or typical sizes are inferred. Recipe matching and inventory
writes still belong to the backend.

Use any PNG with `receipt.md` in the existing `ai/laas.py` prompt-file test block.
For the gallery, recipe requirements, missing ingredients, actual generation
prompts and price sources, see
[the dataset documentation](../../recipe_receipts_20261024/README.md).
