"""Label-based evaluation. No model call is made unless --run is explicitly used."""

import base64
import json
import math
import mimetypes
import re
import time
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

KINDS = {"receipt", "photo", "typed", "voice", "interpret"}


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("synthetic"), bool)
        or not isinstance(data.get("cases"), list)
        or not data["cases"]
    ):
        raise ValueError("Manifest needs synthetic: true/false and a nonempty cases array")
    ids = set()
    for case in data["cases"]:
        if not isinstance(case, dict):
            raise ValueError("Cases must be objects")
        if not isinstance(case.get("id"), str) or case["id"] in ids:
            raise ValueError("Case IDs must be unique strings")
        ids.add(case["id"])
        if case.get("kind") not in KINDS:
            raise ValueError("Unknown case kind")
        label = case.get("expected_adjust" if case["kind"] == "interpret" else "expected")
        if label is not None and not isinstance(
            label, dict if case["kind"] == "interpret" else list
        ):
            raise ValueError("Expected food labels must be arrays; adjustments must be objects")
        if isinstance(label, list):
            for item in label:
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("display_name"), str)
                    or not item["display_name"].strip()
                ):
                    raise ValueError("Every expected item requires display_name")
                if not isinstance(item.get("aliases", []), list) or not all(
                    isinstance(alias, str) for alias in item.get("aliases", [])
                ):
                    raise ValueError("Aliases must be arrays of strings")
        if case["kind"] in {"receipt", "photo"} and not isinstance(case.get("image"), str):
            raise ValueError("Image cases require an image path")
        if case["kind"] not in {"receipt", "photo"} and not isinstance(case.get("text"), str):
            raise ValueError("Text cases require text")
    return data


def _name(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def _matching(expected, actual):
    """Maximum one-to-one name/explicit-alias matching, including duplicate foods."""
    owners = {}

    def assign(index, seen):
        name = _name(actual[index].get("display_name", ""))
        for target, label in enumerate(expected):
            names = [label["display_name"], *label.get("aliases", [])]
            if target in seen or name not in {_name(value) for value in names}:
                continue
            seen.add(target)
            if target not in owners or assign(owners[target], seen):
                owners[target] = index
                return True
        return False

    for index in range(len(actual)):
        assign(index, set())
    return {actual_index: expected_index for expected_index, actual_index in owners.items()}


def _percentile(values, percentile):
    return sorted(values)[max(0, math.ceil(percentile * len(values)) - 1)] if values else None


def _adjust(value):
    return {key: entry for key, entry in value.items() if entry is not None and entry != []}


def evaluate(manifest: dict, predictions: dict) -> dict:
    tp = fp = fn = count_errors = unit_errors = compared_counts = compared_units = 0
    non_food = failures = labelled = interpret_correct = interpret_labelled = 0
    latencies, success_latencies, calibration, corrections = [], [], [], []
    labelled_kinds = Counter()
    known_input = known_output = unknown_usage = 0
    providers, models = set(), set()
    details = []
    for case in manifest["cases"]:
        prediction = predictions.get(case["id"], {"status": 0, "error": "missing prediction"})
        success = prediction.get("status") == 200
        failures += not success
        latency = prediction.get("latency_ms")
        if isinstance(latency, (int, float)) and math.isfinite(latency) and latency >= 0:
            latencies.append(latency)
            if success:
                success_latencies.append(latency)
        providers.add(prediction.get("provider") or "unknown")
        models.add(prediction.get("model") or "unknown")
        usage = [prediction.get("input_tokens"), prediction.get("output_tokens")]
        if all(type(value) is int and value >= 0 for value in usage):
            known_input += usage[0]
            known_output += usage[1]
        else:
            unknown_usage += 1
        if (
            isinstance(case.get("correction_seconds"), (int, float))
            and math.isfinite(case["correction_seconds"])
            and case["correction_seconds"] >= 0
        ):
            corrections.append(case["correction_seconds"])
        body = prediction.get("body") or {}
        if case["kind"] == "interpret":
            expected = case.get("expected_adjust")
            if expected is not None:
                interpret_labelled += 1
                interpret_correct += success and _adjust(body.get("adjust", {})) == _adjust(
                    expected
                )
            continue
        expected = case.get("expected")
        if expected is None:
            details.append(
                {"id": case["id"], "labelled": False, "status": prediction.get("status")}
            )
            continue
        labelled += 1
        labelled_kinds[case["kind"]] += 1
        actual = body.get("items", []) if success else []
        pairs = _matching(expected, actual)
        tp += len(pairs)
        fp += len(actual) - len(pairs)
        fn += len(expected) - len(pairs)
        for index, target in pairs.items():
            if "count" in expected[target]:
                compared_counts += 1
                count_errors += actual[index].get("count") != expected[target]["count"]
            if "unit" in expected[target]:
                compared_units += 1
                unit_errors += actual[index].get("unit") != expected[target]["unit"]
        excluded = {_name(value) for value in case.get("non_food_names", [])}
        non_food += sum(_name(item.get("display_name", "")) in excluded for item in actual)
        for index, item in enumerate(actual):
            confidence = item.get("confidence")
            if (
                isinstance(confidence, (int, float))
                and math.isfinite(confidence)
                and 0 <= confidence <= 1
            ):
                calibration.append((confidence, int(index in pairs)))
        details.append(
            {
                "id": case["id"],
                "labelled": True,
                "matched": len(pairs),
                "false_positives": len(actual) - len(pairs),
                "false_negatives": len(expected) - len(pairs),
            }
        )
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    bins = []
    for lower in (0.0, 0.2, 0.4, 0.6, 0.8):
        upper = round(lower + 0.2, 1)
        values = [(p, y) for p, y in calibration if lower <= p and (p < upper or lower == 0.8)]
        bins.append(
            {
                "lower": lower,
                "upper": round(lower + 0.2, 1),
                "n": len(values),
                "accuracy": sum(y for _, y in values) / len(values) if values else None,
                "mean_confidence": sum(p for p, _ in values) / len(values) if values else None,
            }
        )
    enough_labels = (
        labelled_kinds["receipt"] >= 30
        and labelled_kinds["photo"] >= 20
        and labelled_kinds["voice"] >= 20
    )
    real_provider = providers == {"soclaas"}
    return {
        "synthetic": manifest["synthetic"],
        "cases": len(manifest["cases"]),
        "labelled_food_cases": labelled,
        "labelled_by_kind": dict(labelled_kinds),
        "failures": failures,
        "providers": sorted(providers),
        "models": sorted(models),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "count_comparisons": compared_counts,
        "count_errors": count_errors,
        "unit_comparisons": compared_units,
        "unit_errors": unit_errors,
        "known_non_food_inclusions": non_food,
        "interpretation_cases": interpret_labelled,
        "interpretation_accuracy": interpret_correct / interpret_labelled
        if interpret_labelled
        else None,
        "p50_ms_all": _percentile(latencies, 0.5),
        "p95_ms_all": _percentile(latencies, 0.95),
        "p95_ms_success": _percentile(success_latencies, 0.95),
        "known_input_tokens": known_input,
        "known_output_tokens": known_output,
        "cases_with_unknown_usage": unknown_usage,
        "cost": None,
        "cost_note": "School pricing/quota terms have not been supplied.",
        "confidence_brier_score": sum((p - y) ** 2 for p, y in calibration) / len(calibration)
        if calibration
        else None,
        "confidence_bins": bins,
        "human_correction_observations": len(corrections),
        "mean_correction_seconds": sum(corrections) / len(corrections) if corrections else None,
        "formal_dataset_complete": enough_labels and not manifest["synthetic"] and real_provider,
        "precision_target_met": precision >= 0.9 if precision is not None else None,
        "latency_target_met": _percentile(success_latencies, 0.95) <= 10000
        if success_latencies
        else None,
        "details": details,
    }


def make_payload(case: dict, directory: Path):
    kind = case["kind"]
    if kind in {"receipt", "photo"}:
        image = directory / case["image"]
        if image.stat().st_size > 3 * 1024 * 1024:
            raise ValueError("Compress evaluation images to at most 3 MiB")
        media_type = mimetypes.guess_type(image)[0]
        if media_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError("Evaluation images must be JPEG, PNG or WebP")
        return "/ai/parse-image", {
            "kind": kind,
            "media_type": media_type,
            "image_base64": base64.b64encode(image.read_bytes()).decode(),
        }
    if kind == "interpret":
        return "/ai/interpret", {"text": case["text"]}
    return "/ai/parse-items", {"text": case["text"], "source": kind}


def run_cases(manifest: dict, directory: Path, url: str, timeout: float = 35) -> dict:
    predictions = {}
    for case in manifest["cases"]:
        path, payload = make_payload(case, directory)
        request = Request(
            url.rstrip("/") + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.monotonic()
        try:
            try:
                response = urlopen(request, timeout=timeout)
            except HTTPError as exc:
                response = exc
            with response:
                status, headers = response.status, response.headers
                body = json.load(response)
        except (URLError, TimeoutError, ValueError):
            predictions[case["id"]] = {
                "status": 0,
                "error": "Connection, timeout or invalid JSON",
                "latency_ms": round((time.monotonic() - started) * 1000),
            }
            continue

        def header_int(name, headers=headers):
            value = headers.get(name)
            return int(value) if value is not None and value.isdecimal() else None

        # Evaluation outputs intentionally omit images, input text and raw OCR text.
        if "items" in body:
            body = {
                "items": [
                    {key: item.get(key) for key in ("display_name", "count", "unit", "confidence")}
                    for item in body["items"]
                ]
            }
        elif "adjust" in body:
            body = {"adjust": body["adjust"]}
        else:
            body = {"error": {"code": (body.get("error") or {}).get("code", "UNKNOWN")}}
        predictions[case["id"]] = {
            "status": status,
            "body": body,
            "latency_ms": round((time.monotonic() - started) * 1000),
            "provider": headers.get("x-ai-provider"),
            "model": headers.get("x-ai-model"),
            "input_tokens": header_int("x-ai-input-tokens"),
            "output_tokens": header_int("x-ai-output-tokens"),
            "attempts": header_int("x-ai-attempts"),
            "request_id": headers.get("x-request-id"),
        }
    return predictions


def markdown_report(summary: dict) -> str:
    lines = [
        "# AI evaluation report",
        "",
        "Synthetic/plumbing only: " + str(summary["synthetic"]),
        "",
        "| Metric | Result |",
        "|---|---|",
    ]
    for name in (
        "cases",
        "labelled_food_cases",
        "failures",
        "precision",
        "recall",
        "count_errors",
        "unit_errors",
        "interpretation_accuracy",
        "known_non_food_inclusions",
        "p95_ms_success",
        "known_input_tokens",
        "known_output_tokens",
        "cases_with_unknown_usage",
        "formal_dataset_complete",
    ):
        lines.append(f"| {name} | {summary[name]} |")
    lines += [
        "",
        "Cost is unknown until school pricing/quota terms are supplied.",
        "Missing labels, synthetic data or fake providers cannot establish formal accuracy.",
        "See the JSON report for per-case errors and confidence calibration.",
        "",
    ]
    return "\n".join(lines)
