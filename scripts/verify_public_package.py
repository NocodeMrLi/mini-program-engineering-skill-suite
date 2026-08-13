#!/usr/bin/env python3
"""Verify an exported public package without consulting its source directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Sequence

from validate_suite import validate


MANIFEST_NAME = "package-manifest.json"
MAX_MANIFEST_BYTES = 2_000_000
MAX_MANIFEST_FILES = 10_000
MAX_RELATIVE_PATH_LENGTH = 512
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class DuplicateKeyError(ValueError):
    """Signal a duplicate JSON object key without exposing that key."""


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object while rejecting ambiguous duplicate keys."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError
        result[key] = value
    return result


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for one package file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_safe_manifest_path(value: object) -> bool:
    """Accept only normalized portable relative POSIX paths."""
    if not isinstance(value, str) or not value or len(value) > MAX_RELATIVE_PATH_LENGTH:
        return False
    if "\\" in value or value.startswith("/") or value == MANIFEST_NAME:
        return False
    segments = value.split("/")
    return all(segment not in {"", ".", ".."} for segment in segments)


def load_manifest(package: Path, errors: set[str]) -> dict[str, object] | None:
    """Load a size-bounded, unambiguous JSON manifest."""
    manifest_path = package / MANIFEST_NAME
    if manifest_path.is_symlink():
        errors.add("manifest-invalid")
        return None
    if not manifest_path.is_file():
        errors.add("manifest-missing")
        return None
    try:
        if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
            errors.add("manifest-invalid")
            return None
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (DuplicateKeyError, OSError, UnicodeError, json.JSONDecodeError):
        errors.add("manifest-invalid")
        return None
    if not isinstance(manifest, dict):
        errors.add("manifest-invalid")
        return None
    return manifest


def parse_entries(
    manifest: dict[str, object], errors: set[str]
) -> list[tuple[str, int, str]] | None:
    """Validate manifest metadata and return safe file entries."""
    files = manifest.get("files")
    file_count = manifest.get("file_count")
    metadata_valid = (
        manifest.get("format_version") == 1
        and manifest.get("suite_name") == "mini-program-engineering-suite"
        and isinstance(manifest.get("suite_version"), str)
        and bool(manifest.get("suite_version"))
        and manifest.get("suite_valid") is True
        and manifest.get("sensitive_finding_count") == 0
        and isinstance(files, list)
        and isinstance(file_count, int)
        and not isinstance(file_count, bool)
    )
    if not metadata_valid or not isinstance(files, list) or len(files) > MAX_MANIFEST_FILES:
        errors.add("manifest-invalid")
        return None
    if file_count != len(files):
        errors.add("manifest-file-count-mismatch")

    entries: list[tuple[str, int, str]] = []
    seen_paths: set[str] = set()
    structural_error = False
    for item in files:
        if not isinstance(item, dict):
            errors.add("manifest-invalid")
            structural_error = True
            continue
        relative_path = item.get("path")
        size = item.get("size")
        digest = item.get("sha256")
        if not is_safe_manifest_path(relative_path):
            errors.add("manifest-path-invalid")
            structural_error = True
            continue
        assert isinstance(relative_path, str)
        if relative_path in seen_paths:
            errors.add("manifest-duplicate-path")
            structural_error = True
            continue
        seen_paths.add(relative_path)
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(digest, str)
            or not SHA256_PATTERN.fullmatch(digest)
        ):
            errors.add("manifest-invalid")
            structural_error = True
            continue
        entries.append((relative_path, size, digest))
    return None if structural_error else entries


def actual_package_files(package: Path, errors: set[str]) -> set[str]:
    """Collect regular package files and reject symbolic links."""
    files: set[str] = set()
    for candidate in sorted(package.rglob("*")):
        if candidate.is_symlink():
            errors.add("unsupported-file")
            continue
        if candidate.is_file():
            files.add(candidate.relative_to(package).as_posix())
    return files


def verify_package(package: Path) -> dict[str, object]:
    """Return a redacted integrity report for one exported package."""
    errors: set[str] = set()
    if package.is_symlink() or not package.is_dir():
        return {"valid": False, "verified_file_count": 0, "errors": ["package-invalid"]}

    manifest = load_manifest(package, errors)
    if manifest is None:
        return {"valid": False, "verified_file_count": 0, "errors": sorted(errors)}
    entries = parse_entries(manifest, errors)
    if entries is None:
        return {"valid": False, "verified_file_count": 0, "errors": sorted(errors)}

    actual_files = actual_package_files(package, errors)
    expected_files = {entry[0] for entry in entries} | {MANIFEST_NAME}
    if expected_files - actual_files:
        errors.add("file-missing")
    if actual_files - expected_files:
        errors.add("unexpected-file")

    checked_files = 0
    for relative_path, expected_size, expected_digest in entries:
        target = package.joinpath(*relative_path.split("/"))
        if target.is_symlink() or not target.is_file():
            continue
        try:
            if target.stat().st_size != expected_size:
                errors.add("file-size-mismatch")
            if sha256_file(target) != expected_digest:
                errors.add("file-hash-mismatch")
            checked_files += 1
        except OSError:
            errors.add("file-unreadable")

    if not errors:
        try:
            suite_report = validate(package)
        except (OSError, UnicodeError):
            errors.add("suite-structure-invalid")
        else:
            if not suite_report["valid"]:
                errors.add("suite-structure-invalid")

    return {
        "valid": not errors,
        "verified_file_count": checked_files,
        "errors": sorted(errors),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Verify a package and emit a redacted machine-readable result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Exported package directory")
    args = parser.parse_args(argv)
    report = verify_package(args.package)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
