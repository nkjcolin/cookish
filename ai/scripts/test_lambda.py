"""Send an API Gateway HTTP API v2 event to a local Lambda emulator, not AWS."""

import argparse
import base64
import json
import mimetypes
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def gateway_event(path, payload):
    return {
        "version": "2.0",
        "routeKey": f"POST {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "accountId": "local",
            "apiId": "local",
            "domainName": "localhost",
            "domainPrefix": "local",
            "requestId": str(uuid4()),
            "routeKey": f"POST {path}",
            "stage": "$default",
            "timeEpoch": int(time.time() * 1000),
            "http": {
                "method": "POST",
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "cookish-local-test",
            },
        },
        "body": json.dumps(payload),
        "isBase64Encoded": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--text")
    inputs.add_argument("--interpret")
    inputs.add_argument("--image", type=Path)
    parser.add_argument("--kind", choices=["receipt", "photo"], default="receipt")
    parser.add_argument("--source", choices=["typed", "voice"], default="typed")
    parser.add_argument("--url", default="http://127.0.0.1:9000")
    args = parser.parse_args()
    if args.image:
        media_type = mimetypes.guess_type(args.image)[0]
        if media_type not in {"image/jpeg", "image/png", "image/webp"}:
            parser.error("Use JPEG, PNG or WebP")
        if args.image.stat().st_size > 3 * 1024 * 1024:
            parser.error("Compress images to at most 3 MiB")
        path = "/ai/parse-image"
        payload = {
            "kind": args.kind,
            "media_type": media_type,
            "image_base64": base64.b64encode(args.image.read_bytes()).decode(),
        }
    elif args.interpret is not None:
        path, payload = "/ai/interpret", {"text": args.interpret}
    else:
        path, payload = "/ai/parse-items", {"text": args.text, "source": args.source}
    request = Request(
        args.url.rstrip("/") + "/2015-03-31/functions/function/invocations",
        data=json.dumps(gateway_event(path, payload)).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=35) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError):
        parser.exit(1, "Cannot invoke local Lambda emulator; check its container and port.\n")
    # RIE can return HTTP 200 with a Lambda runtime error. Check the inner status.
    print(json.dumps(result, indent=2))
    return 0 if 200 <= result.get("statusCode", 500) < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
