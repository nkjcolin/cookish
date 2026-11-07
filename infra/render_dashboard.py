"""Render the Cookish CloudWatch dashboard from verified resource identifiers.

Uses only the Python standard library. Does not contact or modify AWS.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PLACEHOLDER = re.compile(r"\$\{([^{}]+)\}")
TEMPLATE = Path(__file__).with_name("cloudwatch-dashboard.json")


def identifier(pattern: str, label: str):
    def parse(value: str) -> str:
        if not re.fullmatch(pattern, value):
            raise argparse.ArgumentTypeError(f"Invalid {label}: {value!r}")
        return value

    return parse


def render(value, substitutions: dict[str, str]):
    if isinstance(value, dict):
        return {key: render(item, substitutions) for key, item in value.items()}
    if isinstance(value, list):
        return [render(item, substitutions) for item in value]
    if isinstance(value, str):

        def substitute(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in substitutions:
                raise ValueError(f"Unknown dashboard placeholder: {name}")
            return substitutions[name]

        return PLACEHOLDER.sub(substitute, value)
    return value


def validate_layout(dashboard: dict) -> None:
    widgets = dashboard.get("widgets")
    if not isinstance(widgets, list) or not widgets:
        raise ValueError("Dashboard must contain widgets")
    rectangles: list[tuple[int, int, int, int]] = []
    for index, widget in enumerate(widgets):
        x, y, width, height = (widget[key] for key in ("x", "y", "width", "height"))
        if not all(
            isinstance(number, int) and not isinstance(number, bool)
            for number in (x, y, width, height)
        ):
            raise ValueError(f"Widget {index} has non-integer layout coordinates")
        if x < 0 or y < 0 or width < 1 or height < 1 or x + width > 24:
            raise ValueError(f"Widget {index} lies outside the dashboard grid")
        rectangle = (x, y, x + width, y + height)
        for other_index, other in enumerate(rectangles):
            if (
                x < other[2]
                and rectangle[2] > other[0]
                and y < other[3]
                and rectangle[3] > other[1]
            ):
                raise ValueError(f"Widgets {other_index} and {index} overlap")
        rectangles.append(rectangle)
        if widget["type"] == "metric":
            properties = widget["properties"]
            if properties.get("period") != 60:
                raise ValueError(f"Widget {index} must retain its one-minute period")
            if not properties.get("metrics"):
                raise ValueError(f"Widget {index} has no metrics")
    if dashboard.get("periodOverride") != "inherit":
        raise ValueError("Dashboard must retain explicit widget periods")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True, type=identifier(r"\d{12}", "AWS account ID"))
    parser.add_argument(
        "--region",
        required=True,
        type=identifier(r"[a-z]{2}(?:-[a-z]+)+-\d+", "AWS region"),
    )
    parser.add_argument("--api-id", required=True, type=identifier(r"[a-z0-9]+", "HTTP API ID"))
    parser.add_argument(
        "--db-instance-id",
        required=True,
        type=identifier(r"[a-zA-Z][a-zA-Z0-9-]{0,62}", "DB instance identifier"),
        help="Verify this in RDS; a CloudFormation logical ID or database name is not sufficient",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination JSON file (not the source template)",
    )
    args = parser.parse_args()
    if args.db_instance_id.endswith("-") or "--" in args.db_instance_id:
        parser.error(
            "DB instance identifier cannot end with a hyphen or contain consecutive hyphens"
        )
    if args.output.resolve() == TEMPLATE.resolve():
        parser.error("Output must not overwrite the source template")

    substitutions = {
        "ACCOUNT_ID": args.account_id,
        "AWS_REGION": args.region,
        "HTTP_API_ID": args.api_id,
        "DB_INSTANCE_ID": args.db_instance_id,
    }
    try:
        template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        dashboard = render(template, substitutions)
        validate_layout(dashboard)
        body = json.dumps(dashboard, indent=2) + "\n"
        if PLACEHOLDER.search(body):
            raise ValueError("Rendered dashboard still contains placeholders")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(f"Rendered {len(dashboard['widgets'])} widgets to {args.output}")
    print("No AWS resources were changed. Verify the identifiers before applying this file.")


if __name__ == "__main__":
    main()
