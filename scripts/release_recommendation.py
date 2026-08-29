#!/usr/bin/env python3
"""Recommend whether the current tree deserves a release, and at which level.

Deterministic and zero-LLM-cost: classifies commits since the last tag by the
paths they touch. Output is exactly one of RECOMMEND_RELEASE (with a level) or
HOLD, always with reasons. The author makes the final call.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


LEVELS = ("patch", "minor", "major")
# Path prefixes that classify the character of a change. Checked in order of severity.
PATH_CLASSES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("SKILL.md", "skills/", "shared/"), "behavior"),
    (("scripts/", "install.sh", ".github/", "tests/", "agents/", "references/"), "tooling"),
    (("platforms/",), "data"),
    (("README", "CHANGELOG", "VERSION", "LICENSE", "COMPATIBILITY", "EVALUATIONS"), "docs"),
    (("assets/",), "assets"),
)


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False, text=True
    )
    if result.returncode:
        raise ValueError(f"git-{'-'.join(args[:1])}-failed:{result.stderr.strip()[:200]}")
    return result.stdout


def last_tag(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "describe", "--tags", "--abbrev=0"],
        capture_output=True, check=False, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def classify_commit(paths: list[str]) -> str:
    """Pick the most significant class among the commit's touched paths."""
    ranking = {"behavior": 4, "tooling": 3, "data": 2, "docs": 1, "assets": 1}
    best = "docs"
    for path in paths:
        for prefixes, label in PATH_CLASSES:
            if path.startswith(prefixes):
                if ranking[label] > ranking[best]:
                    best = label
                break
    return best


def collect_commits(root: Path, tag: str | None) -> list[dict[str, Any]]:
    # git emits: <boundary><hash><sep><subject>\n<file>\n<file>\n per commit with --name-only,
    # so each block starts with its header and carries its own file list.
    separator = "@@FIELD@@"
    boundary = "@@COMMIT@@"
    log_format = f"{boundary}%H{separator}%s"
    raw = git(root, "log", "--name-only", f"--format={log_format}", *(["%s..HEAD" % tag] if tag else []))
    commits: list[dict[str, Any]] = []
    for block in raw.split(boundary):
        lines = [line for line in block.strip().splitlines() if line.strip()]
        if not lines or separator not in lines[0]:
            continue
        header = lines[0].split(separator)
        if len(header) < 2:
            continue
        commits.append({"hash": header[0][:8], "subject": header[1], "paths": lines[1:]})
    return commits


def recommend(root: Path, min_data_changes: int) -> dict[str, Any]:
    tag = last_tag(root)
    commits = collect_commits(root, tag)
    if not commits:
        return {"recommendation": "HOLD", "level": None, "reasons": ["no-commits-since-last-tag"], "tag": tag,
                "commit_count": 0, "classes": {}}

    classes: dict[str, int] = {}
    for commit in commits:
        label = classify_commit(commit["paths"])
        classes[label] = classes.get(label, 0) + 1

    if classes.get("behavior"):
        level = "minor"
        reasons = [f"{classes['behavior']} commit(s) touch skill text, guardrails, or the root skill (behavior changes)"]
    elif classes.get("tooling"):
        level = "minor"
        reasons = [f"{classes['tooling']} commit(s) touch scripts, installer, CI, or tests (tooling changes)"]
    elif classes.get("data"):
        if classes["data"] < min_data_changes:
            return {
                "recommendation": "HOLD",
                "level": None,
                "reasons": [
                    f"only {classes['data']} data-only commit(s) since {tag or 'start'}; "
                    f"threshold is {min_data_changes}; accumulate more or release on demand"
                ],
                "tag": tag, "commit_count": len(commits), "classes": classes,
            }
        level = "patch"
        reasons = [f"{classes['data']} commit(s) of platform fact data only; no behavior or methodology changes"]
    else:
        return {
            "recommendation": "HOLD",
            "level": None,
            "reasons": ["only documentation/asset changes; release on demand, not required"],
            "tag": tag, "commit_count": len(commits), "classes": classes,
        }

    return {
        "recommendation": "RECOMMEND_RELEASE",
        "level": level,
        "reasons": reasons,
        "tag": tag,
        "commit_count": len(commits),
        "classes": classes,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("."), help="Repository root")
    parser.add_argument("--min-data-changes", type=int, default=1, help="Minimum data commits for a patch release")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)
    try:
        report = recommend(args.root.resolve(), args.min_data_changes)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        head = f"{report['recommendation']}" + (f" ({report['level']})" if report.get("level") else "")
        print(head)
        for reason in report["reasons"]:
            print(f"- {reason}")
        print(f"- since tag: {report.get('tag') or 'none'}; commits: {report.get('commit_count', 0)}; classes: {report.get('classes', {})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
