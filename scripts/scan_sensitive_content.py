#!/usr/bin/env python3
"""Scan a public skill package for common sensitive-content patterns."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


SKIP_DIRS = {".git", ".planning", "__pycache__", "tests"}
SKIP_NAMES = {".DS_Store"}


@dataclass(frozen=True)
class Rule:
    """Describe one sensitive-content detector."""

    rule_id: str
    pattern: re.Pattern[str]
    message: str


@dataclass(frozen=True)
class Finding:
    """Represent a redacted finding without exposing the matched value."""

    path: str
    line: int
    rule_id: str
    display_rule_id: str
    message: str
    fingerprint: str
    source_kind: str


@dataclass(frozen=True)
class ScanSummary:
    """Summarize coverage without exposing candidate contents."""

    candidate_count: int
    scanned_count: int
    text_file_count: int
    binary_like_count: int
    unreadable_file_count: int


RULES: tuple[Rule, ...] = (
    Rule("wechat-appid", re.compile(r"\bwx[a-fA-F0-9]{16}\b"), "Possible real WeChat AppID"),
    Rule(
        "absolute-user-path",
        re.compile(r"/(?:Users|home)/[^/\s]+(?:/[^\s\"'`<>]*)?"),
        "User-specific absolute path",
    ),
    Rule(
        "credential-assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|token|password|private[_-]?key)\s*[:=]\s*[\"']?[^\s\"']{8,}"
        ),
        "Possible hardcoded credential",
    ),
    Rule(
        "private-key-block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "Private key material",
    ),
)


def iter_scannable_files(root: Path) -> Iterable[Path]:
    """Yield every non-private file without trusting its name or suffix."""
    if root.is_file():
        if root.name not in SKIP_NAMES:
            yield root
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in SKIP_NAMES:
            continue
        relative = path.relative_to(root)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        yield path


def scan_files_with_summary(paths: Iterable[Path], root: Path) -> tuple[list[Finding], ScanSummary]:
    """Scan exact candidates and track how much coverage was attempted."""
    findings: list[Finding] = []
    candidate_count = 0
    scanned_count = 0
    text_file_count = 0
    binary_like_count = 0
    unreadable_file_count = 0
    for path in sorted(paths):
        candidate_count += 1
        display_path = path.name if root.is_file() else path.relative_to(root).as_posix()
        try:
            raw_content = path.read_bytes()
        except OSError:
            unreadable_file_count += 1
            fingerprint = hashlib.sha256(display_path.encode("utf-8")).hexdigest()[:12]
            findings.append(
                Finding(
                    display_path,
                    0,
                    "unreadable-file",
                    "unreadable-file",
                    "File could not be safely scanned",
                    fingerprint,
                    "unreadable",
                )
            )
            continue
        try:
            content = raw_content.decode("utf-8")
            text_file_count += 1
            source_kind = "text"
        except UnicodeDecodeError:
            content = raw_content.decode("latin-1")
            binary_like_count += 1
            source_kind = "binary-like"
        else:
            if "\x00" in content:
                binary_like_count += 1
                source_kind = "binary-like"
            else:
                source_kind = "text"
        display_rule_prefix = "binary-file:" if source_kind == "binary-like" else ""
        scanned_count += 1
        for line_number, line in enumerate(content.splitlines(), start=1):
            for rule in RULES:
                for match in rule.pattern.finditer(line):
                    fingerprint = hashlib.sha256(match.group(0).encode("utf-8")).hexdigest()[:12]
                    findings.append(
                        Finding(
                            display_path,
                            line_number,
                            rule.rule_id,
                            f"{display_rule_prefix}{rule.rule_id}",
                            rule.message,
                            fingerprint,
                            source_kind,
                        )
                    )
    return findings, ScanSummary(
        candidate_count=candidate_count,
        scanned_count=scanned_count,
        text_file_count=text_file_count,
        binary_like_count=binary_like_count,
        unreadable_file_count=unreadable_file_count,
    )


def scan_files(paths: Iterable[Path], root: Path) -> list[Finding]:
    """Return redacted findings for a set of exact public-package candidates."""
    findings, _ = scan_files_with_summary(paths, root)
    return findings


def scan_path(root: Path) -> list[Finding]:
    """Return redacted findings for every non-private file below ``root``."""
    return scan_files(iter_scannable_files(root), root)


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Public package directory or text file to scan")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the scan and return 1 when sensitive content is detected."""
    args = build_parser().parse_args(argv)
    target = args.path.resolve()
    if not target.exists():
        print(json.dumps({"error": "path does not exist", "path": str(args.path)}), file=sys.stderr)
        return 2

    findings, summary = scan_files_with_summary(iter_scannable_files(target), target)
    report = {
        "path": str(args.path),
        "candidate_count": summary.candidate_count,
        "scanned_count": summary.scanned_count,
        "text_file_count": summary.text_file_count,
        "binary_like_count": summary.binary_like_count,
        "unreadable_file_count": summary.unreadable_file_count,
        "finding_count": len(findings),
        "findings": [asdict(f) for f in findings],
    }
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif findings:
        print(
            "Scanned "
            f"{summary.scanned_count}/{summary.candidate_count} candidates "
            f"({summary.binary_like_count} binary-like, {summary.unreadable_file_count} unreadable)."
        )
        for finding in findings:
            print(
                f"{finding.path}:{finding.line} "
                f"[{finding.display_rule_id}] {finding.message} ({finding.fingerprint})"
            )
    else:
        print(
            "Scanned "
            f"{summary.scanned_count}/{summary.candidate_count} candidates "
            f"({summary.binary_like_count} binary-like, {summary.unreadable_file_count} unreadable); "
            "no sensitive-content patterns found."
        )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
