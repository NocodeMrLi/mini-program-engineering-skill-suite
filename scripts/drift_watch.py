#!/usr/bin/env python3
"""Deterministic drift detection orchestration (the detect stage).

Wraps platform_drift's L0/L1 checks for every platforms/<name>/ directory:
- detection is always deterministic here: fingerprints only, no LLM calls
  (``--no-llm`` documents this explicitly; there is no L2 path in this tool);
- findings become one GitHub issue per actionable rule via ``--emit-issues``
  (uses the repository's Platform rule drift template fields);
- a missing or unreadable rule map fails closed (exit 2).

L2 extraction and consistency review live in drift_audit.py. That
stage runs in CI with the AGENT_API_* secrets configured by the author (see
.github/workflows/drift-watch.yml) or locally with any CLI engine — the
workflow degrades to detection-only when the secrets are absent.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import platform_drift  # noqa: E402
from platform_drift import check_rule, load_fact_annotations, load_json  # noqa: E402


class L2Blocked(Exception):
    """Raised instead of running an LLM extraction when deterministic mode forbids it."""


def deterministic_check(platform_root: Path) -> dict[str, Any]:
    """Run L0/L1 for one platform; L2 is blocked so the path stays token-free."""

    def blocked_run_agent(cwd, prompt):  # noqa: ANN001, ANN202
        raise L2Blocked()

    original_run_agent = platform_drift.run_agent
    platform_drift.run_agent = blocked_run_agent
    try:
        rule_map = load_json(platform_root / "rule-map.json")
        annotations = load_fact_annotations(platform_root / "facts.md")
        results = []
        for rule in rule_map["rules"]:
            try:
                outcome = check_rule(rule, annotations, rule_map["allowed_domains"], force_l2=False)
            except L2Blocked:
                # L1 says the fingerprint changed (or was never recorded) and L2 is
                # forbidden here: surface it as actionable without any model call.
                outcome = {
                    "rule_id": rule["id"],
                    "state": "fingerprint-changed",
                    "reason": "l1-fingerprint-mismatch-or-unrecorded",
                    "url": rule["official"]["url"],
                    "checked_at_utc": utc_now(),
                }
            results.append(outcome)
    finally:
        platform_drift.run_agent = original_run_agent
    counts: dict[str, int] = {}
    for item in results:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    return {
        "platform": rule_map["platform"],
        "checked_at_utc": utc_now(),
        "rule_count": len(results),
        "counts": counts,
        "results": results,
    }

USER_AGENT = "mini-program-engineering-suite-drift-watch/1.0 (weekly CI; low frequency)"
REQUEST_TIMEOUT_SECONDS = 30


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def platform_dirs(root: Path, only: str | None) -> list[Path]:
    platforms = root / "platforms"
    if not platforms.is_dir():
        return []
    dirs = []
    for candidate in sorted(p for p in platforms.iterdir() if p.is_dir() and (p / "rule-map.json").is_file()):
        rule_map = json.loads((candidate / "rule-map.json").read_text(encoding="utf-8"))
        # manual-only platforms (client-rendered SPA docs) cannot be observed by
        # deterministic fingerprints; watching them weekly would only create noise.
        if rule_map.get("detection") == "manual-only":
            continue
        dirs.append(candidate)
    if only:
        dirs = [p for p in dirs if p.name == only]
    return dirs


def manual_only_platforms(root: Path) -> list[Path]:
    """Every platform whose rule-map declares detection=manual-only."""
    platforms = root / "platforms"
    if not platforms.is_dir():
        return []
    result = []
    for candidate in sorted(p for p in platforms.iterdir() if p.is_dir() and (p / "rule-map.json").is_file()):
        rule_map = json.loads((candidate / "rule-map.json").read_text(encoding="utf-8"))
        if rule_map.get("detection") == "manual-only":
            result.append(candidate)
    return result


FACT_VERIFIED = re.compile(r"verified=(\d{4}-\d{2}-\d{2})")


def manual_only_entry(platform_dir: Path) -> dict[str, Any]:
    """One report entry for a platform deterministic detection cannot observe.

    These platforms must STAY VISIBLE in the report with state
    not-automatically-observable (audit P2-02): dropping them silently made
    actionable_count=0 read as "all three platforms have no drift" while two
    of them were never checked.
    """
    facts_path = platform_dir / "facts.md"
    verified_dates: list[str] = []
    if facts_path.is_file():
        verified_dates = FACT_VERIFIED.findall(facts_path.read_text(encoding="utf-8"))
    rule_map = json.loads((platform_dir / "rule-map.json").read_text(encoding="utf-8"))
    urls = sorted({rule.get("official", {}).get("url", "") for rule in rule_map.get("rules", []) if rule.get("official", {}).get("url")})
    return {
        "platform": rule_map.get("platform", platform_dir.name),
        "state": "not-automatically-observable",
        "reason": "manual-only platform: client-rendered docs defeat deterministic fingerprinting",
        "rule_count": len(rule_map.get("rules", [])),
        "last_manual_verification": max(verified_dates) if verified_dates else None,
        "manual_verification_entry_points": urls,
        "next_step": "maintainer opens each official URL and re-verifies verify_points manually",
        "checked_at_utc": utc_now(),
    }


DETECTION_ACTIONABLE = {"fingerprint-changed", "unverifiable"}
AUDIT_ACTIONABLE = {"fingerprint-changed", "unverifiable", "updated", "conflicting"}


def actionable(results: list[dict[str, Any]], states: set[str] | None = None) -> list[dict[str, Any]]:
    """Filter results needing attention; CI detection and full audits use different vocabularies."""
    return [item for item in results if item["state"] in (states or DETECTION_ACTIONABLE)]


def gh_available() -> bool:
    return bool(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))


def existing_open_issues(title_prefix: str) -> set[str]:
    result = subprocess.run(
        ["gh", "issue", "list", "--state", "open", "--json", "title", "--limit", "200"],
        capture_output=True, check=False, text=True,
    )
    if result.returncode:
        return set()
    try:
        return {item["title"] for item in json.loads(result.stdout)}
    except json.JSONDecodeError:
        return set()


def emit_issues(report: dict[str, Any], repo: str | None) -> int:
    """Open one issue per actionable rule; idempotent against open duplicates.

    Returns 1 when any issue creation failed so CI surfaces a broken
    notification chain instead of silently skipping it.
    """
    if not gh_available():
        print(json.dumps({"emit_issues": "skipped", "reason": "no-github-token"}, ensure_ascii=False))
        return 0
    existing = existing_open_issues("[Drift]")
    opened = 0
    failed: list[str] = []
    for platform_block in report["platforms"]:
        for item in actionable(platform_block["results"]):
            title = f"[Drift] {platform_block['platform']}: {item['rule_id']} -> {item['state']}"
            if title in existing:
                continue
            body = (
                f"Automated weekly drift watch (deterministic L0/L1 only).\n\n"
                f"- Platform: {platform_block['platform']}\n"
                f"- Rule id: {item['rule_id']}\n"
                f"- State: {item['state']}\n"
                f"- Source: {item.get('url', 'n/a')}\n"
                f"- Checked at (UTC): {item.get('checked_at_utc')}\n"
                f"- Detail: {item.get('error') or item.get('reason', 'fingerprint changed vs facts.md')}\n\n"
                f"Next step (maintainer, local): run L2 extraction and the consistency reviewer:\n"
                f"```bash\n"
                f"python3 scripts/platform_drift.py platforms/{platform_block['platform']} --rule {item['rule_id']} --proposal-out /tmp/proposal.json\n"
                f"python3 scripts/review_drift_proposal.py /tmp/proposal.json --platform-root platforms/{platform_block['platform']} --drift-report /tmp/drift.json\n"
                f"```\n"
                f"No auto-merge exists: the reviewer's PROPOSAL_CONSISTENT_WITH_EXTRACTION only bounds the draft "
                f"to the model extraction; the author must verify the official page before applying anything."
            )
            command = ["gh", "issue", "create", "--title", title, "--body", body, "--label", "drift"]
            if repo:
                command += ["--repo", repo]
            result = subprocess.run(command, capture_output=True, check=False, text=True)
            if result.returncode == 0:
                opened += 1
            else:
                failed.append(item["rule_id"])
                print(f"issue-create-failed:{item['rule_id']}:{result.stderr.strip()[:200]}")
    print(json.dumps({"emit_issues": "done", "opened": opened, "failed": failed}, ensure_ascii=False))
    return 1 if failed else 0


def run(root: Path, only: str | None, no_llm: bool) -> dict[str, Any] | None:
    dirs = platform_dirs(root, only)
    manual = manual_only_platforms(root)
    if only:
        # Explicit scope: manual-only entries narrow to the named platform.
        manual = [d for d in manual if d.name == only]
    if not dirs and not manual:
        return None
    # Detection in this tool is deterministic by construction; the flag is kept
    # for CLI compatibility and the mode field always states the truth.
    report: dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "mode": "deterministic",
        "llm_stage": "drift_audit.py (detection never calls engines)",
        # Coverage accounting (audit P2-02): actionable_count=0 must never be
        # readable as "no platform drifted" when manual-only platforms were
        # never deterministically checked. They stay in the report.
        "platform_total": len(dirs) + len(manual),
        "automatically_checked": len(dirs),
        "manual_only": len(manual),
        "platforms": [deterministic_check(d) for d in dirs],
        "manual_only_platforms": [manual_only_entry(d) for d in manual],
    }
    if only:
        # An explicit --platform-dir narrows THIS run's scope; the counters then
        # describe the narrowed scope, and skipped_platforms records what was
        # left out so the narrowing can never hide a platform silently.
        included = {d.name for d in dirs} | {d.name for d in manual}
        all_platforms = {
            p.name for p in (root / "platforms").iterdir()
            if p.is_dir() and (p / "rule-map.json").is_file()
        }
        report["skipped_platforms"] = sorted(all_platforms - included)
    report["actionable_count"] = sum(len(actionable(p["results"])) for p in report["platforms"])
    return report


def explicit_manual_only_message(root: Path, only: str | None) -> str | None:
    """Clear guidance when --platform-dir names a manual-only platform.

    The flag used to fall through to no-platform-dirs (exit 2), which reads
    like a tooling error instead of the truth: this platform is deliberately
    not deterministically observable (audit P2-02).
    """
    if not only:
        return None
    platform_root = root / "platforms" / only
    rule_map_path = platform_root / "rule-map.json"
    if not rule_map_path.is_file():
        return None
    try:
        rule_map = json.loads(rule_map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rule_map.get("detection") != "manual-only":
        return None
    entry = manual_only_entry(platform_root)
    return json.dumps(
        {
            "platform": only,
            "status": "not-automatically-observable",
            "reason": entry["reason"],
            "rule_count": entry["rule_count"],
            "last_manual_verification": entry["last_manual_verification"],
            "manual_verification_entry_points": entry["manual_verification_entry_points"],
            "next_step": entry["next_step"],
        },
        ensure_ascii=False, indent=2, sort_keys=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-dir", help="Check only platforms/<name> (path or name)")
    parser.add_argument("--no-llm", action="store_true", help="Deterministic L0/L1 only (CI default)")
    parser.add_argument("--output", type=Path, help="Write the JSON report here")
    parser.add_argument("--report", type=Path, help="Read a previous report (for --emit-issues)")
    parser.add_argument("--emit-issues", action="store_true", help="Open GitHub issues for actionable findings")
    parser.add_argument("--repo", help="Optional repo (owner/name) for gh commands")
    args = parser.parse_args(argv)

    if args.emit_issues:
        # Fresh detection run in the same invocation: write/read our own report
        # (the CI detect step passes --output + --emit-issues together; requiring
        # a separate --report file made every first run fail with report-missing).
        only = None
        if args.platform_dir:
            only = Path(args.platform_dir).name
        report = run(Path.cwd(), only, args.no_llm)
        if report is None:
            print(json.dumps({"error": "no-platform-dirs"}, ensure_ascii=False))
            return 2
        if args.output:
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        emit_rc = emit_issues(report, args.repo)
        # Propagate both failure modes: actionable findings AND notification
        # failures must make the job reflect them (issue-create failures used
        # to be swallowed).
        if emit_rc:
            return emit_rc
        return 1 if report["actionable_count"] else 0

    only = None
    if args.platform_dir:
        only = Path(args.platform_dir).name
    report = run(Path.cwd(), only, args.no_llm)
    if report is None:
        # A manual-only platform named explicitly gets structured guidance, not
        # a generic no-platform-dirs error (audit P2-02).
        manual_message = explicit_manual_only_message(Path.cwd(), only)
        if manual_message:
            print(manual_message)
            return 3
        print(json.dumps({"error": "no-platform-dirs"}, ensure_ascii=False))
        return 2
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    # Exit 1 when anything is actionable so CI shows the job as needing attention.
    return 1 if report["actionable_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
