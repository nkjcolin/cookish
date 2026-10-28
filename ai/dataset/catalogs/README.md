# Retail ingredient catalogue

[`ingridients.json`](ingridients.json) is the frozen, one-time retail snapshot for
synthetic receipt generation. The filename retains the requested spelling.
It covers all **42 distinct ingredients in 48 backend recipes** as checked on
**2026-10-28**: 41 purchasable ingredient/product mappings and one explicit
exclusion for tap water. There are no unmatched ingredient names.

Each product was selected from a public FairPrice product page. Package contents,
retailer stock descriptions, regular prices and applicable single-package
promotions were extracted from that page. Money was calculated using `Decimal`
and cross-checked against the page's embedded Product JSON-LD price. The default
online context was `Fairprice PFC`, without a selected postcode or physical store.
Marketplace listings are identified separately. These are online snapshot prices,
not a FairPrice JEM checkout quote, availability guarantee or actual transaction.

## Structure

The flat `products` list keeps the core fields from the historical
`price_catalog.json`: `canonical_name`, `receipt_name`, `contents_per_package`,
`contents_unit`, `unit_price_sgd`, `price_source`, `price_basis` and `notes`.
Additional fields make the source and quantity interpretation explicit:

| Field | Meaning |
|---|---|
| `retailer_product_id` | Retailer SKU, not a backend `ingredient_id` |
| `product_name`, `brand`, `marketplace_listing` | Product identity and listing type |
| `receipt_name` | Exact retailer-supplied `SAP Product Name`, including source spelling |
| `receipt_name_source`, `receipt_name_verified_on_receipt` | Stock-name provenance; printed POS receipt verification is **false** |
| `pack_description`, `quantity_evidence` | Retailer's displayed package label and source field |
| `contents_per_package`, `contents_unit` | Total as-sold contents of one purchased pack, retaining `kg`, `g`, `ml` or `pcs` |
| `purchase_unit` | `pack`; prices are per purchased pack, not per gram |
| `recipe_units`, `recipe_quantity_conversion` | Recipe comparison dimension and any unresolved quantity issue |
| `unit_price_sgd`, `regular_price_sgd` | Positive two-decimal strings for snapshot single-pack and regular prices |
| `promotion` | Single-pack discount, minimum purchase, listed dates and order type, or null |
| `price_source`, `checked_on`, `retrieved_at`, `source_html_sha256` | Product URL, snapshot date, UTC retrieval timestamp and saved-page hash |

Top-level `source_recipes` records each source recipe's path, hash and ingredient
names. `recipe_ingredients` includes water even though `excluded_ingredients`
explains why it does not become a purchased receipt line. `unresolved_ingredients`
is empty: product matching is complete, while the quantity caveats below remain.

## Quantity rules

- Eggs: one carton contains **10 eggs**. Its secondary label of 550 g does not
  replace the piece count.
- Firm tofu: **450 g total** across two blocks in one purchased pack, not 900 g.
- Rice, frozen peas and pumpkin keep their listed **1 kg** packages. Two packages
  provide 2 kg. Convert to grams only for an explicit calculation.
- Lemons: **3 pieces** per pack; fruit weight is not guessed.
- Cabbage: **1 head** per pack. The SAP name says 1.2 kg while another metadata
  field says 1.5 kg. Both conflicting values are recorded; verified head weight
  remains null. Measure it before claiming a gram-based recipe is covered.
- Chickpeas: **400 g net contents including liquid**. Drained contents remain
  null. Obtain a verified drained amount before claiming enough edible chickpeas.
- Other masses are as sold. Trimming, peeling, shelling and cooking yields are
  not inferred. Fresh/dried mushrooms and cooked/uncooked rice stay distinct;
  the cod entry is Atlantic cod rather than sablefish sold as "black cod".

Single-pack promotions are recorded for five products. They were valid at the
snapshot date; listed source timestamps do not specify a timezone. A generator
using a different receipt date must check the recorded conditions and use the
regular snapshot price when the promotion is inapplicable. Neither price is
automatically refreshed or represented as today's live quote.

## Offline use and validation

Generation should read this JSON file, select by `canonical_name` and multiply
whole purchased packages by the package price using `Decimal`. For example:

```python
import json
from decimal import Decimal
from pathlib import Path

catalogue = json.loads(Path("ai/dataset/catalogs/ingridients.json").read_text())
products = {product["canonical_name"]: product for product in catalogue["products"]}
egg = products["egg"]
purchased_packages = 2
total_eggs = purchased_packages * egg["contents_per_package"]  # 20 pcs
line_price = Decimal(egg["unit_price_sgd"]) * purchased_packages  # SGD 5.70
```

From the repository root, validate coverage, prices, units, promotions and the
unchanged recipe snapshot without network calls or additional dependencies:

```bash
python3 ai/dataset/tools/validate_ingredient_catalog.py
```

The validator deliberately fails if a recipe is added, removed or changed. Review
the changed recipes and catalogue explicitly rather than silently modifying this
frozen source. It checks saved facts and coverage; it cannot prove current prices,
printed receipt text or edible yields.

Public source HTML, search candidates and one-time collection/assembly scripts
are retained locally under ignored `dataset/work/catalogue/20261028/`. They are
not required by the validator and are not included in Git or Docker images.
The older 28-product `work/receipts/20261024/price_catalog.json` remains historical
batch evidence and was not treated as a verified current price source.

This file is for synthetic receipts, not AI inference, inventory IDs, model API
pricing or reviewed extraction labels. The existing historical generation helpers
still contain their original product/scenario logic; wiring a reusable
configuration-driven generator and selection command to this catalogue is a
separate task. New generated batches belong in ignored `dataset/work/`; only
handpicked images and their manifest entries belong in `dataset/receipt/`.
