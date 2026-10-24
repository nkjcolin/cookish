"""Build a single-architecture local Lambda image; never pushes or deploys."""

import argparse
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=["arm64", "amd64"], default="arm64")
    parser.add_argument("--tag", default="cookish-ai:lambda")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [
            "docker",
            "buildx",
            "build",
            "--platform",
            f"linux/{args.arch}",
            "--provenance=false",
            "--load",
            "-f",
            str(root / "Dockerfile.lambda"),
            "-t",
            args.tag,
            str(root),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
