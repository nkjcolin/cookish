"""Send one local API request; no SDK, API key or experimental script is needed."""

import argparse
import base64
import json
import mimetypes
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--text", help="Typed list or voice transcript")
    inputs.add_argument("--image", type=Path, help="A compressed JPEG, PNG or WebP image")
    inputs.add_argument("--interpret", help="Cooking adjustment text")
    parser.add_argument("--source", choices=["typed", "voice"], default="typed")
    parser.add_argument("--kind", choices=["receipt", "photo"], default="receipt")
    parser.add_argument("--url", default="http://127.0.0.1:8001", help="Your local AI service")
    parser.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args()
    if args.image:
        try:
            if args.image.stat().st_size > 3 * 1024 * 1024:
                parser.error("Image exceeds 3 MiB; compress it before sending")
            data = args.image.read_bytes()
        except OSError:
            parser.error("Cannot read the specified image")
        media_type = mimetypes.guess_type(args.image)[0]
        if media_type not in {"image/jpeg", "image/png", "image/webp"}:
            parser.error("Use a JPEG, PNG or WebP image")
        path = "/ai/parse-image"
        payload = {
            "kind": args.kind,
            "media_type": media_type,
            "image_base64": base64.b64encode(data).decode("ascii"),
        }
    elif args.interpret is not None:
        path = "/ai/interpret"
        payload = {"text": args.interpret}
    else:
        path = "/ai/parse-items"
        payload = {"text": args.text, "source": args.source}
    request = Request(
        args.url.rstrip("/") + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=args.timeout) as response:
            status, body = response.status, response.read()
    except HTTPError as exc:
        status, body = exc.code, exc.read()
    except TimeoutError:
        print("The local API did not respond before --timeout expired.", file=sys.stderr)
        return 1
    except URLError as exc:
        message = (
            "The local API request timed out."
            if isinstance(exc.reason, TimeoutError)
            else "Cannot connect to the local API; check its URL and running container."
        )
        print(message, file=sys.stderr)
        return 1
    print(f"HTTP {status} in {time.monotonic() - started:.2f}s")
    try:
        print(json.dumps(json.loads(body), indent=2, ensure_ascii=False))
    except ValueError:
        print("The local API returned a non-JSON response.", file=sys.stderr)
        return 1
    return 0 if status < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
