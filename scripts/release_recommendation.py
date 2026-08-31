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

from evidence_signature import SignatureError, verify_signed_document


LEVELS = ("patch", "minor", "major")
LEVEL_RANK = {"patch": 0, "minor": 1, "major": 2}
MANUAL_ONLY_PLATFORMS = ("alipay", "douyin")
VERIFICATION_MAX_AGE_DAYS = 90
FACT_ANNOTATION = re.compile(
    r"<!--\s*fact:\s*\S+\s+verified=(?P<verified>[^\s]+)\s+source=\S+\s+digest=\S+\s*-->"
)
# Conventional-commit breaking markers: a subject like "feat!:" or any
# "BREAKING CHANGE" mention classifies the whole release as major.
BREAKING_SUBJECT = re.compile(r"BREAKING[ -]CHANGE|^\w+!:", re.IGNORECASE)
# New tooling CAPABILITY (feat:) is a compatible addition -> minor; tooling
# fixes (fix:/chore:/test:/refactor:) stay patch (audit P1-02 five classes:
# metadata / behavior-body / tooling-fix / compatible-addition / breaking).
FEATURE_SUBJECT = re.compile(r"^(feat|add|新增)\b", re.IGNORECASE)
# Root SKILL.md frontmatter lines that are release METADATA, not behavior:
# bumping version/last_reviewed must not force a minor release (audit P1-02).
ROOT_SKILL_METADATA_LINE = re.compile(r"^[+-]\s*(?:version|last_reviewed):")
# Path prefixes that classify the character of a change. Checked in order of severity.
# VERSION is release metadata (its own class); root SKILL.md starts in
# "behavior" but is reclassified to "metadata" when its diff only touches
# version/last_reviewed lines (see root_skill_change_is_metadata_only).
PATH_CLASSES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("SKILL.md", "skills/", "shared/"), "behavior"),
    (("scripts/", "install.sh", ".github/", "tests/", "agents/", "references/"), "tooling"),
    (("platforms/",), "data"),
    (("VERSION",), "metadata"),
    (("README", "CHANGELOG", "LICENSE", "COMPATIBILITY", "EVALUATIONS"), "docs"),
    (("assets/",), "assets"),
)


def parse_semver(tag: str) -> tuple[int, int, int] | None:
    """Parse v<major>.<minor>.<patch>; None for anything else."""
    body = tag[1:] if tag.startswith("v") else tag
    parts = body.split(".")
    if len(parts) != 3:
        return None
    try:
        values = tuple(int(part) for part in parts)
    except ValueError:
        return None
    return values  # type: ignore[return-value]


def semver_bump(baseline: str, candidate: str) -> str | None:
    """Return patch/minor/major for baseline->candidate; None when not a strict bump."""
    base = parse_semver(baseline)
    cand = parse_semver(candidate)
    if base is None or cand is None or cand <= base:
        return None
    if cand[0] != base[0]:
        return "major"
    if cand[1] != base[1]:
        return "minor"
    return "patch"


def release_tags_sorted(root: Path) -> list[str]:
    """All v<x.y.z> tags sorted by semver (ascending)."""
    result = subprocess.run(
        ["git", "-C", str(root), "tag", "--list", "v*"],
        capture_output=True, check=False, text=True,
    )
    parsed: list[tuple[tuple[int, int, int], str]] = []
    for line in result.stdout.splitlines():
        tag = line.strip()
        value = parse_semver(tag) if tag else None
        if value is not None:
            parsed.append((value, tag))
    return [tag for _, tag in sorted(parsed)]


def root_skill_change_is_metadata_only(root: Path, commit_hash: str) -> bool:
    """True when this commit's root SKILL.md diff only moves version metadata.

    The behavior class otherwise fires on ANY root SKILL.md edit, so a pure
    version bump was misclassified as a behavior change and forced minor
    releases (audit P1-02: v3.1.9 was released as patch while the gate
    summary said minor).
    """
    diff = git(root, "show", "--format=", "--unified=0", commit_hash, "--", "SKILL.md")
    changed = [
        line
        for line in diff.splitlines()
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]
    if not changed:
        return True
    return all(ROOT_SKILL_METADATA_LINE.match(line) for line in changed)


def commit_paths_are_metadata_only(root: Path, commit_hash: str, paths: list[str]) -> bool:
    """True when this commit's root SKILL.md edit only moves release metadata.

    The release-prep commit bumps VERSION + root SKILL.md frontmatter and often
    carries tooling/docs edits in the same commit. The QUESTION this answers is
    narrow: did the BEHAVIOR-classified content (root SKILL.md) actually change
    behaviorally? If SKILL.md only moved version/last_reviewed lines, its
    behavior class is reclassified to metadata even when the same commit also
    touches scripts or docs — those keep their own classes (audit P1-02).
    """
    if not any(path == "SKILL.md" for path in paths):
        return False
    return root_skill_change_is_metadata_only(root, commit_hash)


def load_downgrade_override(root: Path, candidate_tag: str, required_level: str) -> dict[str, Any] | None:
    """Load and validate a structured manual downgrade (release-override.json).

    A downgrade may lower the required level by exactly one step (major->minor
    or minor->patch), must name THIS candidate tag, and must carry a reason and
    an independent signer. Anything else is rejected (returns None and the
    original level stands) — never a silent pass.
    """
    path = root / "release-override.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"accepted": False, "problems": ["override-unreadable"]}
    if not isinstance(data, dict):
        return {"accepted": False, "problems": ["override-not-object"]}
    problems: list[str] = []
    try:
        signer_key_id = verify_signed_document(
            data,
            root / ".github" / "release-evidence" / "trusted-signers.pem",
            expected_key_id="release-evaluation-2026-08-31",
        )
    except SignatureError as exc:
        signer_key_id = None
        problems.append(f"override-{exc}")
    target = data.get("to")
    allowed = {"major": "minor", "minor": "patch"}
    if not isinstance(data.get("reason"), str) or not data["reason"].strip():
        problems.append("override-reason-missing")
    if not isinstance(data.get("signed_by"), str) or not data["signed_by"].strip():
        problems.append("override-signer-missing")
    else:
        try:
            candidate_author = git(root, "show", "-s", "--format=%ae", candidate_tag).strip()
        except ValueError:
            candidate_author = ""
        if candidate_author and data["signed_by"].strip().casefold() == candidate_author.casefold():
            problems.append("override-signer-not-independent")
    if data.get("candidate_tag") != candidate_tag:
        problems.append("override-candidate-tag-mismatch")
    if data.get("from") != required_level or target != allowed.get(required_level):
        problems.append("override-not-one-step-downgrade")
    if problems:
        return {"accepted": False, "problems": problems}
    return {
        "accepted": True,
        "from": required_level,
        "to": target,
        "reason": data["reason"].strip(),
        "signed_by": data["signed_by"].strip(),
        "signer_key_id": signer_key_id,
        "candidate_tag": candidate_tag,
    }


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
    ranking = {"behavior": 5, "tooling": 3, "data": 2, "metadata": 1, "docs": 1, "assets": 1}
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


def recommend(root: Path | str, min_data_changes: int, candidate_tag: str | None = None) -> dict[str, Any]:
    root = Path(root)
    baseline_tag: str | None
    # Every recommendation mode needs real history. Without this common guard,
    # no-candidate callers (notably drift_audit in Actions) treat a depth-1
    # checkout as a root commit, classify the entire tree, and falsely report
    # history_complete=true.
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
    if candidate_tag:
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
                "baseline_tag": None, "commit_count": 0, "classes": {}, "history_complete": True}

    classes: dict[str, int] = {}
    for commit in commits:
        # Full class SET per commit: a scripts+facts commit counts as both
        # tooling and data, so the data trigger for manual verification cannot
        # be swallowed by the higher-ranked label (codex probe).
        commit_classes = classify_commit_classes(commit["paths"])
        # Release-metadata-only commits (VERSION + root SKILL.md frontmatter
        # version bump) are reclassified to metadata, not behavior (P1-02).
        if "behavior" in commit_classes:
            if commit_paths_are_metadata_only(root, commit["hash"], commit["paths"]):
                commit_classes.discard("behavior")
                commit_classes.add("metadata")
        # Conventional breaking markers upgrade the whole release to major.
        if BREAKING_SUBJECT.search(commit.get("subject") or ""):
            commit_classes.add("breaking")
        # A tooling commit that ADDS capability (feat:) is a compatible
        # addition (minor); tooling fixes stay fix-class (patch).
        if "tooling" in commit_classes and FEATURE_SUBJECT.match(commit.get("subject") or ""):
            commit_classes.add("feature")
        for label in commit_classes:
            classes[label] = classes.get(label, 0) + 1

    # Explicit breaking changes always mean major.
    if classes.get("breaking"):
        level = "major"
        reasons = [f"{classes['breaking']} commit(s) carry breaking-change markers"]
    elif classes.get("behavior"):
        level = "minor"
        reasons = [f"{classes['behavior']} commit(s) touch skill text, guardrails, or the root skill (behavior changes)"]
    elif classes.get("feature"):
        level = "minor"
        reasons = [f"{classes['feature']} commit(s) add compatible tooling capability (feat)"]
    elif classes.get("tooling"):
        level = "patch"
        reasons = [f"{classes['tooling']} commit(s) fix scripts, installer, CI, or tests (tooling fixes)"]
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
        # Version-metadata-only commits (VERSION bump + root SKILL.md
        # version/last_reviewed) release as patch (audit P1-02).
        if classes.get("metadata"):
            level = "patch"
            reasons = [f"{classes['metadata']} commit(s) touch release metadata only (VERSION / frontmatter version fields)"]
        else:
            return {
                "recommendation": "HOLD",
                "level": None,
                "reasons": ["only documentation/asset changes; release on demand, not required"],
                "tag": tag, "baseline_tag": tag, "commit_count": len(commits), "classes": classes,
                "history_complete": True,
            }

    # --- SemVer consistency (audit P1-02): the RECOMMENDED level must match
    # the candidate tag's real increment over the baseline. A release whose
    # actual increment is SMALLER than required blocks; a larger increment is
    # allowed (a patch-worthy change shipped as minor is safe, not silent).
    semver: str | None = None
    required_level: str = level
    downgrade: dict[str, Any] | None = None
    if candidate_tag:
        semver = semver_bump(tag, candidate_tag) if tag else None
        if semver is None:
            return {
                "recommendation": "MANUAL_VERIFICATION_REQUIRED",
                "level": level,
                "reasons": [
                    f"candidate tag {candidate_tag} is not a strict semver bump of baseline {tag or 'none'} "
                    "(equal, lower, or non-semver); release blocked"
                ],
                "tag": tag, "baseline_tag": tag, "commit_count": len(commits), "classes": classes,
                "history_complete": True,
                "semver_bump": None,
                "required_level": level,
                "manual_verification": {"required": True, "platforms": {}, "evidence": {}},
            }
        if LEVEL_RANK[semver] < LEVEL_RANK[level]:
            downgrade = load_downgrade_override(root, candidate_tag, level)
            if downgrade is None or not downgrade.get("accepted"):
                return {
                    "recommendation": "MANUAL_VERIFICATION_REQUIRED",
                    "level": level,
                    "reasons": [
                        f"semver bump {semver} is lower than required level {level}; "
                        "provide a structured one-step downgrade (release-override.json with reason and "
                        "independent signer) or retag at the required level"
                    ] + (downgrade or {}).get("problems", []),
                    "tag": tag, "baseline_tag": tag, "commit_count": len(commits), "classes": classes,
                    "history_complete": True,
                    "semver_bump": semver,
                    "required_level": level,
                    "override": downgrade,
                    "manual_verification": {"required": True, "platforms": {}, "evidence": {}},
                }
            required_level = downgrade["to"]
    base_result = {
        "tag": tag,
        "baseline_tag": tag,
        "commit_count": len(commits),
        "classes": classes,
        "history_complete": True,
        "semver_bump": semver,
        "required_level": required_level,
    }
    if downgrade and downgrade.get("accepted"):
        base_result["override"] = downgrade

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
            **base_result,
            "manual_verification": verification,
        }

    return {
        "recommendation": "RECOMMEND_RELEASE",
        "level": level,
        "reasons": reasons,
        **base_result,
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
