"""Manual script for testing the school's image-capable model API.

Setup (from the repository root): cd ai && uv sync
Run: uv run python laas.py
Edit main() to choose your own image, prompt file or inline prompt.

Required settings in ai/.env (ignored by Git), or exported in your environment:
    SOCLAAS_BASE_URL=https://school-api.example/v1
    SOCLAAS_API_KEY=your-school-api-key
    SOCLAAS_MODEL=your-school-model-name
Use the API base URL, not the full /chat/completions endpoint.

Optional: SOCLAAS_IMAGE_MODEL overrides the default model for the single-image
helpers. Their model= keyword takes priority over both model environment settings.
The receipt batch helpers require SOCLAAS_MODEL. Existing environment variables
take precedence over ai/.env, which is resolved relative to this file.
AI_PROVIDER is not used here: this script calls the school API directly.
Local images in eval/data/receipt/ and eval/data/grocery/, and saved output/,
are ignored by Git. Shared image fixtures are published under dataset/ and are
used by the default test paths below.
"""

import base64
import json
import math
import mimetypes
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from app.receipts import finalize_receipt_quantities
from app.quantities import ExtractionResult, resolve_quantities
from app.schemas import DraftResult

script_dir = Path(__file__).resolve().parent
load_dotenv(script_dir / ".env")
PROMPT_DIR = script_dir / "app/prompts"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def load_prompt(prompt_name: str | Path) -> str:
    """Load a prompt from app/prompts by filename or stem, e.g. 'photo.md' or 'photo'."""
    if not str(prompt_name).strip():
        raise ValueError("Choose a prompt filename, such as photo.md.")
    name = Path(prompt_name)
    if not name.suffix:
        name = name.with_suffix(".md")
    folder = PROMPT_DIR.resolve()
    path = (folder / name).resolve()
    if not path.is_relative_to(folder):
        raise ValueError("Choose a prompt inside ai/app/prompts/.")
    if not path.is_file():
        available = ", ".join(sorted(item.name for item in folder.glob("*.md")))
        raise FileNotFoundError(f"Prompt not found: {name}. Available prompts: {available}")
    prompt = path.read_text(encoding="utf-8")
    if not prompt.strip():
        raise ValueError(f"Prompt file is empty: {name}")
    return prompt


def ask_image_with_prompt_file(
    image_path: str | Path,
    prompt_name: str | Path,
    *,
    model: str | None = None,
    timeout: float = 180,
) -> str:
    """Test an image using any prompt file in app/prompts, without a fixed output schema."""
    return ask_image(image_path, load_prompt(prompt_name), model=model, timeout=timeout)


# Function to encode the image
def encode_image(image_path: Path) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def ask_image(
    image_path: str | Path,
    prompt: str,
    *,
    model: str | None = None,
    timeout: float = 180,
) -> str:
    """Ask the school model about your image; return its answer as plain text.

    Example: ask_image("dataset/grocery/photo.jpg", "List the visible groceries.")
    Credentials come from ai/.env or the existing process environment. No Docker,
    receipt instructions, output schema, file saving or API cleanup is involved.
    """
    image_path = Path(image_path).expanduser()
    if not image_path.is_file():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    media_type = mimetypes.guess_type(image_path)[0]
    if image_path.suffix.lower() not in IMAGE_EXTENSIONS or media_type not in {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }:
        raise ValueError("Use a JPG/JPEG, PNG, WebP or GIF image; export HEIC to JPEG first.")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Provide a nonempty prompt.")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be a positive, finite number of seconds.")

    base_url = os.environ.get("SOCLAAS_BASE_URL", "").strip()
    api_key = os.environ.get("SOCLAAS_API_KEY", "").strip()
    selected_model = (
        model
        if model is not None
        else os.environ.get("SOCLAAS_IMAGE_MODEL") or os.environ.get("SOCLAAS_MODEL", "")
    ).strip()
    missing = [
        name
        for name, value in (
            ("SOCLAAS_BASE_URL", base_url),
            ("SOCLAAS_API_KEY", api_key),
            ("SOCLAAS_MODEL (or the model parameter)", selected_model),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing school API settings in ai/.env/environment: " + ", ".join(missing)
        )

    with OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0) as client:
        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{encode_image(image_path)}"
                            },
                        },
                    ],
                }
            ],
        )
    if not response.choices:
        raise RuntimeError("The model returned no answer choices.")
    choice = response.choices[0]
    if choice.message.refusal:
        raise RuntimeError("The model refused the image request.")
    if choice.finish_reason in {"length", "content_filter", "tool_calls"}:
        raise RuntimeError("The model did not complete a usable text answer.")
    answer = choice.message.content
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("The model returned an empty answer.")
    return answer


def extract_receipt(
    image_path: Path,
    client: OpenAI,
    model: str,
    prompt: str | None = None,
) -> DraftResult:
    """Extract food drafts using receipt.md, not the old name/price instructions."""
    return extract_receipt_with_prompt(
        image_path, client, model, load_receipt_prompt() if prompt is None else prompt
    )


def load_receipt_prompt(
    prompt_path: Path = script_dir / "app/prompts/receipt.md",
) -> str:
    """Read the shared receipt prompt verbatim; no catalogue is required."""
    return Path(prompt_path).read_text(encoding="utf-8")


def extract_receipt_with_prompt(
    image_path: Path,
    client: OpenAI,
    model: str,
    prompt: str,
) -> DraftResult:
    """Use the receipt prompt and the app's draft-item schema for one image."""
    media_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    response = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract the food items from this receipt."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{encode_image(image_path)}"
                        },
                    },
                ],
            },
        ],
        response_format=ExtractionResult,
    )
    message = response.choices[0].message
    if message.refusal:
        raise RuntimeError(f"The model refused to extract the receipt: {message.refusal}")
    if message.parsed is None:
        raise RuntimeError("The model did not return a structured receipt.")

    extracted = ExtractionResult.model_validate(message.parsed.model_dump())
    return finalize_receipt_quantities(resolve_quantities(extracted))


def process_receipts_with_prompt(
    receipt_dir: Path = script_dir / "dataset/receipt",
    output_path: Path = script_dir / "output/prompt.json",
) -> dict[str, DraftResult]:
    """Run receipt.md on every image and save the results together by filename."""
    receipt_dir = Path(receipt_dir)
    output_path = Path(output_path)
    images = sorted(
        path
        for path in receipt_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        raise RuntimeError(f"No supported images found in {receipt_dir}")

    prompt = load_receipt_prompt()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results = {}
    failures = []
    with OpenAI(
        base_url=os.environ["SOCLAAS_BASE_URL"],
        api_key=os.environ["SOCLAAS_API_KEY"],
        timeout=180,
        max_retries=0,
    ) as client:
        model = os.environ["SOCLAAS_MODEL"]
        for image_path in images:
            print(f"Processing {image_path.name} with receipt.md...", flush=True)
            try:
                result = extract_receipt_with_prompt(image_path, client, model, prompt)
            except (OpenAIError, ValidationError, OSError, RuntimeError) as exc:
                failures.append(image_path.name)
                print(f"Failed {image_path.name}: {exc}", file=sys.stderr, flush=True)
                continue
            results[image_path.name] = result
            # Save progress so completed results are available during a long batch.
            output_path.write_text(
                json.dumps(
                    {name: draft.model_dump(mode="json") for name, draft in results.items()},
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"Saved {len(result.items)} items for {image_path.name}", flush=True)

    if failures:
        raise RuntimeError(
            f"Saved {len(results)} of {len(images)} receipts. Failed: {', '.join(failures)}"
        )
    print(f"Saved all {len(results)} results to {output_path}", flush=True)
    return results


def process_receipts(
    receipt_dir: Path = script_dir / "dataset/receipt",
    output_dir: Path = script_dir / "output",
) -> list[Path]:
    """Use receipt.md and save one draft JSON per image, continuing after failures."""
    receipt_dir = Path(receipt_dir)
    output_dir = Path(output_dir)
    images = sorted(
        path
        for path in receipt_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        print(f"No supported images found in {receipt_dir}")
        return []

    prompt = load_receipt_prompt()
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_paths = []
    failures = []
    with OpenAI(
        base_url=os.environ["SOCLAAS_BASE_URL"],
        api_key=os.environ["SOCLAAS_API_KEY"],
        timeout=180,
        max_retries=0,
    ) as client:
        model = os.environ["SOCLAAS_MODEL"]
        for image_path in images:
            # Keep the image extension so receipt.jpg and receipt.png stay distinct.
            output_path = output_dir / f"{image_path.name}.json"
            try:
                receipt = extract_receipt(image_path, client, model, prompt)
                output_path.write_text(receipt.model_dump_json(indent=2) + "\n", encoding="utf-8")
            except (OpenAIError, ValidationError, OSError, RuntimeError) as exc:
                failures.append(image_path.name)
                print(f"Failed {image_path.name}: {exc}", file=sys.stderr)
                continue
            saved_paths.append(output_path)
            print(f"Saved {output_path}")

    if failures:
        raise RuntimeError(
            f"Saved {len(saved_paths)} of {len(images)} receipts. Failed: {', '.join(failures)}"
        )
    return saved_paths


def main() -> None:
    # Keep the call for the test you want uncommented; comment out the other calls.

    # 1. RECEIPT IMAGES + PROMPT FILE (existing function)
    # Reads app/prompts/receipt.md and every image in ai/dataset/receipt/.
    # Saves/overwrites the combined results in ai/output/prompt.json.
    # process_receipts_with_prompt()

    # 2. IMAGE + CHOOSE A FILE FROM app/prompts/
    # Change prompt_name to photo.md, receipt.md or a new prompt file you add.
    # Paths based on script_dir are relative to ai/, regardless of your terminal folder.
    # image_path = script_dir / "dataset/grocery/grocery.jpeg"
    image_path = script_dir / "dataset/grocery/grocery-table.webp"
    prompt_name = "photo.md"
    print(ask_image_with_prompt_file(image_path, prompt_name))

    # 3. IMAGE + YOUR OWN INLINE PROMPT
    custom_prompt = """
                    Describe this image and list the visible food items.
                    """

    # print(ask_image(image_path, custom_prompt))


if __name__ == "__main__":
    main()
