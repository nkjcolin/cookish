"""Prepare realistic retail-pack receipt revisions; no image or school API calls."""

import copy
import json
import math
from decimal import Decimal
from pathlib import Path

DATASET = Path(__file__).resolve().parents[1]
BASELINE = DATASET / "work/receipts/20261024/original_cases.json"
REVISION = DATASET / "work/receipts/realistic_v2"
VEGETABLES = "https://www.fairprice.com.sg/vegetables"

# Content is usable inventory quantity per purchased retail package, not AI count.
# Price references are observed online listings, not a quote for the JEM branch.
PRODUCTS = [
    (
        "egg",
        "PSR FRESH EGGS 10S",
        10,
        "pcs",
        "2.85",
        "https://www.fairprice.com.sg/product/pasar-fresh-eggs-10-eggs-550g-451724",
        "listed",
        "10 eggs per purchased carton",
    ),
    (
        "soy sauce",
        "FP LT SOYA SAUCE 660ML",
        660,
        "ml",
        "2.42",
        "https://www.fairprice.com.sg/product-listing?tag=seafood-mala-xiang-guo---light-soya-sauce",
        "listed regular price",
        "regular price, without the listed promotion",
    ),
    (
        "spring onion",
        "PSR SPRING ONION 100G",
        100,
        "g",
        "1.25",
        "https://www.fairprice.com.sg/product/pasar-malaysia-spring-onion-100g-10344536",
        "listed",
        "",
    ),
    (
        "uncooked rice",
        "FP THAI HOM MALI RICE 1KG",
        1000,
        "g",
        "3.90",
        "https://www.fairprice.com.sg/product/fairprice-gold-thai-hom-mali-superior-rice-1kg-13097849",
        "listed",
        "dry rice; not cooked rice",
    ),
    (
        "firm tofu",
        "FORTUNE TAU KWA 450G",
        450,
        "g",
        "1.42",
        "https://www.fairprice.com.sg/en/fairprice/beancurd-tofu",
        "listed",
        "one 450 g retail pack, not two separate purchased packs",
    ),
    (
        "coconut milk",
        "AYAM COCONUT MILK 200ML",
        200,
        "ml",
        "1.40",
        "https://www.fairprice.com.sg/product/ayam-brand-coconut-milk-200ml-10725136",
        "listed",
        "",
    ),
    (
        "carrot",
        "PSR CARROTS 500G",
        500,
        "g",
        "1.10",
        VEGETABLES,
        "listed",
        "single-pack price; no multi-buy applied",
    ),
    ("long bean", "SF LONG BEAN 200G", 200, "g", "1.65", VEGETABLES, "listed", ""),
    ("onion", "CHEF RED ONION 700G", 700, "g", "1.70", VEGETABLES, "listed", ""),
    ("garlic", "CHEF WHITE GARLIC 500G", 500, "g", "2.85", VEGETABLES, "listed", ""),
    ("ginger", "SF OLD GINGER 200G", 200, "g", "2.20", VEGETABLES, "listed", ""),
    (
        "turmeric powder",
        "BABAS TURMERIC PWDR 125G",
        125,
        "g",
        "1.78",
        "https://www.fairprice.com.sg/en/fairprice/search/spices",
        "listed",
        "plain turmeric, not curry powder",
    ),
    (
        "chilli paste",
        "SINGLONG CHILLI PASTE 500G",
        500,
        "g",
        "1.73",
        "https://www.fairprice.com.sg/category/chili-paste---sambal",
        "listed",
        "plain chilli paste, not sambal belacan",
    ),
    (
        "canola oil",
        "FP CANOLA OIL 500ML",
        500,
        "ml",
        "2.90",
        "https://www.fairprice.com.sg/product-listing?category=canola-oil&pageType=category&url=canola-oil",
        "listed",
        "",
    ),
    (
        "salt",
        "FP FINE SALT 500G",
        500,
        "g",
        "0.45",
        "https://www.fairprice.com.sg/tag/recipe-easy-bean-stew",
        "listed",
        "",
    ),
    (
        "cabbage",
        "MY ROUND CABBAGE 1KG",
        1000,
        "g",
        "3.25",
        "https://www.fairprice.com.sg/product-listing?category=fresh-produce--1&pageType=category&url=fresh-produce--1",
        "listed price; assumed pack weight",
        "listing is one cabbage per pack; 1 kg is this synthetic fixture's chosen weight",
    ),
    (
        "chicken thigh",
        "MG CHICK THIGH BNLS 330G",
        330,
        "g",
        "9.40",
        "https://payment.fairprice.com.sg/product/master-grocer-fresh-chicken-thigh-boneless-and-skinless-330-g-90175209",
        "listed",
        "raw boneless skinless thigh; not marinated or bone-in",
    ),
    ("potato", "HOLLAND POTATO 1KG", 1000, "g", "1.40", VEGETABLES, "listed", ""),
    (
        "lemon",
        "FRESH LEMON 1PC",
        1,
        "pcs",
        "0.85",
        "",
        "estimated",
        "plausible loose-lemon price; no exact SKU price verified",
    ),
    (
        "black pepper",
        "FP GROUND BLACK PEPPER 100G",
        100,
        "g",
        "4.13",
        "https://www.fairprice.com.sg/tag/recipe-easy-bean-stew",
        "listed",
        "",
    ),
    (
        "broccoli",
        "AGRO FRESH BROCCOLI 280G",
        280,
        "g",
        "2.55",
        "https://omni.fairprice.com.sg/product/orgo-fresh-royal-broccoli-280-g-90153099",
        "listed promotional price",
        "two 280 g packs are needed for the recipe's 300 g",
    ),
    (
        "rice vermicelli",
        "FP RICE VERMICELLI 400G",
        400,
        "g",
        "1.16",
        "https://www.fairprice.com.sg/vermicelli",
        "listed",
        "",
    ),
    (
        "cucumber",
        "MY JAPANESE CUCUMBER 400G",
        400,
        "g",
        "2.40",
        VEGETABLES,
        "listed regular price",
        "regular price, without the listed promotion",
    ),
    ("tomato", "FRESH TOMATOES 600G", 600, "g", "2.30", VEGETABLES, "listed", ""),
    (
        "canned chickpea",
        "CIRIO CHICK PEAS 400G",
        240,
        "g",
        "3.23",
        "https://www.fairprice.com.sg/product/cirio-ceci-chick-peas-400g-12603933",
        "listed",
        "400 g net, 240 g drained edible contents; recipe comparison uses drained weight",
    ),
    (
        "cooked rice",
        "CJ COOKED WHITE RICE 210G",
        210,
        "g",
        "2.25",
        "https://www.fairprice.com.sg/category/supplier-2-off-cj-2",
        "listed",
        "two ready-cooked trays provide 420 g; not dry rice",
    ),
    (
        "soba noodle",
        "HAKUBAKU ORG SOBA 270G",
        270,
        "g",
        "4.28",
        "https://www.fairprice.com.sg/product-listing?personalisationType=SIMILAR_PRODUCT&title=Similar+Products&trackinfo=1304789",
        "listed",
        "",
    ),
    (
        "sesame oil",
        "DBL PAGODA SESAME OIL 150ML",
        150,
        "ml",
        "3.50",
        "https://www.fairprice.com.sg/sesame-oil",
        "listed",
        "",
    ),
]


def main():
    if not BASELINE.is_file():
        raise SystemExit(
            "Historical local baseline is missing; batch archives are not stored in Git"
        )
    if (REVISION / "cases.json").exists():
        raise FileExistsError("Revision already prepared; refusing to reset it")
    REVISION.mkdir(parents=True, exist_ok=True)
    (REVISION / "images").mkdir(exist_ok=True)
    data = copy.deepcopy(json.loads(BASELINE.read_text()))
    data["reference_images"] = [
        str((DATASET / "receipt" / Path(path).name).relative_to(DATASET.parent.parent))
        for path in data["reference_images"]
    ]
    catalog = {
        name: {
            "canonical_name": name,
            "receipt_name": label,
            "contents_per_package": contents,
            "contents_unit": unit,
            "unit_price_sgd": price,
            "price_source": source,
            "price_basis": basis,
            "notes": notes,
        }
        for name, label, contents, unit, price, source, basis, notes in PRODUCTS
    }
    assert len(catalog) == len(PRODUCTS)
    for number, case in enumerate(data["cases"], 1):
        purchases = []
        for old in case["purchases"]:
            product = catalog[old["canonical_name"]]
            quantity = math.ceil(old["required_count"] / product["contents_per_package"])
            price = Decimal(product["unit_price_sgd"])
            item = {
                **old,
                **product,
                "count": quantity * product["contents_per_package"],
                "unit": product["contents_unit"],
                "purchase_count": quantity,
                "purchase_unit": "pcs",
                "price_sgd": float(price * quantity),
                "quantity_text": f"{quantity}X${price:.2f}/Unit",
            }
            assert item["count"] >= old["required_count"]
            purchases.append(item)
        case["purchases"] = purchases
        total = sum((Decimal(str(i["price_sgd"])) for i in purchases), Decimal(0))
        # Whole-dollar tender gives believable cash/change arithmetic, including cents.
        cash = Decimal(math.ceil(total))
        change = cash - total
        lines = [
            "FAIRPRICE XTRA",
            "JEM HYPERMART",
            "50 Jurong Gateway Road",
            "#B1-21/22 & #B3-01",
            "Singapore 608549",
            "TEL: 6339 1729",
            "--------------------------------",
            f"24/10/2026  14:{22 + number // 60:02}:{number % 60:02}",
            "POS 03  CASHIER 06",
            "--------------------------------",
        ]
        layout = (number - 1) % 3
        for item in purchases:
            name_line = f"{item['receipt_name']:<27} {item['price_sgd']:.2f}"
            qty_line = f"  {item['quantity_text']}"
            lines.extend([qty_line, name_line] if layout == 1 else [name_line, qty_line])
        lines.extend(
            [
                "--------------------------------",
                f"TOTAL SGD                  {total:.2f}",
                f"CASH                       {cash:.2f}",
                f"CHANGE                     {change:.2f}",
                "GST INCLUDED",
                f"{sum(i['purchase_count'] for i in purchases)} ITEMS",
                "THANK YOU. PLEASE COME AGAIN.",
            ]
        )
        case["receipt_text"] = "\n".join(lines)
        case["total_sgd"] = str(total)
        case["cash_sgd"] = str(cash)
        case["change_sgd"] = str(change)
        case["image_review"] = "pending revised image generation"
        case["generation_prompt"] = (
            "Use case: photorealistic-natural. Generate ONE separate portrait phone photograph of a "
            "Singapore supermarket receipt, approximately 1024x1536. Closely follow the PROVIDED FairPrice "
            "reference photo, including the exact FAIRPRICE XTRA / JEM HYPERMART title, compact small "
            "monospaced thermal printing, narrow off-white paper and ordinary checkout layout. Reference "
            "is for store title, typography, photographic texture and receipt layout; replace all purchases "
            "with the exact text below. Do not reproduce the reference's original purchases. "
            "Make it look like an authentic casual phone snapshot, not a polished graphic, poster, "
            "illustration, pristine scan or oversized evenly typeset mockup. Keep the entire receipt visible "
            "with a thin margin and a little neutral tabletop. Slight natural crumpling, small folds, soft "
            "shadows, mildly uneven faded ink and modest perspective are welcome; all purchases and prices "
            "must remain readable. Keep heading modest and item text dense like the reference. "
            "Every name suffix is a real retail PACK SIZE; the separate 1X$.../Unit or 2X$.../Unit line is "
            "the number of PACKAGES bought. Do not turn pack contents into the purchase count. Each amount "
            "on the item line is the line total, not a per-kilogram price. Exact item names, package sizes, "
            "purchase counts, decimal prices, cash and change are critical. No added or missing purchases; "
            "no substitutions, no duplicated items. No COOKISH TEST MART, SYNTHETIC banners, case labels, "
            "recipe/scenario names, invented discounts, added tax, personal/card details, barcode or QR code. "
            "Synthetic provenance is retained externally in dataset metadata. Avoid large empty "
            "decorative margins. Render the following text verbatim:\n" + case["receipt_text"]
        )
        for stale in ("image_bytes", "image_dimensions", "image_sha256", "within_api_3_mib_limit"):
            case.pop(stale, None)
    data["revision"] = "realistic_v2"
    data["assumptions"] = [
        "Synthetic realistic-looking development images; not actual merchant transactions or human labels.",
        "Original ten recipes, two servings, unchanged ingredient-presence scenarios; only tap water initially available.",
        "Retail package counts differ from edible contents used for recipe comparisons. No app conversion is implemented here.",
        "purchase_count/purchase_unit describe receipt extraction; count/unit describe total available package contents.",
        "Chickpeas: 400 g net per can, conservative 240 g drained edible contents, two cans for the 300 g recipe.",
        "Cabbage fixture chooses a 1 kg retail head; the price source lists one head without a fixed weight.",
        "Prices are online listing references checked 2026-10-24; lemon is an explicitly marked estimate.",
        "Online prices, promotions and marketplace products are not guaranteed stock/prices at the named branch.",
        "No claim about current backend recipe ranking or inventory stock conversion is made.",
    ]
    data["price_catalog"] = "price_catalog.json"
    (REVISION / "cases.json").write_text(json.dumps(data, indent=2) + "\n")
    price_data = {
        "checked_on": "2026-10-24",
        "currency": "SGD",
        "synthetic": True,
        "note": "Online reference prices, not an actual JEM checkout quote. Product descriptions are abbreviated for receipt realism.",
        "drained_weight_source": "https://alivini.com/wp-content/uploads/product_pdf/F1400414-TS.pdf",
        "products": list(catalog.values()),
    }
    (REVISION / "price_catalog.json").write_text(json.dumps(price_data, indent=2) + "\n")
    (REVISION / "prompts.md").write_text(
        "# Realistic receipt generation prompts\n\n"
        + "\n\n".join(
            f"## {case['id']}\n\n```text\n{case['generation_prompt']}\n```"
            for case in data["cases"]
        )
        + "\n"
    )
    rows = [
        "# Retail pack and price references",
        "",
        "Observed online on 2026-10-24; not a JEM branch price or availability guarantee.",
        "",
        "| Ingredient | Receipt description | Contents per pack | Price/pack SGD | Basis |",
        "|---|---|---|---:|---|",
    ]
    for p in catalog.values():
        basis = (
            f"[{p['price_basis']}]({p['price_source']})" if p["price_source"] else p["price_basis"]
        )
        rows.append(
            f"| {p['canonical_name']} | {p['receipt_name']} | {p['contents_per_package']:g} {p['contents_unit']} | {p['unit_price_sgd']} | {basis} |"
        )
    rows.extend(
        [
            "",
            "Cabbage weight is a chosen synthetic pack weight. Chickpea drained weight is from the [product specification](https://alivini.com/wp-content/uploads/product_pdf/F1400414-TS.pdf).",
            "",
            "Package counts and contents must stay separate. A receipt's 2 cans is not 2 g; 400 g net chickpeas is not 400 g drained food.",
        ]
    )
    (REVISION / "PRICES.md").write_text("\n".join(rows) + "\n")
    print(
        json.dumps(
            {"revision": str(REVISION), "cases": len(data["cases"]), "products": len(catalog)}
        )
    )


if __name__ == "__main__":
    main()
