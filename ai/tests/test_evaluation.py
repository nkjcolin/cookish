import json

import pytest

from eval.runner import evaluate, load_manifest, markdown_report


def case(expected, **extra):
    return {"id": "one", "kind": "receipt", "image": "not-read.jpeg", "expected": expected, **extra}


def prediction(items, **extra):
    return {
        "one": {
            "status": 200,
            "body": {"items": items},
            "latency_ms": 150,
            "provider": "soclaas",
            "model": "test",
            **extra,
        }
    }


def score(expected, actual, **extra):
    return evaluate({"synthetic": False, "cases": [case(expected, **extra)]}, prediction(actual))


def test_metrics_include_false_positives_false_negatives_and_quantity_errors():
    result = score(
        [{"display_name": "Egg", "count": 2, "unit": "pcs"}, {"display_name": "Milk"}],
        [{"display_name": "Egg", "count": 3, "unit": "pack"}, {"display_name": "Soap"}],
        non_food_names=["Soap"],
    )
    assert result["precision"] == result["recall"] == 0.5
    assert result["count_errors"] == result["unit_errors"] == 1
    assert result["known_non_food_inclusions"] == 1


def test_alias_matching_is_one_to_one_not_greedy():
    result = score(
        [
            {"display_name": "Food A", "aliases": ["shared"]},
            {"display_name": "Food B", "aliases": ["shared"]},
        ],
        [{"display_name": "shared"}, {"display_name": "Food A"}],
    )
    assert result["true_positives"] == 2
    assert result["precision"] == result["recall"] == 1


def test_duplicate_predictions_are_not_counted_twice():
    result = score([{"display_name": "Egg"}], [{"display_name": "Egg"}] * 2)
    assert result["true_positives"] == result["false_positives"] == 1


def test_unlabelled_does_not_mean_empty_ground_truth():
    result = score(None, [{"display_name": "Egg"}])
    assert result["labelled_food_cases"] == 0
    assert result["precision"] is None and result["recall"] is None
    assert result["formal_dataset_complete"] is False


def test_unavailable_prediction_counts_as_false_negative():
    result = evaluate({"synthetic": False, "cases": [case([{"display_name": "Egg"}])]}, {})
    assert result["failures"] == result["false_negatives"] == 1
    assert result["recall"] == 0


def test_confidence_is_measured_not_calibrated_by_invention():
    result = score(
        [{"display_name": "Egg"}],
        [
            {"display_name": "Egg", "confidence": 0.9},
            {"display_name": "Soap", "confidence": 0.9},
        ],
    )
    assert result["confidence_brier_score"] == pytest.approx(0.41)
    assert result["confidence_bins"][-1]["accuracy"] == 0.5
    assert result["cost"] is None and result["cases_with_unknown_usage"] == 1


def test_token_usage_zero_is_known_not_missing():
    result = evaluate(
        {"synthetic": True, "cases": [case([])]}, prediction([], input_tokens=0, output_tokens=0)
    )
    assert result["cases_with_unknown_usage"] == 0
    assert result["formal_dataset_complete"] is False
    assert "Synthetic/plumbing only: True" in markdown_report(result)


@pytest.mark.parametrize(
    "status,cost,subtotal,expected_status",
    [
        ("estimated", "0.0001872", "0.0001872", "estimated"),
        ("partial", None, "0.0001872", "partial"),
        ("fake", "0", "0", "unknown"),
        ("estimated", "NaN", None, "unknown"),
    ],
)
def test_estimated_cost_is_separate_from_actual_billing(status, cost, subtotal, expected_status):
    result = evaluate(
        {"synthetic": True, "cases": [case([])]},
        prediction(
            [],
            cost_status=status,
            estimated_cost=cost,
            known_estimated_cost=subtotal,
            cost_unit="provider_dollars",
        ),
    )
    assert result["cost"] is None
    assert result["cost_status"] == expected_status
    assert result["estimated_cost"] == (cost if expected_status == "estimated" else None)
    assert result["known_estimated_cost"] == (
        subtotal if expected_status in {"estimated", "partial"} else None
    )


def test_confidence_bin_boundaries_are_not_double_counted():
    result = score(
        [{"display_name": "Egg"}],
        [
            {"display_name": "Egg", "confidence": 0.6},
            {"display_name": "Soap", "confidence": 1.0},
        ],
    )
    assert sum(bucket["n"] for bucket in result["confidence_bins"]) == 2


def test_interpretation_is_scored_separately():
    result = evaluate(
        {
            "synthetic": True,
            "cases": [
                {
                    "id": "one",
                    "kind": "interpret",
                    "text": "quicker",
                    "expected_adjust": {"tags": ["quicker"]},
                }
            ],
        },
        {
            "one": {
                "status": 200,
                "body": {"adjust": {"tags": ["quicker"], "people": None, "max_minutes": None}},
            }
        },
    )
    assert result["interpretation_accuracy"] == 1
    assert result["labelled_food_cases"] == 0


def test_formal_coverage_requires_real_provider_and_full_labels():
    cases = []
    predictions = {}
    for kind, size in [("receipt", 30), ("photo", 20), ("voice", 20)]:
        for number in range(size):
            identifier = f"{kind}-{number}"
            cases.append({"id": identifier, "kind": kind, "expected": []})
            predictions[identifier] = {"status": 200, "provider": "fake", "body": {"items": []}}
    result = evaluate({"synthetic": False, "cases": cases}, predictions)
    assert result["formal_dataset_complete"] is False
    for entry in predictions.values():
        entry["provider"] = "soclaas"
    assert evaluate({"synthetic": False, "cases": cases}, predictions)["formal_dataset_complete"]


def test_manifest_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"synthetic": True, "cases": [case([]), case([])]}))
    with pytest.raises(ValueError, match="unique"):
        load_manifest(path)


def test_cli_can_rescore_only_one_selected_case(tmp_path, monkeypatch):
    from scripts import evaluate as cli

    manifest = tmp_path / "manifest.json"
    predictions = tmp_path / "predictions.json"
    output = tmp_path / "report.json"
    manifest.write_text(
        json.dumps(
            {
                "synthetic": True,
                "cases": [
                    {"id": "food", "kind": "typed", "text": "food", "expected": []},
                    {
                        "id": "cooking",
                        "kind": "interpret",
                        "text": "quicker",
                        "expected_adjust": {"tags": ["quicker"]},
                    },
                ],
            }
        )
    )
    predictions.write_text(
        json.dumps(
            {
                "cooking": {
                    "status": 200,
                    "body": {"adjust": {"tags": ["quicker"]}},
                    "provider": "fake",
                }
            }
        )
    )
    monkeypatch.setattr(
        cli.sys,
        "argv",
        [
            "evaluate.py",
            str(manifest),
            "--predictions",
            str(predictions),
            "--case",
            "cooking",
            "--out",
            str(output),
        ],
    )
    assert cli.main() == 0
    summary = json.loads(output.read_text())["summary"]
    assert summary["cases"] == summary["interpretation_cases"] == 1
    assert summary["interpretation_accuracy"] == 1
