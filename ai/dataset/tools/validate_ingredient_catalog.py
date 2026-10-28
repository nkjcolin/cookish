"""Validate the frozen receipt catalogue and its recipe snapshot without network calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG = REPO_ROOT / "ai/dataset/catalogs/ingridients.json"
MONEY = re.compile(r"\d+\.\d{2}")
SHA256 = re.compile(r"[a-f0-9]{64}")
DIMENSIONS = {"pcs": "count", "g": "mass", "kg": "mass", "ml": "volume", "l": "volume"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def unique_names(rows: list[dict], label: str) -> set[str]:
    names = [row["canonical_name"] for row in rows]
    require(len(names) == len(set(names)), f"Duplicate {label} canonical name")
    require(
        all(isinstance(name, str) and name.strip() == name and name for name in names),
        f"Invalid {label} canonical name",
    )
    return set(names)


def validate(catalog: dict, repo_root: Path = REPO_ROOT) -> None:
    """Raise on incomplete coverage, inconsistent purchase facts or stale recipe sources."""
    require(catalog["schema_version"] == 1, "Unsupported schema_version")
    require(catalog["currency"] == "SGD", "Expected SGD prices")
    require(catalog["purpose"] == "synthetic_receipt_generation", "Wrong catalogue purpose")
    checked_on = date.fromisoformat(catalog["checked_on"])
    products = catalog["products"]
    product_names = unique_names(products, "product")
    excluded_names = unique_names(catalog["excluded_ingredients"], "excluded ingredient")
    require(not product_names & excluded_names, "A product cannot also be excluded")
    require(excluded_names == {"water"}, "Only tap water is excluded in this snapshot")
    require(not catalog["unresolved_ingredients"], "Unresolved ingredient matches remain")
    recipe_names = catalog["recipe_ingredients"]
    require(len(recipe_names) == len(set(recipe_names)), "Duplicate recipe ingredient")
    require(
        set(recipe_names) == product_names | excluded_names, "Recipe ingredient coverage differs"
    )
    require(catalog["recipe_ingredient_count"] == len(recipe_names), "Ingredient count differs")
    require(catalog["retail_product_count"] == len(products), "Retail product count differs")

    skus = []
    for product in products:
        name = product["canonical_name"]
        sku = product["retailer_product_id"]
        skus.append(sku)
        require(isinstance(sku, str) and sku.isdigit(), f"{name}: invalid retailer SKU")
        require(product["retailer"] == "FairPrice", f"{name}: unsupported retailer")
        source = urlsplit(product["price_source"])
        require(
            source.scheme == "https"
            and source.netloc == "www.fairprice.com.sg"
            and source.path.startswith("/product/")
            and len(source.path) > len("/product/")
            and not source.query
            and not source.fragment,
            f"{name}: invalid product URL",
        )
        require(
            bool(product["product_name"].strip() and product["receipt_name"].strip()),
            f"{name}: missing product/stock name",
        )
        require(
            product["receipt_name_source"] == "retailer_sap_product_name"
            and product["receipt_name_verified_on_receipt"] is False,
            f"{name}: retailer stock name must not claim printed-receipt verification",
        )
        require(product["checked_on"] == catalog["checked_on"], f"{name}: mixed snapshot dates")
        retrieved = datetime.fromisoformat(product["retrieved_at"])
        require(
            retrieved.tzinfo is not None and retrieved.date() == checked_on,
            f"{name}: invalid retrieval timestamp",
        )
        require(
            bool(SHA256.fullmatch(product["source_html_sha256"])), f"{name}: missing source hash"
        )
        quantity = product["contents_per_package"]
        require(
            type(quantity) in (int, float) and Decimal(str(quantity)).is_finite() and quantity > 0,
            f"{name}: invalid package contents",
        )
        unit = product["contents_unit"]
        require(unit in DIMENSIONS, f"{name}: unsupported package unit")
        require(product["purchase_unit"] == "pack", f"{name}: price must be per purchased pack")
        require(
            product["quantity_evidence"]["field"] == "entity.metaData.DisplayUnit"
            and product["quantity_evidence"]["value"] == product["pack_description"],
            f"{name}: missing displayed quantity evidence",
        )
        label = product["pack_description"]
        if unit == "pcs":
            count = re.search(r"(\d+) per pack", label) or re.fullmatch(r"(\d+) S", label)
            require(
                count is not None and Decimal(count[1]) == Decimal(str(quantity)),
                f"{name}: piece count differs from displayed package count",
            )
        else:
            mass_or_volume = re.match(r"(\d+(?:\.\d+)?)\s*(kg|g|ml|l)\b", label, re.IGNORECASE)
            require(
                mass_or_volume is not None
                and mass_or_volume[2].lower() == unit
                and Decimal(mass_or_volume[1]) == Decimal(str(quantity)),
                f"{name}: contents differ from displayed package amount/unit",
            )
        if "items_per_package" in product:
            inner_count = re.search(r"\((\d+) per pack\)", label)
            require(
                inner_count is not None and int(inner_count[1]) == product["items_per_package"],
                f"{name}: inner item count differs from package label",
            )
        conversion = product["recipe_quantity_conversion"]
        if name == "cabbage":
            require(
                conversion == "requires_measured_head_weight"
                and unit == "pcs"
                and quantity == 1
                and product["weight_evidence_conflict"]["verified_weight"] is None,
                "Cabbage head weight must remain unknown",
            )
        elif name == "canned chickpea":
            require(
                conversion == "requires_verified_drained_weight"
                and product["quantity_basis"] == "as_sold_net_contents"
                and product["drained_contents_per_package"] is None,
                "Chickpea net weight must not be presented as drained weight",
            )
        else:
            require(conversion == "same_dimension_as_sold_only", f"{name}: unknown conversion rule")
            require(product["quantity_basis"] == "as_sold", f"{name}: unsupported quantity basis")
            require(
                all(DIMENSIONS.get(value) == DIMENSIONS[unit] for value in product["recipe_units"]),
                f"{name}: recipe comparison needs an unverified dimension conversion",
            )
        for field in ("unit_price_sgd", "regular_price_sgd"):
            value = product[field]
            require(
                isinstance(value, str) and bool(MONEY.fullmatch(value)) and Decimal(value) > 0,
                f"{name}: {field} must be a positive two-decimal string",
            )
        price, regular = Decimal(product["unit_price_sgd"]), Decimal(product["regular_price_sgd"])
        promo = product["promotion"]
        if promo is None:
            require(
                price == regular and product["price_basis"] == "listed_single_package",
                f"{name}: unexplained price difference",
            )
        else:
            discount = promo["discount_per_package_sgd"]
            require(
                bool(MONEY.fullmatch(discount))
                and Decimal(discount) > 0
                and price + Decimal(discount) == regular
                and promo["minimum_packages"] == 1
                and product["price_basis"] == "listed_single_package_promotion",
                f"{name}: invalid single-package promotion",
            )
            require(
                date.fromisoformat(promo["valid_from_as_listed"][:10])
                <= checked_on
                <= date.fromisoformat(promo["valid_until_as_listed"][:10]),
                f"{name}: promotion was not active on snapshot date",
            )
    require(len(skus) == len(set(skus)), "Duplicate retailer SKU; review the ingredient mapping")

    source_dir = "backend/seed/recipes"
    require(catalog["source_recipe_directory"] == source_dir, "Unexpected source recipe directory")
    actual_paths = {
        file.relative_to(repo_root).as_posix()
        for suffix in ("*.yaml", "*.yml")
        for file in (repo_root / source_dir).glob(suffix)
    }
    sources = catalog["source_recipes"]
    recorded_paths = [source["path"] for source in sources]
    require(len(recorded_paths) == len(set(recorded_paths)), "Duplicate source recipe")
    require(
        set(recorded_paths) == actual_paths,
        "Recipe file set changed or is unavailable; review catalogue coverage explicitly",
    )
    require(catalog["source_recipe_count"] == len(sources), "Source recipe count differs")
    source_names = set()
    for source in sources:
        file = repo_root / source["path"]
        require(
            hashlib.sha256(file.read_bytes()).hexdigest() == source["sha256"],
            f"Recipe changed since snapshot: {source['path']}; review catalogue explicitly",
        )
        require(bool(source["canonical_names"]), f"Missing source ingredients: {source['path']}")
        source_names.update(source["canonical_names"])
    require(source_names == set(recipe_names), "Recipe snapshot ingredient coverage differs")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args()
    try:
        catalog = json.loads(args.catalog.read_text())
        validate(catalog)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Invalid catalogue: {error}")
        return 1
    print(
        f"Valid: {len(catalog['products'])} products, {catalog['recipe_ingredient_count']} ingredients, "
        f"{catalog['source_recipe_count']} unchanged recipes; tap water excluded."
    )
    print("Quantity caveats: cabbage head weight and chickpea drained weight remain unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
