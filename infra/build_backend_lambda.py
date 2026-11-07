"""Build the API/migration ZIP from one Git commit and its frozen uv lockfile.

Run with Python 3.12. This script does not sign in to AWS or deploy anything.
"""

import argparse
import ast
import csv
import hashlib
import io
import json
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from importlib.metadata import distributions
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = (
    "backend/app",
    "backend/migrations",
    "backend/alembic.ini",
    "backend/seed/seed.py",
    "backend/seed/ingredients.csv",
    "backend/seed/recipes",
    "backend/pyproject.toml",
    "backend/uv.lock",
)
PLATFORMS = {
    "arm64": ("aarch64-manylinux_2_28", 183),
    "x86_64": ("x86_64-manylinux_2_28", 62),
}


def run(*args: str, cwd: Path = ROOT) -> bytes:
    return subprocess.check_output(args, cwd=cwd)


def committed_files(commit: str) -> dict[str, bytes]:
    archive_bytes = run("git", "archive", commit, *SOURCE_PATHS)
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            path = PurePosixPath(member.name)
            if not member.isfile() or ".." in path.parts or path.is_absolute():
                raise ValueError(f"Unexpected source archive entry: {member.name}")
            relative = path.relative_to("backend").as_posix()
            if path.suffix not in {".py", ".mako", ".ini", ".csv", ".yaml", ".toml", ".lock"}:
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"Cannot read source file: {member.name}")
            files[relative] = stream.read()
    for required in (
        "app/lambda_handler.py",
        "app/migrate.py",
        "migrations/env.py",
        "seed/seed.py",
        "seed/ingredients.csv",
        "pyproject.toml",
        "uv.lock",
    ):
        if required not in files:
            raise ValueError(f"Missing source file: {required}")
    return files


def migration_head(files: dict[str, bytes]) -> str:
    revisions = set()
    parents = set()
    for name, data in files.items():
        if not name.startswith("migrations/versions/") or not name.endswith(".py"):
            continue
        for node in ast.parse(data, filename=name).body:
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign):
                targets, value = [node.target], node.value
            else:
                continue
            for target in targets:
                if not isinstance(target, ast.Name) or target.id not in {
                    "revision",
                    "down_revision",
                }:
                    continue
                revision = ast.literal_eval(value)
                if target.id == "revision":
                    revisions.add(revision)
                elif revision:
                    parents.update(revision if isinstance(revision, tuple) else [revision])
    heads = revisions - parents
    if len(heads) != 1:
        raise ValueError(f"Expected one migration head, found {sorted(heads)}")
    return heads.pop()


def dependency_files(directory: Path) -> dict[str, bytes]:
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Unexpected dependency symlink: {path.name}")
        if not path.is_file():
            continue
        relative = path.relative_to(directory)
        if relative.parts[0] in {"bin", "Scripts"} or "__pycache__" in relative.parts:
            continue
        if path.name == ".lock" or path.suffix in {".pyc", ".pyo"}:
            continue
        if path.suffix.lower() in {".dll", ".exe", ".pyd"}:
            raise ValueError(f"Windows binary in dependency package: {relative}")
        files[relative.as_posix()] = path.read_bytes()
    return files


def validate_files(files: dict[str, bytes], architecture: str) -> tuple[int, int]:
    python_count = native_count = 0
    for name, data in files.items():
        if data.startswith(b"MZ"):
            raise ValueError(f"Windows executable in package: {name}")
        if data.startswith(b"\x7fELF"):
            if len(data) < 20 or data[4:6] != b"\x02\x01":
                raise ValueError(f"Expected 64-bit little-endian ELF: {name}")
            if struct.unpack("<H", data[18:20])[0] != PLATFORMS[architecture][1]:
                raise ValueError(f"Wrong binary architecture: {name}")
            native_count += 1
        elif ".so" in PurePosixPath(name).suffixes:
            raise ValueError(f"Shared library is not ELF: {name}")
        if name.endswith(".py"):
            compile(data, name, "exec", dont_inherit=True)
            python_count += 1
    return python_count, native_count


def write_archive(path: Path, files: dict[str, bytes]) -> None:
    # Exclusive creation prevents accidentally replacing an earlier release.
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o755 if data.startswith(b"\x7fELF") else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archive integrity check failed")


def build(args: argparse.Namespace) -> None:
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Use Python 3.12 so source compilation matches the Lambda runtime")
    uv = shutil.which(args.uv)
    if uv is None:
        raise ValueError("uv was not found; install uv or pass --uv /absolute/path/to/uv")
    output = (ROOT / args.output_dir).resolve()
    allowed = [(ROOT / name).resolve() for name in ("private", ".aws-sam")]
    if not any(output == base or base in output.parents for base in allowed):
        raise ValueError("--output-dir must be inside this repository's private/ or .aws-sam/")
    if not any(ROOT == base.parent for base in allowed if output == base or base in output.parents):
        raise ValueError("Output root must not be a symlink outside the repository")
    commit = (
        run("git", "rev-parse", "--verify", "--end-of-options", f"{args.source_ref}^{{commit}}")
        .decode()
        .strip()
    )
    files = committed_files(commit)
    name = f"cookish-backend-{commit[:12]}-python312-{args.architecture}"
    target = output / f"{name}.zip"
    manifest_path = output / f"{name}.json"
    requirements_path = output / f"{name}-requirements.txt"
    for path in (target, manifest_path, requirements_path):
        if path.exists():
            raise ValueError(f"Output already exists; choose another --output-dir: {path}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="build-", dir=output) as temporary:
        staging = Path(temporary)
        project = staging / "project"
        project.mkdir()
        for filename in ("pyproject.toml", "uv.lock"):
            (project / filename).write_bytes(files.pop(filename))
        requirements = staging / "requirements.txt"
        run(
            uv,
            "export",
            "--project",
            str(project),
            "--frozen",
            "--no-dev",
            "--no-emit-project",
            "--no-header",
            "--no-annotate",
            "--quiet",
            "--output-file",
            str(requirements),
        )
        dependencies = staging / "dependencies"
        run(
            uv,
            "pip",
            "install",
            "--python",
            sys.executable,
            "--requirements",
            str(requirements),
            "--require-hashes",
            "--python-version",
            "3.12",
            "--python-platform",
            PLATFORMS[args.architecture][0],
            "--only-binary",
            ":all:",
            "--target",
            str(dependencies),
            "--link-mode",
            "copy",
            "--no-progress",
        )
        source_hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
        installed = dependency_files(dependencies)
        if installed.keys() & files.keys():
            raise ValueError("Dependency package conflicts with application source")
        installed.update(files)
        python_count, native_count = validate_files(installed, args.architecture)
        ingredients = list(
            csv.DictReader(io.StringIO(files["seed/ingredients.csv"].decode("utf-8-sig")))
        )
        manifest = {
            "source_commit": commit,
            "runtime": "python3.12",
            "architecture": args.architecture,
            "platform": PLATFORMS[args.architecture][0],
            "uv_version": run(uv, "--version").decode().strip(),
            "dependency_lock_sha256": hashlib.sha256(
                (project / "uv.lock").read_bytes()
            ).hexdigest(),
            "packages": dict(
                sorted(
                    (d.metadata["Name"], d.version) for d in distributions(path=[str(dependencies)])
                )
            ),
            "runtime_supplied_packages": ["boto3 and its AWS SDK dependencies"],
            "migration_head": migration_head(files),
            "ingredient_rows": len(ingredients),
            "recipe_files": sum(
                n.startswith("seed/recipes/") and n.endswith(".yaml") for n in files
            ),
            "python_files_compiled": python_count,
            "native_files": native_count,
            "source_file_sha256": source_hashes,
            "validation_limit": "Native imports still require verification on the Lambda runtime.",
        }
        installed["release-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
        write_archive(target, installed)
        manifest.update(
            archive_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            archive_bytes=target.stat().st_size,
            uncompressed_bytes=sum(map(len, installed.values())),
            archive_entries=len(installed),
        )
        with requirements_path.open("xb") as stream:
            stream.write(requirements.read_bytes())
        with manifest_path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "archive": str(target),
                "manifest": str(manifest_path),
                "sha256": manifest["archive_sha256"],
                "bytes": manifest["archive_bytes"],
            },
            indent=2,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-ref", default="HEAD", help="Committed Git ref to package (default: HEAD)"
    )
    parser.add_argument("--architecture", choices=PLATFORMS, default="arm64")
    parser.add_argument("--uv", default="uv", help="uv executable name or full path")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".aws-sam/backend-release"),
        help="Output directory under private/ or .aws-sam/ (relative to repository root)",
    )
    args = parser.parse_args()
    try:
        build(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
