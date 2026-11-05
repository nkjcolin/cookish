"""Harness tests use temporary copies of known development data, never reserved cases."""

import copy
import json
import shutil

import pytest
import yaml

from evaluation import held_out as runner
from evaluation.run import SUITE, InputError, run_suite, source_provenance


@pytest.fixture
def rehearsal(tmp_path, monkeypatch):
    # Test a stable source fingerprint without declaring this working tree frozen.
    source = {**source_provenance(), "git_head": "test-only", "working_tree_dirty": False}
    monkeypatch.setattr(runner, "source_provenance", lambda: copy.deepcopy(source))
    fixtures = tmp_path / "fixtures.yaml"
    cases = tmp_path / "development-copies"
    cases.mkdir()
    shutil.copyfile(SUITE / "fixtures.yaml", fixtures)
    for name in ("cook-01-cold-start.yaml", "shop-01-empty-pantry.yaml"):
        shutil.copyfile(SUITE / "development" / name, cases / name)
    freeze = tmp_path / "rehearsal-freeze.json"
    runner.create_freeze(freeze, "rehearsal")
    return dict(
        freeze_path=freeze,
        fixtures_path=fixtures,
        cases_dir=cases,
        output_dir=tmp_path / "attempt",
        mode="rehearse",
    ), source


def args(options):
    return [
        options["mode"],
        "--freeze",
        str(options["freeze_path"]),
        "--fixtures",
        str(options["fixtures_path"]),
        "--cases-dir",
        str(options["cases_dir"]),
        "--output-dir",
        str(options["output_dir"]),
    ]


def rewrite_case(options, **changes):
    path = options["cases_dir"] / "cook-01-cold-start.yaml"
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    value.update(changes)
    path.write_text(yaml.safe_dump(value), encoding="utf-8")


def test_rehearsal_preserves_inputs_and_labels_all_results_as_development_evidence(
    rehearsal, capsys
):
    options, _ = rehearsal
    assert runner.main(args(options)) == 0
    report = json.loads((options["output_dir"] / "result.json").read_text(encoding="utf-8"))
    assert report["split"] == "rehearsal"
    assert report["valid_frozen_source"]
    assert not report["first_held_out_attempt"]
    assert report["summary"]["scenarios"] == report["summary"]["passed"] == 2
    assert report["summary"]["held_out_executed"] == 0
    assert set(report["summary"]["modes"]) == {"cook", "shop"}
    assert report["inputs"]["fixtures"] == runner.snapshot(options["fixtures_path"])
    assert report["inputs"]["scenarios"]["cook-01-cold-start.yaml"] == runner.snapshot(
        options["cases_dir"] / "cook-01-cold-start.yaml"
    )
    assert (options["output_dir"] / "attempt.json").exists()
    assert not runner.Path(str(options["freeze_path"]) + ".first-attempt.json").exists()
    assert "held-out executed: 0" in capsys.readouterr().out


def test_failed_expectations_are_preserved_and_exit_one(rehearsal):
    options, _ = rehearsal
    rewrite_case(options, expect={"result": True, "selected_any": ["tofu-rice"]})
    assert runner.main(args(options)) == 1
    report = json.loads((options["output_dir"] / "result.json").read_text(encoding="utf-8"))
    assert report["summary"]["passed"] == 1
    assert report["summary"]["failures_by_kind"] == {"expectation": 1}
    assert report["results"][0]["steps"][0]["failures"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("git_head", "changed"),
        ("working_tree_dirty", True),
        ("working_tree_dirty", None),
        ("runtime", {}),
        ("source_sha256", {}),
        ("config", {}),
    ],
)
def test_changed_or_unverifiable_freeze_stops_before_reading_cases(
    rehearsal, monkeypatch, field, value
):
    options, source = rehearsal
    source[field] = value
    monkeypatch.setattr(
        runner, "prepare_inputs", lambda *a: pytest.fail("must reject before input read")
    )
    assert runner.main(args(options)) == 2
    assert not options["output_dir"].exists()


def test_manifests_and_result_directories_cannot_be_overwritten(rehearsal):
    options, _ = rehearsal
    before = options["freeze_path"].read_bytes()
    with pytest.raises(FileExistsError):
        runner.create_freeze(options["freeze_path"], "rehearsal")
    assert options["freeze_path"].read_bytes() == before
    assert runner.main(args(options)) == 0
    result = options["output_dir"] / "result.json"
    before = result.read_bytes()
    assert runner.main(args(options)) == 2
    assert result.read_bytes() == before


def test_first_attempt_reservation_cannot_be_reused_for_another_output(rehearsal):
    options, _ = rehearsal
    frozen = runner.verify_freeze(options["freeze_path"], "rehearse")
    runner.reserve_first_attempt(options["freeze_path"], frozen, options["output_dir"])
    marker = runner.Path(str(options["freeze_path"]) + ".first-attempt.json")
    before = marker.read_bytes()
    with pytest.raises(FileExistsError):
        runner.reserve_first_attempt(
            options["freeze_path"], frozen, options["output_dir"] / "retry"
        )
    assert marker.read_bytes() == before


def test_rehearsal_freeze_cannot_be_used_for_actual_evaluation(rehearsal, monkeypatch):
    options, _ = rehearsal
    monkeypatch.setattr(
        runner, "prepare_inputs", lambda *a: pytest.fail("must reject before input read")
    )
    with pytest.raises(InputError, match="evaluation freeze"):
        runner.evaluate(**{**options, "mode": "run"}, independent_author="Test only")


def test_actual_run_rejects_dev_copies_and_requires_author_and_unused_manifest(rehearsal, tmp_path):
    options, _ = rehearsal
    freeze = tmp_path / "evaluation-format-test-only.json"
    frozen = runner.create_freeze(freeze, "evaluation")
    options.update(freeze_path=freeze, mode="run")
    with pytest.raises(InputError, match="author"):
        runner.evaluate(**options)
    # No development case is ever executed as held-out, even with an evaluation manifest.
    with pytest.raises(InputError):
        runner.evaluate(**options, independent_author="Test only")
    assert not options["output_dir"].exists()
    runner.reserve_first_attempt(freeze, frozen, tmp_path / "previous")
    with pytest.raises(InputError, match="first attempt"):
        runner.evaluate(**options, independent_author="Test only")


def test_held_out_input_schema_and_count_are_checked_without_executing_cases(rehearsal):
    options, _ = rehearsal
    for path in options["cases_dir"].glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        # Schema-only test copies, NOT new independently authored scenarios.
        data.update(id=data["id"].replace("DEV-", "HELD-"), split="held-out")
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(InputError, match="30 cases"):
        runner.prepare_inputs(options["fixtures_path"], options["cases_dir"], "run", 30)
    _, _, cases = runner.prepare_inputs(options["fixtures_path"], options["cases_dir"], "run", 2)
    assert {case.mode for case in cases} == {"cook", "shop"}
    with pytest.raises(InputError):
        runner.prepare_inputs(options["fixtures_path"], options["cases_dir"], "rehearse", 30)
    with pytest.raises(InputError):
        run_suite(options["fixtures_path"], options["cases_dir"], selected=["HELD-C01"])


@pytest.mark.parametrize(
    "malformation", ["duplicate", "bad_yaml", "unknown_field", "wrong_mode", "empty"]
)
def test_invalid_inputs_do_not_run_or_create_a_report(rehearsal, monkeypatch, malformation):
    options, _ = rehearsal
    path = options["cases_dir"] / "cook-01-cold-start.yaml"
    if malformation == "duplicate":
        shutil.copyfile(path, options["cases_dir"] / "duplicate.yaml")
    elif malformation == "bad_yaml":
        path.write_text("id: [unfinished", encoding="utf-8")
    elif malformation == "unknown_field":
        rewrite_case(options, unsupported_assertion=True)
    elif malformation == "wrong_mode":
        rewrite_case(options, id="DEV-S99")
    else:
        for path in options["cases_dir"].glob("*.yaml"):
            path.unlink()
    monkeypatch.setattr(
        runner, "run_scenario", lambda *a: pytest.fail("invalid cases must not execute")
    )
    assert runner.main(args(options)) == 2
    assert not options["output_dir"].exists()


def test_source_change_during_run_invalidates_and_preserves_the_result(rehearsal, monkeypatch):
    options, source = rehearsal
    original = runner.run_scenario

    def changed(case, world):
        result = original(case, world)
        source["git_head"] = "changed-during-run"
        return result

    monkeypatch.setattr(runner, "run_scenario", changed)
    assert runner.main(args(options)) == 2
    report = json.loads((options["output_dir"] / "result.json").read_text(encoding="utf-8"))
    assert not report["valid_frozen_source"]
    assert not report["first_held_out_attempt"]
    assert len(report["results"]) == 2


def test_interrupted_run_preserves_attempt_and_completed_results(rehearsal, monkeypatch):
    options, _ = rehearsal
    original = runner.run_scenario

    def interrupted(case, world):
        if case.mode == "shop":
            raise KeyboardInterrupt("test-only interruption")
        return original(case, world)

    monkeypatch.setattr(runner, "run_scenario", interrupted)
    with pytest.raises(KeyboardInterrupt):
        runner.evaluate(**options)
    partial = json.loads((options["output_dir"] / "interrupted.json").read_text(encoding="utf-8"))
    assert len(partial["completed_results"]) == 1
    assert (options["output_dir"] / "attempt.json").exists()
    assert not (options["output_dir"] / "result.json").exists()
    assert runner.main(args(options)) == 2


def test_regression_references_original_hash_and_rejects_changed_inputs(rehearsal, tmp_path):
    options, _ = rehearsal
    captured, _, _ = runner.prepare_inputs(
        options["fixtures_path"], options["cases_dir"], "rehearse", 30
    )
    original = tmp_path / "test-only-result-metadata.json"
    # A format fixture only: no held-out evaluation was performed to produce it.
    runner.write_new(original, {"split": "held-out", "inputs": captured})
    link = runner.original_result_link(original, captured)
    assert link["sha256"] == runner.snapshot(original)["sha256"]
    changed = copy.deepcopy(captured)
    changed["fixtures"]["sha256"] = "different"
    with pytest.raises(InputError, match="inputs differ"):
        runner.original_result_link(original, changed)
    with pytest.raises(InputError, match="requires the original"):
        runner.original_result_link(None, captured)
    rehearsal_result = tmp_path / "test-only-rehearsal.json"
    runner.write_new(rehearsal_result, {"split": "rehearsal", "inputs": captured})
    with pytest.raises(InputError, match="original result"):
        runner.original_result_link(rehearsal_result, captured)
