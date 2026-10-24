"""Evaluate saved predictions or explicitly run requests against a local AI API."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.runner import evaluate, load_manifest, markdown_report, run_cases  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--predictions", type=Path, help="Score saved JSON; no requests")
    source.add_argument(
        "--run", action="store_true", help="Explicitly send requests; may use school quota"
    )
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--timeout", type=float, default=35)
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        dest="case_ids",
        help="Run/score only this case ID; repeat to select several",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-formal", action="store_true")
    args = parser.parse_args()
    if args.out.exists() or args.out.with_suffix(".md").exists():
        parser.error("Output exists; choose a new filename to preserve earlier measurements")
    try:
        manifest = load_manifest(args.manifest)
        if args.case_ids:
            selected = set(args.case_ids)
            if selected - {case["id"] for case in manifest["cases"]}:
                raise ValueError("Unknown selected case")
            manifest = {
                **manifest,
                "cases": [case for case in manifest["cases"] if case["id"] in selected],
            }
        predictions = (
            run_cases(manifest, args.manifest.parent, args.url, args.timeout)
            if args.run
            else json.loads(args.predictions.read_text(encoding="utf-8"))
        )
        if not args.run and "predictions" in predictions:
            predictions = predictions["predictions"]
        summary = evaluate(manifest, predictions)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(
            1, f"Evaluation could not run ({type(exc).__name__}); check manifest and inputs.\n"
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps({"summary": summary, "predictions": predictions}, indent=2) + "\n"
    )
    args.out.with_suffix(".md").write_text(markdown_report(summary), encoding="utf-8")
    print(f"Report: {args.out}; formal dataset complete: {summary['formal_dataset_complete']}")
    return (
        1
        if summary["failures"] or (args.require_formal and not summary["formal_dataset_complete"])
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(main())
