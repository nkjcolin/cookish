"""Frozen offline evaluation, with a separate development-only rehearsal mode.

Never supply reserved cases to rehearsal. The development CLI remains DEV-only.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import yaml

from app import clock
from evaluation.run import (
    InputError,
    UniqueLoader,
    make_world,
    run_scenario,
    source_provenance,
    summarize,
    validate_references,
)
from evaluation.schema import Fixtures, HeldOutScenario, Scenario, StrictModel


class Freeze(StrictModel):
    version: Literal[1] = 1
    freeze_id: UUID
    purpose: Literal["rehearsal", "evaluation"]
    created_at: datetime
    expected_cases: Literal[30] = 30
    acceptance: Literal["all scenarios and steps pass with no hard-constraint violations"] = (
        "all scenarios and steps pass with no hard-constraint violations"
    )
    source: dict


def write_new(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def clean_source():
    source = source_provenance()
    if source["working_tree_dirty"] is not False or not source["git_head"]:
        raise InputError("a verifiably clean Git checkout is required")
    return source


def create_freeze(output: Path, purpose: str):
    frozen = Freeze(
        freeze_id=uuid4(), purpose=purpose, created_at=clock.now(), source=clean_source()
    )
    write_new(output, frozen.model_dump(mode="json"))
    return frozen


def verify_freeze(path: Path, mode: str):
    frozen = Freeze.model_validate_json(path.read_text(encoding="utf-8"))
    required = "rehearsal" if mode == "rehearse" else "evaluation"
    if frozen.purpose != required:
        raise InputError(f"{mode} requires a {required} freeze manifest")
    if frozen.source != clean_source():
        raise InputError("source, commit, configuration or runtime differs from the freeze")
    return frozen


def snapshot(path: Path):
    text = path.read_text(encoding="utf-8")  # Normalize CRLF exactly as development hashes do.
    return {"text": text, "sha256": hashlib.sha256(text.encode()).hexdigest()}


def parse(snapshot_value, model):
    try:
        return model.model_validate(yaml.load(snapshot_value["text"], UniqueLoader))
    except (ValueError, TypeError, yaml.YAMLError) as exc:
        raise InputError(str(exc)) from exc


def prepare_inputs(fixtures_path: Path, cases_dir: Path, mode: str, expected_cases: int):
    captured = {
        "fixtures": snapshot(fixtures_path),
        "scenarios": {path.name: snapshot(path) for path in sorted(cases_dir.glob("*.yaml"))},
    }
    if not captured["scenarios"]:
        raise InputError("no scenario YAML files found")
    model = Scenario if mode == "rehearse" else HeldOutScenario
    world = make_world(parse(captured["fixtures"], Fixtures))
    cases = [parse(value, model) for value in captured["scenarios"].values()]
    ids = [case.id for case in cases]
    if len(set(ids)) != len(ids):
        raise InputError("duplicate scenario IDs")
    if mode != "rehearse":
        if len(cases) != expected_cases or {case.mode for case in cases} != {"cook", "shop"}:
            raise InputError(
                f"held-out suite must contain {expected_cases} cases covering Cook and Shop"
            )
    for case in cases:
        validate_references(case, world)
    return captured, world, cases


def input_hashes(captured):
    return {
        "fixtures": captured["fixtures"]["sha256"],
        "scenarios": {name: value["sha256"] for name, value in captured["scenarios"].items()},
    }


def reserve_first_attempt(freeze_path: Path, frozen: Freeze, output_dir: Path):
    write_new(
        Path(str(freeze_path) + ".first-attempt.json"),
        {
            "freeze_id": str(frozen.freeze_id),
            "output_dir": str(output_dir.resolve()),
            "started_at": clock.now().isoformat(),
        },
    )


def original_result_link(original: Path | None, captured):
    if original is None:
        raise InputError("regression requires the original result.json")
    previous = json.loads(original.read_text(encoding="utf-8"))
    if previous.get("split") not in {"held-out", "held-out-regression"}:
        raise InputError("original result must be a held-out run or its regression")
    if input_hashes(previous["inputs"]) != input_hashes(captured):
        raise InputError("regression inputs differ from the original; preserve the original suite")
    return {"path": str(original.resolve()), "sha256": snapshot(original)["sha256"]}


def evaluate(
    *,
    freeze_path: Path,
    fixtures_path: Path,
    cases_dir: Path,
    output_dir: Path,
    mode: str,
    independent_author: str | None = None,
    original: Path | None = None,
):
    frozen = verify_freeze(freeze_path, mode)
    if mode == "run" and not (independent_author and independent_author.strip()):
        raise InputError("record the independent scenario author's name before the first run")
    if mode == "run" and Path(str(freeze_path) + ".first-attempt.json").exists():
        raise InputError("this freeze already has a first attempt; preserve it and use regression")
    captured, world, cases = prepare_inputs(fixtures_path, cases_dir, mode, frozen.expected_cases)
    original_link = None
    if mode == "regression":
        original_link = original_result_link(original, captured)
    verify_freeze(freeze_path, mode)  # Check again after reading inputs, before any engine calls.
    output_dir.mkdir(parents=True, exist_ok=False)
    if mode == "run":
        # A second first-run command using this manifest cannot silently replace
        # failed evidence by choosing a fresh output directory.
        reserve_first_attempt(freeze_path, frozen, output_dir)
    split = {"rehearse": "rehearsal", "run": "held-out", "regression": "held-out-regression"}[mode]
    attempt = {
        "version": 1,
        "split": split,
        "scope": "Offline synthetic fixtures; not database, deployed, load or user-study evidence.",
        "started_at": clock.now().isoformat(),
        "freeze": frozen.model_dump(mode="json"),
        "independent_author": independent_author,
        "original_result": original_link,
        "as_of": world.fixtures.as_of.isoformat(),
        "inputs": captured,
    }
    write_new(output_dir / "attempt.json", attempt)
    results = []
    try:
        for case in cases:
            results.append(run_scenario(case, world))
        after = source_provenance()
        valid = after == frozen.source
        report = {
            **attempt,
            "finished_at": clock.now().isoformat(),
            "valid_frozen_source": valid,
            "source_after": after,
            "summary": summarize(
                results, held_out_executed=len(cases) if mode != "rehearse" else 0
            ),
            "first_held_out_attempt": mode == "run" and valid,
            "results": results,
        }
        write_new(output_dir / "result.json", report)
    except BaseException as exc:
        # Preserve a partial attempt on interruption, rather than inviting a
        # replacement run to masquerade as untouched evidence.
        write_new(
            output_dir / "interrupted.json",
            {
                "error": type(exc).__name__,
                "message": str(exc),
                "completed_results": results,
            },
        )
        raise
    if not valid:
        raise InputError("source changed during evaluation; recorded result is invalid")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze", help="Record source before accepting unseen inputs")
    freeze.add_argument("--purpose", choices=("rehearsal", "evaluation"), required=True)
    freeze.add_argument("--output", type=Path, required=True)
    for name in ("rehearse", "run", "regression"):
        command = commands.add_parser(name)
        command.add_argument("--freeze", type=Path, required=True)
        command.add_argument("--fixtures", type=Path, required=True)
        command.add_argument("--cases-dir", type=Path, required=True)
        command.add_argument("--output-dir", type=Path, required=True)
        if name == "run":
            command.add_argument("--independent-author", required=True)
        if name == "regression":
            command.add_argument("--original", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "freeze":
            create_freeze(args.output, args.purpose)
            print(f"Recorded {args.purpose} freeze: {args.output}; no scenarios executed")
            return 0
        report = evaluate(
            freeze_path=args.freeze,
            fixtures_path=args.fixtures,
            cases_dir=args.cases_dir,
            output_dir=args.output_dir,
            mode=args.command,
            independent_author=getattr(args, "independent_author", None),
            original=getattr(args, "original", None),
        )
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Invalid evaluation input or evidence destination: {exc}", file=sys.stderr)
        return 2
    summary = report["summary"]
    print(
        f"{report['split']}: {summary['passed']}/{summary['scenarios']} scenarios; "
        f"held-out executed: {summary['held_out_executed']}; "
        f"first held-out attempt: {report['first_held_out_attempt']}"
    )
    return 0 if summary["passed"] == summary["scenarios"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
