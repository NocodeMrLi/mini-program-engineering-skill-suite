#!/usr/bin/env python3
"""CI orchestration for weekly deterministic drift watching.

Wraps platform_drift's L0/L1 checks for every platforms/<name>/ directory:
- default mode is fully deterministic (``--no-llm``): fingerprints only, no
  extraction, no tokens, no agent credentials in CI;
- findings become one GitHub issue per actionable rule via ``--emit-issues``
  (uses the repository's Platform rule drift template fields);
- a missing or unreadable rule map fails closed (exit 2).

L2 extraction and proposal review always run locally (see platform_drift.py
and review_drift_proposal.py); CI never holds agent credentials.
"""

from __future__ import annotations

import argparse
import json
import os
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


def actionable(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in results if item["state"] in {"fingerprint-changed", "unverifiable"}]


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
    """Open one issue per actionable rule; idempotent against open duplicates."""
    if not gh_available():
        print(json.dumps({"emit_issues": "skipped", "reason": "no-github-token"}, ensure_ascii=False))
        return 0
    existing = existing_open_issues("[Drift]")
    opened = 0
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
                f"Next step (maintainer, local): run L2 extraction and the proposal reviewer:\n"
                f"```bash\n"
                f"python3 scripts/platform_drift.py platforms/{platform_block['platform']} --rule {item['rule_id']} --proposal-out /tmp/proposal.json\n"
                f"python3 scripts/review_drift_proposal.py /tmp/proposal.json --platform-root platforms/{platform_block['platform']} --drift-report /tmp/drift.json\n"
                f"```\n"
                f"Shadow mode is ON: proposals are reported, never auto-merged."
            )
            command = ["gh", "issue", "create", "--title", title, "--body", body, "--label", "drift"]
            if repo:
                command += ["--repo", repo]
            result = subprocess.run(command, capture_output=True, check=False, text=True)
            if result.returncode == 0:
                opened += 1
            else:
                print(f"issue-create-failed:{item['rule_id']}:{result.stderr.strip()[:200]}")
    print(json.dumps({"emit_issues": "done", "opened": opened}, ensure_ascii=False))
    return 0


def run(root: Path, only: str | None, no_llm: bool) -> dict[str, Any] | None:
    dirs = platform_dirs(root, only)
    if not dirs:
        return None
    report: dict[str, Any] = {
        "generated_at_utc": utc_now(),
        "mode": "deterministic" if no_llm else "full",
        "platforms": [deterministic_check(d) for d in dirs],
    }
    report["actionable_count"] = sum(len(actionable(p["results"])) for p in report["platforms"])
    return report


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
        if not args.report or not args.report.is_file():
            print(json.dumps({"error": "report-missing"}, ensure_ascii=False))
            return 2
        return emit_issues(json.loads(args.report.read_text(encoding="utf-8")), args.repo)

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
    # Exit 1 when anything is actionable so CI shows the job as needing attention.
    return 1 if report["actionable_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
