"""Write the API contract to docs/openapi.json, or check that the file is current.

uv run python scripts/export_openapi.py           # regenerate
uv run python scripts/export_openapi.py --check   # exit 1 if out of date (CI)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    current = render()
    if "--check" not in sys.argv:
        OPENAPI_PATH.write_text(current)
        print(f"Wrote {OPENAPI_PATH}")
        return 0
    if not OPENAPI_PATH.exists() or OPENAPI_PATH.read_text() != current:
        print("docs/openapi.json is out of date. Run: uv run python scripts/export_openapi.py")
        return 1
    print("docs/openapi.json is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
