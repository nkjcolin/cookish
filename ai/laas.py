"""Manual script for testing the school's image and audio model APIs.

Setup (from the repository root): cd ai && uv sync
Run: uv run python laas.py
Edit main() to choose your own image, prompt file, inline prompt or audio file.
list_models() calls GET /v1/models using only the base URL and API key; no model
setting is required. It preserves school-specific pricing/capability metadata.
Use show_details=True on a single-image/audio helper to print response usage and
safe billing/rate-limit headers. Missing usage or prices are unknown, not zero.

Required settings in ai/.env (ignored by Git), or exported in your environment:
    SOCLAAS_BASE_URL=https://school-api.example/v1
    SOCLAAS_API_KEY=your-school-api-key
    SOCLAAS_MODEL=your-school-model-name
Use the API base URL, not the full /chat/completions endpoint.

For audio transcription, set SOCLAAS_AUDIO_MODEL to the school's speech-to-text
model ID, or pass model= directly to transcribe_audio(). SOCLAAS_MODEL is only
needed for the image/receipt helpers; it is not an audio-model fallback.
With a base URL ending in /v1, audio uploads go to POST /v1/audio/transcriptions.

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


def list_models(*, timeout: float = 30) -> dict:
    """Return the full school model catalogue, including any pricing metadata.

    With SOCLAAS_BASE_URL ending in /v1 this sends GET /v1/models. Print the
    returned dictionary as JSON in main(); school-specific `soclaas` fields are
    retained rather than reducing each entry to just a model ID.
    """
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be a positive, finite number of seconds.")
    base_url = os.environ.get("SOCLAAS_BASE_URL", "").strip()
    api_key = os.environ.get("SOCLAAS_API_KEY", "").strip()
    if not base_url or not api_key:
        raise RuntimeError("Set SOCLAAS_BASE_URL and SOCLAAS_API_KEY in ai/.env/environment.")
    with OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0) as client:
        result = client.models.list().model_dump(mode="json")
    if not isinstance(result.get("data"), list):
        raise RuntimeError("The school API returned an unusable model list.")
    return result


def _print_call_details(raw_response, model: str) -> None:
    """Show usage without printing credentials, the prompt, image or audio bytes."""
    body = raw_response.http_response.json()
    headers = {
        name: value
        for name, value in raw_response.headers.items()
        if any(
            part in name.lower()
            for part in ("cost", "price", "usage", "token", "ratelimit", "request-id")
        )
    }
    details = {
        "endpoint": raw_response.http_request.url.path,
        "requested_model": model,
        "response_model": body.get("model"),
        "usage": body.get("usage"),
        "cost": body.get("cost"),
        "pricing": body.get("pricing"),
        "soclaas": body.get("soclaas"),
        "duration": body.get("duration"),
        "response_headers": headers,
    }
    print("API call details:")
    print(json.dumps(details, indent=2, ensure_ascii=False))


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
    show_details: bool = False,
) -> str:
    """Test an image using any prompt file in app/prompts, without a fixed output schema."""
    return ask_image(
        image_path, load_prompt(prompt_name), model=model, timeout=timeout,
        show_details=show_details,
    )


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
    show_details: bool = False,
) -> str:
    """Ask the school model about your image; return its answer as plain text.

    Example: ask_image("dataset/grocery/photo.jpg", "List the visible groceries.")
    Credentials come from ai/.env or the existing process environment. No Docker,
    receipt instructions, output schema, file saving or API cleanup is involved.
    Set show_details=True to print the model, returned usage and billing headers.
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
        create = (
            client.chat.completions.with_raw_response.create
            if show_details else client.chat.completions.create
        )
        response = create(
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
        if show_details:
            _print_call_details(response, selected_model)
            response = response.parse()
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


def transcribe_audio(
    audio_path: str | Path,
    *,
    model: str | None = None,
    language: str | None = "en",
    prompt: str | None = None,
    timeout: float = 180,
    show_details: bool = False,
) -> str:
    """Upload audio to the school transcription API and return its text.

    Edit the audio block in main() to test your own file/model. The optional
    prompt supplies transcription context, not ingredient-parsing instructions.
    This helper does not call /ai/parse-items or save/modify the transcript.
    Set show_details=True to inspect usage and any billing headers. Some audio
    providers return only text, so usage and duration will remain unknown.
    """
    audio_path = Path(audio_path).expanduser()
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")
    if audio_path.stat().st_size == 0:
        raise ValueError("Provide a nonempty audio file.")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be a positive, finite number of seconds.")

    base_url = os.environ.get("SOCLAAS_BASE_URL", "").strip()
    api_key = os.environ.get("SOCLAAS_API_KEY", "").strip()
    selected_model = (
        model if model is not None else os.environ.get("SOCLAAS_AUDIO_MODEL", "")
    ).strip()
    missing = [
        name
        for name, value in (
            ("SOCLAAS_BASE_URL", base_url),
            ("SOCLAAS_API_KEY", api_key),
            ("SOCLAAS_AUDIO_MODEL (or the model parameter)", selected_model),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing school API settings in ai/.env/environment: " + ", ".join(missing)
        )

    options = {}
    if language:
        options["language"] = language
    if prompt:
        options["prompt"] = prompt
    with (
        OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0) as client,
        audio_path.open("rb") as audio_file,
    ):
        create = (
            client.audio.transcriptions.with_raw_response.create
            if show_details else client.audio.transcriptions.create
        )
        response = create(
            model=selected_model,
            file=audio_file,
            response_format="json",
            **options,
        )
        if show_details:
            _print_call_details(response, selected_model)
            response = response.parse()
    transcript = response.text
    if not isinstance(transcript, str) or not transcript.strip():
        raise RuntimeError("The model returned an empty transcription.")
    return transcript


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
    # print(ask_image_with_prompt_file(image_path, prompt_name, show_details=True))

    # 3. IMAGE + YOUR OWN INLINE PROMPT
    custom_prompt = """
                    Describe this image and list the visible food items.
                    """

    # print(ask_image(image_path, custom_prompt))

    # 4. AUDIO -> TRANSCRIPT (POST /v1/audio/transcriptions)
    # Set SOCLAAS_AUDIO_MODEL in ai/.env, or add model="your-speech-model" below.
    # Comment out the enabled image test above before enabling this test.
    audio_path = script_dir / "dataset/audio/ingredients.wav"
    print(transcribe_audio(audio_path, show_details=True))

    # 5. LIST MODELS + SCHOOL PRICING (GET /v1/models)
    # Comment out the audio call above to run only this read-only catalogue request.
    # print(json.dumps(list_models(), indent=2, ensure_ascii=False))

    # To inspect usage on a POST, add show_details=True to the call you enable:
    # print(ask_image_with_prompt_file(image_path, prompt_name, show_details=True))
    # print(transcribe_audio(audio_path, show_details=True))


if __name__ == "__main__":
    main()
