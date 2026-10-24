"""Validate local artifacts and build a gallery; no network or school calls."""

import hashlib
import html
import json
import struct
from collections import Counter
from pathlib import Path

DATASET = Path(__file__).resolve().parents[1]
HERE = DATASET / "recipe_receipts_20261024"
ROOT = DATASET.parent.parent
TITLES = {
    "enough": "1. Enough to cook",
    "missing_some": "2. Some ingredients missing",
    "below_half": "3. Fewer than half present",
}


def main():
    data = json.loads((HERE / "cases.json").read_text())
    records = json.loads((HERE / "generation.json").read_text())
    assert len(data["recipes"]) == 10 and len(data["cases"]) == 30
    assert len(records) == 30 and len({r["id"] for r in records}) == 30
    record_by_id = {record["id"]: record for record in records}
    assert Counter(c["scenario"] for c in data["cases"]) == {
        "enough": 10,
        "missing_some": 10,
        "below_half": 10,
    }
    for recipe in data["recipes"]:
        assert (
            hashlib.sha256((ROOT / recipe["source"]).read_bytes()).hexdigest()
            == recipe["source_sha256"]
        )
    for case in data["cases"]:
        case["image_review"] = record_by_id[case["id"]]["visual_review"]
        case["generation_prompt"] = record_by_id[case["id"]]["prompt"]
        content = (HERE / case["image"]).read_bytes()
        assert content[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", content[16:24])
        assert width <= 8192 and height <= 8192 and width * height <= 16_000_000
        case["image_bytes"] = len(content)
        case["image_dimensions"] = [width, height]
        case["within_api_3_mib_limit"] = len(content) <= 3 * 1024 * 1024
        case["image_sha256"] = hashlib.sha256(content).hexdigest()
    assert len({c["image_sha256"] for c in data["cases"]}) == 30
    (HERE / "cases.json").write_text(json.dumps(data, indent=2) + "\n")
    (HERE / "prompts.md").write_text(
        "# Actual built-in image generation prompts\n\n"
        + "\n\n".join(
            f"## {case['id']}\n\n```text\n{case['generation_prompt']}\n```"
            for case in data["cases"]
        )
        + "\n"
    )
    intended = {
        "synthetic": True,
        "note": "Historical retail-package design labels, not human-reviewed extraction labels. Review printed totals and units before using with the current API.",
        "cases": [
            {
                "id": c["id"],
                "kind": "receipt",
                "image": c["image"],
                "expected": [
                    {
                        "display_name": i["canonical_name"],
                        "count": i.get("purchase_count", i["count"]),
                        "unit": i.get("purchase_unit", i["unit"]),
                    }
                    for i in c["purchases"]
                ],
            }
            for c in data["cases"]
        ],
    }
    manifest = {
        "synthetic": True,
        "note": "Unlabelled generated images. Copy reviewed intended labels before scoring.",
        "cases": [
            {"id": c["id"], "kind": "receipt", "image": c["image"], "expected": None}
            for c in data["cases"]
        ],
    }
    (HERE / "intended_labels.json").write_text(json.dumps(intended, indent=2) + "\n")
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    esc = html.escape
    sections = []
    summary = [
        "# Scenario summary",
        "",
        "All recipes: 2 servings. Tap water available; other starting stock empty.",
        "",
        "| Recipe | Enough essential coverage | Missing some | Below half |",
        "|---|---:|---:|---:|",
    ]
    for index, recipe in enumerate(data["recipes"], 1):
        cases = [c for c in data["cases"] if c["recipe_id"] == recipe["recipe_id"]]
        summary.append(
            f"| {recipe['title']} | "
            + " | ".join(
                f"{c['present_essential_count']}/{c['required_essential_count']}" for c in cases
            )
            + " |"
        )
        rows = "".join(
            f"<tr><td>{esc(i['canonical_name'])}</td><td>{i['required_count']:g} {i['unit']}</td>"
            f"<td>{'essential' if i['essential'] else 'optional'}</td></tr>"
            for i in recipe["ingredients"]
        )
        cards = []
        for case in cases:
            missing = ", ".join(case["missing_ingredients"]) or "None"
            purchases = "; ".join(
                f"{i['canonical_name']}: "
                + (f"{i['purchase_count']} retail package(s), " if "purchase_count" in i else "")
                + f"{i['count']:g} {i['unit']} available contents"
                for i in case["purchases"]
            )
            warning = (
                ""
                if case["within_api_3_mib_limit"]
                else "<p class='warning'>Over API byte limit; compress before upload.</p>"
            )
            cards.append(
                f"<article class='{case['scenario']}' data-scenario='{case['scenario']}'>"
                f"<h3>{TITLES[case['scenario']]}</h3><p><strong>{case['id']}</strong> · "
                f"{case['present_essential_count']}/{case['required_essential_count']} essential ingredients</p>"
                f"<a href='{case['image']}'><img loading='lazy' src='{case['image']}' alt='{esc(case['id'])} synthetic receipt'></a>"
                f"<p><strong>Missing:</strong> {esc(missing)}</p>{warning}"
                f"<details><summary>Intended purchases</summary><p>{esc(purchases)}</p></details>"
                f"<details><summary>Intended printed text</summary><pre>{esc(case['receipt_text'])}</pre></details></article>"
            )
        sections.append(
            f"<section><h2>{index:02}. {esc(recipe['title'])}</h2>"
            f"<p>2 servings · <code>{esc(recipe['source'])}</code></p>"
            f"<details><summary>Recipe ingredient requirements</summary><table><thead><tr>"
            f"<th>Ingredient</th><th>Required amount</th><th>Role</th></tr></thead><tbody>{rows}</tbody></table></details>"
            f"<div class='cards'>{''.join(cards)}</div></section>"
        )
    page = (
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cookish synthetic receipt scenarios</title><style>
body{font:16px/1.5 system-ui,sans-serif;margin:0;background:#f4f5f3;color:#183027}main{max-width:1400px;margin:auto;padding:32px}
h1,h2,h3{line-height:1.2}header{max-width:900px}section{margin:36px 0;padding-top:20px;border-top:1px solid #ccd4cf}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin-top:20px}article{background:white;border-radius:12px;padding:18px;border-top:5px solid #398060}
.missing_some{border-top-color:#b28724}.below_half{border-top-color:#b5564d}img{width:100%;height:auto;display:block;border-radius:4px}details{margin:12px 0}summary{cursor:pointer}
pre{white-space:pre-wrap;font-size:12px}table{border-collapse:collapse}td,th{padding:6px 18px 6px 0;text-align:left}select{font:inherit;padding:8px}code{overflow-wrap:anywhere}.warning{color:#9b351e}
article[hidden]{display:none}@media(max-width:800px){main{padding:18px}.cards{grid-template-columns:1fr}}
</style><main><header><h1>Cookish receipt scenarios</h1><p>10 randomly selected backend recipes × 3 scenarios = 30 synthetic receipt images.</p>
<p>Each recipe serves two. Assume empty inventory except tap water. Click any receipt to open the full image. Retail package counts and available contents are recorded separately.</p>
<p>These are synthetic development fixtures. They do not establish real-world recognition accuracy or backend recommendation behavior.</p>
<label>Show <select id="filter"><option value="all">All scenarios</option><option value="enough">Enough to cook</option><option value="missing_some">Some missing</option><option value="below_half">Fewer than half present</option></select></label>
<p><a href="README.md">Instructions</a> · <a href="summary.md">Coverage table</a> · <a href="cases.json">Scenario specifications</a> · <a href="prompts.md">Generation prompts</a></p></header>
"""
        + "".join(sections)
        + """</main><script>document.getElementById('filter').addEventListener('change',e=>document.querySelectorAll('[data-scenario]').forEach(card=>{card.hidden=e.target.value!=='all'&&card.dataset.scenario!==e.target.value}));</script></html>"""
    )
    (HERE / "index.html").write_text(page)
    (HERE / "summary.md").write_text("\n".join(summary) + "\n")
    print(
        json.dumps(
            {
                "images": len(data["cases"]),
                "total_bytes": sum(c["image_bytes"] for c in data["cases"]),
                "over_3_mib": [c["id"] for c in data["cases"] if not c["within_api_3_mib_limit"]],
            }
        )
    )


if __name__ == "__main__":
    main()
