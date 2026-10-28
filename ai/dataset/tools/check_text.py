"""Read-only macOS OCR aid, separate from the school model under test."""

import argparse
import json
import re
import subprocess
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
HERE = TOOL_DIR.parent / "work/receipts/20261024"
CACHE = TOOL_DIR.parent.parent / "output/dataset/.swift-cache"


def normalized(value):
    return re.sub(r"[^A-Z0-9.]", "", value.upper())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, default=HERE, help="Local batch directory")
    batch = parser.parse_args().batch.resolve()
    if not batch.is_relative_to((TOOL_DIR.parent / "work").resolve()):
        parser.error("Batch records must stay inside the ignored dataset/work/ directory")
    if not (batch / "cases.json").is_file():
        parser.error("Local cases.json is required; batches are not stored in Git")
    CACHE.mkdir(parents=True, exist_ok=True)
    cases = json.loads((batch / "cases.json").read_text())["cases"]
    present = [case for case in cases if (batch / case["image"]).is_file()]
    result = subprocess.run(
        [
            "swift",
            "-module-cache-path",
            str(CACHE),
            str(TOOL_DIR / "inspect_text.swift"),
            *[str(batch / case["image"]) for case in present],
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    results = json.loads(result.stdout)
    reports = []
    for case, ocr in zip(present, results, strict=True):
        lines = ocr.get("lines", [])
        text = normalized(" ".join(lines))
        absent_names, absent_quantities = [], []
        for item in case["purchases"]:
            name = item["canonical_name"]
            printed = item.get(
                "receipt_name", "CHICKPEAS DRAINED" if name == "canned chickpea" else name
            )
            if normalized(printed) not in text:
                absent_names.append(name)
            quantity = item.get("quantity_text", f"QTY {item['count']:g} {item['unit']}")
            if normalized(quantity) not in text:
                absent_quantities.append(quantity)
        reports.append(
            {
                "id": case["id"],
                "image": case["image"],
                "lines": lines,
                "names_not_found": absent_names,
                "quantities_not_found": absent_quantities,
                "note": "OCR is an aid, not proof of exact item/quantity association or human labels.",
            }
        )
    (batch / "ocr_review.json").write_text(json.dumps(reports, indent=2) + "\n")
    print(
        json.dumps(
            {
                "checked": len(reports),
                "flagged": [
                    {k: r[k] for k in ("id", "names_not_found", "quantities_not_found")}
                    for r in reports
                    if r["names_not_found"] or r["quantities_not_found"]
                ],
            }
        )
    )


if __name__ == "__main__":
    main()
