#!/usr/bin/env python3
"""Recommend whether the current tree deserves a release, and at which level.

Deterministic and zero-LLM-cost: classifies commits since the last tag by the
paths they touch. Output is exactly one of RECOMMEND_RELEASE (with a level),
MANUAL_VERIFICATION_REQUIRED, or HOLD, always with reasons. The author makes
the final call.

manual-only platform policy (platforms/README.md): major releases require
re-verification of every alipay/douyin fact; minor releases require it when
the last verification is older than 90 days or when platform facts / release
governance changed; patch releases only when related facts changed, a user
report arrived, or the platform shifted. Overdue verification downgrades the
recommendation to MANUAL_VERIFICATION_REQUIRED — it never passes silently.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence


LEVELS = ("patch", "minor", "major")
MANUAL_ONLY_PLATFORMS = ("alipay", "douyin")
VERIFICATION_MAX_AGE_DAYS = 90
FACT_ANNOTATION = re.compile(
    r"<!--\s*fact:\s*\S+\s+verified=(?P<verified>[^\s]+)\s+source=\S+\s+digest=\S+\s*-->"
)
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


def last_tag(root: Path, before: str | None = None) -> str | None:
    """Newest tag, optionally strictly BEFORE a given rev.

    With before=None this is the plain "most recent tag" (HEAD-relative). With
    before="<candidate>^" it returns the last tag that precedes the candidate's
    parent — the true baseline for a release checkout, where HEAD sits ON the
    candidate tag and a plain describe would return the candidate itself
    (the P0 bypass: candidate..HEAD = empty -> HOLD -> gate skipped).
    """
    args = ["git", "-C", str(root), "describe", "--tags", "--abbrev=0"]
    if before is not None:
        args.append(before)
    result = subprocess.run(args, capture_output=True, check=False, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def head_commit(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, check=False, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def tag_commit(root: Path, tag: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", f"{tag}^{{}}"],
        capture_output=True, check=False, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def is_shallow_repository(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-shallow-repository"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode:
        raise ValueError(f"git-shallow-check-failed:{result.stderr.strip()[:200]}")
    return result.stdout.strip() == "true"


def classify_commit(paths: list[str]) -> str:
    """Pick the most significant class among the commit's touched paths (kept for callers that want one label)."""
    ranking = {"behavior": 4, "tooling": 3, "data": 2, "docs": 1, "assets": 1}
    best = "docs"
    for label in classify_commit_classes(paths):
        if ranking[label] > ranking[best]:
            best = label
    return best


def classify_commit_classes(paths: list[str]) -> set[str]:
    """Return EVERY class the commit touches, not just the highest.

    A commit editing scripts/ AND platforms/alipay/facts.md is both tooling
    and data; keeping only "tooling" silently dropped the data trigger for
    manual verification (codex probe).
    """
    classes: set[str] = set()
    for path in paths:
        for prefixes, label in PATH_CLASSES:
            if path.startswith(prefixes):
                classes.add(label)
                break
    return classes


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


PLATFORM_TOKEN = r"(?:alipay(?:\s*/\s*douyin)?|douyin(?:\s*/\s*alipay)?)"
PLATFORM_VERIFICATION_RE = re.compile(
    PLATFORM_TOKEN
    + r"\s+facts\s+人工核验于\s*(?P<date>\d{4}-\d{2}-\d{2})"
    + r"(?:\s*\([^)]*tag[:：]\s*(?P<tag>[v0-9.]+)[^)]*\))?",
    re.IGNORECASE,
)


def changelog_verification_evidence(root: Path, since_tag: str | None) -> dict[str, dict[str, str | None]]:
    """Parse per-platform manual-verification evidence from this cycle's CHANGELOG.

    Returns {platform: {date, tag}}. A single douyin line must never satisfy
    alipay (the global-boolean bug, codex sixth audit); a tag that does not
    equal the candidate tag is not evidence for this release; the evidence
    date must also match every facts.md verified date for that platform.
    """
    changelog = root / "CHANGELOG.md"
    empty: dict[str, dict[str, str | None]] = {}
    if not changelog.is_file():
        return empty
    text = changelog.read_text(encoding="utf-8")
    if since_tag:
        version = since_tag.lstrip("v")
        # match the version header with or without a trailing suffix
        # ("## 3.1.6 - date" or "## 3.1.6\n"); a bare "## 3.1.6 " with a
        # trailing space missed headers written without one.
        for marker in (f"\n## {version} ", f"\n## {version}\n"):
            idx = text.find(marker)
            if idx > 0:
                text = text[: idx + 1]
                break
    else:
        first = text.find("\n## ")
        if first >= 0:
            second = text.find("\n## ", first + 1)
            text = text[first:second] if second > 0 else text[first:]
    evidence: dict[str, dict[str, str | None]] = {}
    for m in PLATFORM_VERIFICATION_RE.finditer(text):
        entry = {"date": m.group("date"), "tag": m.group("tag")}
        matched = m.group(0).lower()
        for platform in MANUAL_ONLY_PLATFORMS:
            if platform in matched:
                evidence[platform] = dict(entry)
    return evidence


def _valid_utc_date(value: str | None) -> bool:
    if not value:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def manual_verification_status(
    root: Path,
    level: str,
    classes: dict[str, int],
    since_tag: str | None = None,
    candidate_tag: str | None = None,
) -> dict[str, Any]:
    """Check manual-only platform fact verification against the release policy.

    Evidence is per-platform, from THIS cycle's CHANGELOG block, and must
    carry the candidate tag (option a). Checks per platform:
    - evidence exists for THIS platform (a douyin line never covers alipay)
    - evidence tag == candidate tag when a candidate is supplied
    - evidence date is a valid UTC date
    - every facts.md verified date for the platform == evidence date
    Level rules: major requires both platforms; minor requires platforms that
    are stale (>90d) or touched by this release (data class); patch requires
    platforms whose facts this release touches.
    """
    now = datetime.now(timezone.utc)
    evidence = changelog_verification_evidence(root, since_tag)
    details: dict[str, Any] = {}
    required = False
    for platform in MANUAL_ONLY_PLATFORMS:
        facts_path = root / "platforms" / platform / "facts.md"
        if not facts_path.is_file():
            # Platform directory absent in this tree (fixture or trimmed repo):
            # no facts to verify. Structural completeness (all bundled platforms
            # present) is enforced by validate_suite's rule-map/facts binding,
            # not by the verification gate.
            details[platform] = {"status": "no-facts-file", "needs_verification": False,
                                 "why": ["platform not present in this tree"]}
            continue
        verified_dates = [
            m.group("verified")
            for m in FACT_ANNOTATION.finditer(facts_path.read_text(encoding="utf-8"))
        ]
        unknown = [v for v in verified_dates if v == "unknown"]
        dated = []
        for value in verified_dates:
            try:
                dated.append(datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc))
            except ValueError:
                continue
        oldest = min(dated) if dated else None

        # does this release REQUIRE verification for this platform?
        must_verify = False
        trigger = ""
        if level == "major":
            must_verify = True
            trigger = "major release requires both manual-only platforms"
        elif level == "minor":
            if classes.get("data"):
                must_verify = True
                trigger = "this release touches platform fact data"
            elif oldest is None or now - oldest > timedelta(days=VERIFICATION_MAX_AGE_DAYS):
                must_verify = True
                trigger = f"last verification older than {VERIFICATION_MAX_AGE_DAYS} days"
        elif classes.get("data"):
            must_verify = True
            trigger = "this release touches platform fact data"

        if not must_verify:
            details[platform] = {
                "needs_verification": False,
                "why": ["no verification trigger for this platform at this level"],
                "unknown_count": len(unknown),
                "oldest_verified": oldest.date().isoformat() if oldest else None,
            }
            continue

        why: list[str] = [trigger]
        ev = evidence.get(platform)
        if ev is None:
            why.append(f"no {platform} evidence line in this cycle's CHANGELOG")
        else:
            if candidate_tag and ev.get("tag") != candidate_tag:
                why.append(f"evidence tag {ev.get('tag')} != candidate {candidate_tag}")
            if not _valid_utc_date(ev.get("date")):
                why.append("evidence date is not a valid UTC date")
            # every fact's verified date must equal the evidence date
            mismatched = [v for v in verified_dates if v != ev.get("date")]
            if mismatched:
                why.append(f"{len(mismatched)} fact(s) verified date != evidence date {ev.get('date')}")
        if unknown:
            why.append(f"{len(unknown)} fact(s) still verified=unknown")
        needs = bool(why[1:]) or bool(unknown)
        if needs:
            required = True
        details[platform] = {
            "needs_verification": needs,
            "why": why,
            "unknown_count": len(unknown),
            "oldest_verified": oldest.date().isoformat() if oldest else None,
        }
    return {"required": required, "platforms": details, "evidence": evidence}


def recommend(root: Path, min_data_changes: int, candidate_tag: str | None = None) -> dict[str, Any]:
    baseline_tag: str | None
    if candidate_tag:
        # A release candidate needs its parent and prior tags. In a depth-1
        # checkout the candidate is a grafted root, so classifying it would
        # treat the whole tree as one change and fabricate the release scope.
        if is_shallow_repository(root):
            return {
                "recommendation": "MANUAL_VERIFICATION_REQUIRED",
                "level": None,
                "reasons": ["shallow repository history is incomplete; fetch full history and tags"],
                "tag": candidate_tag,
                "baseline_tag": None,
                "commit_count": 0,
                "classes": {},
                "history_complete": False,
                "manual_verification": {"required": True, "platforms": {}, "evidence": {}},
            }
        # Release checkout: HEAD sits on the candidate tag. The baseline must be
        # the tag BEFORE the candidate (via its parent), never the candidate
        # itself; and HEAD must actually be the candidate commit.
        candidate_commit = tag_commit(root, candidate_tag)
        current_head = head_commit(root)
        if candidate_commit is None:
            return {"recommendation": "MANUAL_VERIFICATION_REQUIRED", "level": None,
                    "reasons": [f"candidate tag {candidate_tag} not found in repository"],
                    "tag": candidate_tag, "baseline_tag": None, "commit_count": 0, "classes": {},
                    "history_complete": True,
                    "manual_verification": {"required": True, "platforms": {}, "evidence": {}}}
        if current_head != candidate_commit:
            return {"recommendation": "MANUAL_VERIFICATION_REQUIRED", "level": None,
                    "reasons": [f"HEAD {str(current_head)[:8]} != candidate tag commit {candidate_commit[:8]}"],
                    "tag": candidate_tag, "baseline_tag": None, "commit_count": 0, "classes": {},
                    "history_complete": True,
                    "manual_verification": {"required": True, "platforms": {}, "evidence": {}}}
        baseline_tag = last_tag(root, before=f"{candidate_tag}^") or last_tag(root, before=candidate_tag)
        if baseline_tag == candidate_tag:
            baseline_tag = None
        if baseline_tag is None:
            return {
                "recommendation": "MANUAL_VERIFICATION_REQUIRED",
                "level": None,
                "reasons": ["no preceding release tag found for candidate; release history is incomplete"],
                "tag": candidate_tag,
                "baseline_tag": None,
                "commit_count": 0,
                "classes": {},
                "history_complete": False,
                "manual_verification": {"required": True, "platforms": {}, "evidence": {}},
            }
        tag = baseline_tag
    else:
        tag = last_tag(root)
    commits = collect_commits(root, tag)
    if not commits:
        if candidate_tag:
            # A candidate release with zero commits since baseline is anomalous
            # (double-tagged or mis-sequenced): must block, not HOLD-through.
            return {"recommendation": "MANUAL_VERIFICATION_REQUIRED", "level": None,
                    "reasons": ["no commits between baseline tag and candidate tag"],
                    "tag": tag, "baseline_tag": tag, "commit_count": 0, "classes": {},
                    "history_complete": True,
                    "manual_verification": {"required": True, "platforms": {}, "evidence": {}}}
        return {"recommendation": "HOLD", "level": None, "reasons": ["no-commits-since-last-tag"], "tag": tag,
                "baseline_tag": None, "commit_count": 0, "classes": {}}

    classes: dict[str, int] = {}
    for commit in commits:
        # Full class SET per commit: a scripts+facts commit counts as both
        # tooling and data, so the data trigger for manual verification cannot
        # be swallowed by the higher-ranked label (codex probe).
        for label in classify_commit_classes(commit["paths"]):
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
                "tag": tag, "baseline_tag": tag, "commit_count": len(commits), "classes": classes,
                "history_complete": True,
            }
        level = "patch"
        reasons = [f"{classes['data']} commit(s) of platform fact data only; no behavior or methodology changes"]
    else:
        return {
            "recommendation": "HOLD",
            "level": None,
            "reasons": ["only documentation/asset changes; release on demand, not required"],
            "tag": tag, "baseline_tag": tag, "commit_count": len(commits), "classes": classes,
            "history_complete": True,
        }

    verification = manual_verification_status(root, level, classes, since_tag=tag, candidate_tag=candidate_tag)
    if verification["required"]:
        return {
            "recommendation": "MANUAL_VERIFICATION_REQUIRED",
            "level": level,
            "reasons": reasons + [
                f"{platform}: {'; '.join(detail['why'])}"
                for platform, detail in verification["platforms"].items()
                if detail.get("needs_verification")
            ],
            "tag": tag,
            "baseline_tag": tag,
            "commit_count": len(commits),
            "classes": classes,
            "history_complete": True,
            "manual_verification": verification,
        }

    return {
        "recommendation": "RECOMMEND_RELEASE",
        "level": level,
        "reasons": reasons,
        "tag": tag,
        "baseline_tag": tag,
        "commit_count": len(commits),
        "classes": classes,
        "history_complete": True,
        "manual_verification": verification,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("."), help="Repository root")
    parser.add_argument("--min-data-changes", type=int, default=1, help="Minimum data commits for a patch release")
    parser.add_argument("--candidate-tag", help="Tag being released (e.g. v3.1.7); verification evidence must carry this tag")
    parser.add_argument("--format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)
    try:
        report = recommend(args.root.resolve(), args.min_data_changes, candidate_tag=args.candidate_tag)
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
