"""Validate a rendered revision and finalise an ignored local batch."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

DATASET = Path(__file__).resolve().parents[1]
HERE = DATASET / "work/receipts/realistic_v2_final"
REVISION = DATASET / "work/receipts/realistic_v2"
BASELINE = DATASET / "work/receipts/20261024/original_cases.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", type=Path, default=REVISION)
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args()
    revision, batch = args.revision.resolve(), args.output.resolve()
    if not batch.is_relative_to((DATASET / "work").resolve()):
        parser.error("Generated batches must stay inside the ignored dataset/work/ directory")
    if batch.exists():
        parser.error("Output batch already exists; choose another --output to preserve it")
    if not BASELINE.is_file():
        parser.error(
            "The historical baseline is local-only; restore it before using this legacy tool"
        )
    data = json.loads((revision / "cases.json").read_text())
    records = json.loads((revision / "generation.json").read_text())
    assert data["revision"] == "realistic_v2" and data["synthetic"] is True
    assert len(data["recipes"]) == 10 and len(data["cases"]) == len(records) == 30
    assert {c["id"] for c in data["cases"]} == {r["id"] for r in records}
    assert Counter(c["scenario"] for c in data["cases"]) == {
        "enough": 10,
        "missing_some": 10,
        "below_half": 10,
    }
    original = json.loads(BASELINE.read_text())
    old_by_id = {c["id"]: c for c in original["cases"]}
    for case in data["cases"]:
        assert (revision / case["image"]).is_file()
        old = old_by_id[case["id"]]
        for key in (
            "recipe_id",
            "scenario",
            "servings",
            "missing_ingredients",
            "required_essential_count",
            "present_essential_count",
        ):
            assert case[key] == old[key], (case["id"], key)
        for item in case["purchases"]:
            assert item["count"] == item["purchase_count"] * item["contents_per_package"]
            assert item["count"] >= item["required_count"]
            assert Decimal(str(item["price_sgd"])) == (
                Decimal(item["unit_price_sgd"]) * item["purchase_count"]
            )
        assert Decimal(case["total_sgd"]) == sum(
            (Decimal(str(i["price_sgd"])) for i in case["purchases"]), Decimal(0)
        )
        assert Decimal(case["cash_sgd"]) - Decimal(case["total_sgd"]) == Decimal(case["change_sgd"])
        assert "FAIRPRICE XTRA\nJEM HYPERMART" in case["receipt_text"]
        assert "COOKISH TEST MART" not in case["receipt_text"]
    # Finalising a batch never automatically publishes its images into curated data.
    batch.mkdir(parents=True)
    destination = batch / "images"
    destination.mkdir(parents=True, exist_ok=True)
    for case in data["cases"]:
        source = revision / case["image"]
        shutil.copy2(source, destination / Path(case["image"]).name)
        assert digest(source) == digest(destination / Path(case["image"]).name)
        case["image"] = "images/" + Path(case["image"]).name
    (batch / "cases.json").write_text(json.dumps(data, indent=2) + "\n")
    for name in ("generation.json", "prompts.md", "price_catalog.json", "PRICES.md"):
        shutil.copy2(revision / name, batch / name)
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name("finish.py")), "--batch", str(batch)],
        check=True,
    )
    print(
        f"Finalised 30 receipts in {batch}. Copy selected images into dataset/receipt/generated/."
    )


if __name__ == "__main__":
    main()
