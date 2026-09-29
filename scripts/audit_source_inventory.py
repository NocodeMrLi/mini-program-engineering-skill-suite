#!/usr/bin/env python3
"""Inventory a source snapshot and reject unsupported audit provenance claims."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Optional, Sequence


EXCLUDED_DIRECTORIES = frozenset({".git", ".planning", ".venv", "node_modules", "__pycache__"})
MAX_FILES = 10000
MAX_BYTES = 512 * 1024 * 1024
TOTAL_COUNT = re.compile(
    r"(?:\ball\s+|\btotal\s+|\bsnapshot\s*\(\s*|\(\s*|共\s*)"
    r"(\d+)\s*(?:source\s+)?(?:files\b|个文件)",
    re.IGNORECASE,
)
COMMIT_CLAIM = re.compile(r"\bcommit\s+`?([0-9a-f]{7,40})\b", re.IGNORECASE)


def _git_commit(root: Path) -> str:
    marker = root / ".git"
    if marker.is_symlink():
        raise ValueError("git-marker-symlink")
    if not marker.exists():
        return "unknown"
    try:
        top = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        if Path(top).resolve() != root:
            return "unknown"
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        return commit if re.fullmatch(r"[0-9a-f]{40}", commit) else "unknown"
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"


def inventory(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("root-not-directory")
    files: list[str] = []
    total_bytes = 0

    def raise_walk_error(error: OSError) -> None:
        raise error

    for directory, names, filenames in os.walk(root, followlinks=False, onerror=raise_walk_error):
        base = Path(directory)
        for name in names:
            path = base / name
            if name not in EXCLUDED_DIRECTORIES and path.is_symlink():
                raise ValueError("source-symlink:" + path.relative_to(root).as_posix())
        names[:] = sorted(name for name in names if name not in EXCLUDED_DIRECTORIES)
        for name in sorted(filenames):
            if name in EXCLUDED_DIRECTORIES:
                continue
            path = base / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or not path.is_file():
                raise ValueError("source-nonregular:" + relative)
            files.append(relative)
            if len(files) > MAX_FILES:
                raise ValueError("source-file-limit")
            size = path.stat().st_size
            total_bytes += size
            if total_bytes > MAX_BYTES:
                raise ValueError("source-byte-limit")
    files.sort()
    tree = hashlib.sha256()
    for relative in files:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError("source-changed:" + relative)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        tree.update(relative.encode("utf-8") + b"\0" + digest.digest())
    return {
        "schema_version": 1,
        "file_count": len(files),
        "files": files,
        "tree_sha256": tree.hexdigest(),
        "git_commit": _git_commit(root),
        "excluded_directories": sorted(EXCLUDED_DIRECTORIES),
    }


def check_report(text: str, facts: dict[str, Any]) -> list[str]:
    """Fail on conflicting total-count/commit claims; never certify content quality."""
    errors: list[str] = []
    count = facts["file_count"]
    for match in TOTAL_COUNT.finditer(text):
        if int(match.group(1)) != count:
            errors.append(f"file-count-mismatch:{match.group(1)}!={count}")
    commit = facts["git_commit"]
    for match in COMMIT_CLAIM.finditer(text):
        claimed = match.group(1).lower()
        if commit == "unknown" or not commit.startswith(claimed):
            errors.append("unsupported-commit-claim")
    return sorted(set(errors))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--report", type=Path, help="Optional audit report to check")
    args = parser.parse_args(argv)
    try:
        facts = inventory(args.root)
        errors = check_report(args.report.read_text(encoding="utf-8"), facts) if args.report else []
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 2
    print(json.dumps({"valid": not errors, "inventory": facts, "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
