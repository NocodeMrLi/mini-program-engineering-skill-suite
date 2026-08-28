#!/usr/bin/env python3
"""Validate and export a deterministic, redacted public skill package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Iterable, Sequence

from scan_sensitive_content import scan_files, scan_path
from validate_suite import REQUIRED_FILES, validate
from verify_public_package import verify_package


EXCLUDED_PARTS = {".git", ".planning", "tests", "__pycache__", ".pytest_cache"}
IGNORED_NAMES = {".DS_Store", ".gitignore"}
PUBLIC_PATHS = frozenset(REQUIRED_FILES)


def iter_source_candidates(root: Path) -> Iterable[Path]:
    """Yield every file outside explicitly private development boundaries."""
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in IGNORED_NAMES:
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        yield path


def collect_public_files(root: Path) -> list[Path]:
    """Resolve the exact public allowlist and reject every unknown candidate."""
    candidates = list(iter_source_candidates(root))
    unexpected = [path for path in candidates if path.relative_to(root).as_posix() not in PUBLIC_PATHS]
    if unexpected:
        raise ValueError(f"source contains {len(unexpected)} file(s) outside public allowlist")

    files = [root / relative_path for relative_path in sorted(PUBLIC_PATHS)]
    missing = [path for path in files if not path.is_file()]
    if missing:
        raise ValueError(f"source is missing {len(missing)} public allowlist file(s)")
    if any(path.is_symlink() for path in files):
        raise ValueError("source public allowlist contains unsupported symbolic links")
    return files


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(root: Path, files: list[Path]) -> dict[str, object]:
    """Build a location-independent manifest for copied files."""
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    entries = [
        {"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path), "size": path.stat().st_size}
        for path in files
    ]
    return {
        "format_version": 1,
        "suite_name": "mini-program-engineering-suite",
        "suite_version": version,
        "suite_valid": True,
        "sensitive_finding_count": 0,
        "file_count": len(entries),
        "files": entries,
    }


def export_package(source: Path, output: Path) -> dict[str, object]:
    """Validate source, copy public files, and verify the exported package."""
    source = source.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError("output path already exists")
    if not source.is_dir():
        raise ValueError("source path is not a directory")
    files = collect_public_files(source)
    if scan_files(files, source):
        raise ValueError("source sensitive-content scan failed")
    source_report = validate(source)
    if not source_report["valid"]:
        raise ValueError("source suite validation failed")

    manifest = build_manifest(source, files)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_path = Path(tempfile.mkdtemp(prefix="skill-export-", dir=str(output.parent)))
    try:
        for path in files:
            target = temp_path / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        (temp_path / "package-manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        exported_report = validate(temp_path)
        exported_findings = scan_path(temp_path)
        integrity_report = verify_package(temp_path)
        if not exported_report["valid"] or exported_findings or not integrity_report["valid"]:
            raise ValueError("exported package verification failed")
        temp_path.replace(output)
    except Exception:
        shutil.rmtree(temp_path, ignore_errors=True)
        raise
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    """Run the public export and print its redacted manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Suite source directory")
    parser.add_argument("--output", required=True, type=Path, help="New output directory")
    args = parser.parse_args(argv)
    try:
        manifest = export_package(args.source, args.output)
    except (OSError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
