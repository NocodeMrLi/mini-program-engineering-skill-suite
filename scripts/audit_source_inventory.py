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
    r"(?:\ball\s+|\btotal\s+|\bsnapshot\s*\(\s*|共\s*)"
    r"(\d+)\s*(?:source\s+)?(?:files\b|个文件)",
    re.IGNORECASE,
)
COMMIT_CLAIM = re.compile(r"\bcommit\s+`?([0-9a-f]{7,40})\b", re.IGNORECASE)
CODE_SUFFIXES = frozenset({".js", ".ts", ".wxs"})
MAX_SCAN_BYTES = 1024 * 1024
MAX_TARGETS_PER_CATEGORY_FILE = 12
HOTSPOT_PATTERNS = (
    ("active-resource", re.compile(r"\b(?:setInterval|setTimeout|addEventListener|wx\.on\w+)\s*\(")),
    ("numeric-guard", re.compile(r"\btypeof\b.{0,100}?[=!]==?\s*['\"]number['\"]", re.DOTALL)),
    ("length-modulo", re.compile(r"%\s*(?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*\.length")),
)
REVIEW_CHALLENGES = {
    "active-resource": "Trace create, pause, resume, and dispose across onLoad/onShow/onHide/onShow/onUnload; does a leave-and-return restart the resource?",
    "numeric-guard": "Substitute NaN, Infinity, -Infinity, a fraction, and an out-of-range number into each read/write guard; calculate the branch result and downstream use.",
    "length-modulo": "For the same input calculate the result with collection lengths N and N+1, then advance N steps; test any stability or no-repeat claim.",
    "local-cloud-authority": "When local cache is absent or stale, or cloud is unavailable, which source authorizes the state on a second device and how does it converge?",
    "multiwrite-atomicity": "Interrupt or retry between the writes and consider concurrent requests; identify whether a transaction, unique constraint, or idempotent winner closes the gap.",
    "error-success-boundary": "Follow the error handler to the persisted and user-visible state; does a local-only fallback claim server-confirmed success?",
}


def _hotspots(root: Path, files: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    targets: list[dict[str, Any]] = []
    skipped: list[str] = []
    seen: set[tuple[str, str, int]] = set()

    def add_target(category: str, relative: str, source: str, offset: int) -> None:
        line = source.count("\n", 0, offset) + 1
        key = (category, relative, line)
        if key not in seen:
            seen.add(key)
            targets.append({"category": category, "path": relative, "line": line})

    for relative in files:
        path = root / relative
        if path.suffix not in CODE_SUFFIXES:
            continue
        if path.stat().st_size > MAX_SCAN_BYTES:
            skipped.append(relative)
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        for category, pattern in HOTSPOT_PATTERNS:
            matches = list(pattern.finditer(source))
            for match in matches[:MAX_TARGETS_PER_CATEGORY_FILE]:
                add_target(category, relative, source, match.start())
            if len(matches) > MAX_TARGETS_PER_CATEGORY_FILE:
                skipped.append(f"{relative}:{category}:truncated")
        local_read = source.find("wx.getStorageSync")
        if local_read >= 0 and "wx.cloud.callFunction" in source:
            add_target("local-cloud-authority", relative, source, local_read)
        cloud_add = re.search(r"\.add\s*\(", source)
        if "db.collection" in source and cloud_add and re.search(r"\.(?:update|remove)\s*\(", source):
            add_target("multiwrite-atomicity", relative, source, cloud_add.start())
        handler = re.search(r"\bcatch\s*(?:\(|\{)", source)
        if handler and re.search(r"localOnly|status\s*:\s*['\"]confirmed['\"]", source):
            add_target("error-success-boundary", relative, source, handler.start())
    targets.sort(key=lambda item: (item["category"], item["path"], item["line"]))
    return targets, skipped


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
    targets, skipped = _hotspots(root, files)
    active_categories = sorted({target["category"] for target in targets})
    return {
        "schema_version": 1,
        "file_count": len(files),
        "files": files,
        "tree_sha256": tree.hexdigest(),
        "git_commit": _git_commit(root),
        "excluded_directories": sorted(EXCLUDED_DIRECTORIES),
        "review_targets": targets,
        "review_challenges": {category: REVIEW_CHALLENGES[category] for category in active_categories},
        "hotspot_scan_skipped": skipped,
    }


def check_report(text: str, facts: dict[str, Any], *, check_challenges: bool = False) -> list[str]:
    """Reject provenance contradictions and optional missing boundary mentions, not reasoning quality."""
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
    if check_challenges and "numeric-guard" in facts["review_challenges"]:
        if not re.search(r"\bNaN\b|非数", text, re.IGNORECASE):
            errors.append("missing-numeric-boundary:NaN")
    return sorted(set(errors))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--report", type=Path, help="Optional audit report to check")
    parser.add_argument("--check-challenges", action="store_true", help="Lint explicit boundary coverage; does not prove reasoning")
    args = parser.parse_args(argv)
    try:
        facts = inventory(args.root)
        if args.check_challenges and not args.report:
            parser.error("--check-challenges requires --report")
        errors = check_report(
            args.report.read_text(encoding="utf-8"), facts,
            check_challenges=args.check_challenges,
        ) if args.report else []
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 2
    print(json.dumps({"valid": not errors, "inventory": facts, "errors": errors}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
