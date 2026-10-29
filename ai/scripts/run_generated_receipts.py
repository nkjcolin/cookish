"""Run receipt.md on generated receipts, saving progress without Docker or AWS.

Run from the repository root with:
    conda run -n cookish python ai/scripts/run_generated_receipts.py

Completed matching results are reused on restart. Each unfinished image gets one
request, without automatic provider retries or the application's non-food filter.
Structured receipt quantity checks against copied raw text, normalization and
defaults are shared with the API.
"""

import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from openai import OpenAI  # noqa: E402

import laas  # noqa: E402

IMAGE_DIR = AI_ROOT / "dataset/receipt/generated"
OUTPUT_DIR = AI_ROOT / "output/generated"
TIMEOUT_SECONDS = 180


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main():
    images = sorted(
        p for p in IMAGE_DIR.iterdir() if p.is_file() and p.suffix.lower() in laas.IMAGE_EXTENSIONS
    )
    if not images:
        raise RuntimeError("No generated receipt images found")
    prompt = laas.load_receipt_prompt()
    model = (os.environ.get("SOCLAAS_IMAGE_MODEL") or os.environ.get("SOCLAAS_MODEL", "")).strip()
    base_url = os.environ.get("SOCLAAS_BASE_URL", "").strip()
    api_key = os.environ.get("SOCLAAS_API_KEY", "").strip()
    if not all((model, base_url, api_key)):
        raise RuntimeError(
            "School base URL, model and API key must be configured in ai/.env/environment"
        )
    fingerprint = {
        "model": model,
        "quantity_processing": "extracted-factors-original-units-raw-text-v4",
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "image_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in images},
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state_path = OUTPUT_DIR / "_run.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state["inputs"] != fingerprint:
            raise RuntimeError(
                "Existing run has different images, prompt, model or quantity processing; "
                "preserve its outputs before starting a new run"
            )
    else:
        if list(OUTPUT_DIR.glob("*.json")):
            raise RuntimeError("Existing outputs have no run metadata; refusing to overwrite them")
        state = {
            "started_at": datetime.now(UTC).isoformat(),
            "inputs": fingerprint,
            "prompt": "app/prompts/receipt.md",
            "timeout_seconds": TIMEOUT_SECONDS,
            "automatic_retries": 0,
            "non_food_filtering": False,
            "quantity_processing": {
                "count": "total amount in unit, extracted factors multiplied in Python",
                "normalization": (
                    "unit spellings, restore source scale, "
                    "reconcile explicit raw-text sizes/counts; "
                    "conflicting amounts to null"
                ),
                "defaults": "missing unmeasured purchase count to 1; null unit to pcs",
            },
            "images": {},
        }
    results = {}
    for image in images:
        record = state["images"].get(image.name, {})
        output = OUTPUT_DIR / (image.name + ".json")
        if record.get("status") == "success":
            draft = laas.DraftResult.model_validate_json(output.read_text())
            results[image.name] = draft.model_dump(mode="json")
    state["status"] = "running"
    write_json(state_path, state)
    print(
        f"Model: {model}; images: {len(images)}; already saved: {len(results)}; "
        f"timeout: {TIMEOUT_SECONDS}s; retries: 0",
        flush=True,
    )
    stopped = False
    with OpenAI(
        base_url=base_url, api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=0
    ) as client:
        for index, image in enumerate(images, 1):
            if image.name in results:
                continue
            output = OUTPUT_DIR / (image.name + ".json")
            if output.exists():
                raise FileExistsError(f"Refusing to overwrite untracked result: {output.name}")
            print(f"START {index}/{len(images)} {image.name}", flush=True)
            started = time.monotonic()
            record = {"status": "processing", "started_at": datetime.now(UTC).isoformat()}
            state["images"][image.name] = record
            write_json(state_path, state)
            try:
                draft = laas.extract_receipt_with_prompt(image, client, model, prompt)
                parsed = draft.model_dump(mode="json")
                write_json(output, parsed)
                results[image.name] = parsed
                record.update(status="success", output=output.name, items=len(draft.items))
                print(
                    f"SAVED {image.name}: {len(draft.items)} items in "
                    f"{time.monotonic() - started:.1f}s ({len(results)}/{len(images)})",
                    flush=True,
                )
            except Exception as exc:
                # Do not print or persist provider bodies, request payloads or credentials.
                status_code = getattr(exc, "status_code", None)
                record.update(
                    status="failed", error_type=type(exc).__name__, http_status=status_code
                )
                print(
                    f"FAILED {image.name}: {type(exc).__name__}, HTTP {status_code}, "
                    f"{time.monotonic() - started:.1f}s",
                    flush=True,
                )
                if status_code in (401, 403, 404, 429):
                    stopped = True
            record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            write_json(OUTPUT_DIR / "results.json", results)
            write_json(state_path, state)
            if stopped:
                print(
                    "Stopped requests after an authentication, endpoint/model or quota error.",
                    flush=True,
                )
                break
    failed = [name for name, record in state["images"].items() if record["status"] == "failed"]
    state["status"] = "complete" if len(results) == len(images) else "incomplete"
    state["finished_at"] = datetime.now(UTC).isoformat()
    state["successful_images"] = len(results)
    state["failed_images"] = failed
    state["unprocessed_images"] = [p.name for p in images if p.name not in state["images"]]
    write_json(state_path, state)
    print(
        f"FINISHED: {len(results)}/{len(images)} saved, {len(failed)} failed, "
        f"{len(state['unprocessed_images'])} unprocessed. {OUTPUT_DIR}",
        flush=True,
    )
    return 0 if state["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
