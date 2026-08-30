#!/usr/bin/env python3
"""Run L2 extraction and shadow-mode proposal review for detected drift.

Executed in CI after deterministic detection (drift_watch): for every platform
with actionable rules, fetch and extract via the pluggable engine (L2), build
the redacted proposal, then run the deterministic gates plus faithfulness
audits in shadow mode. One issue per platform carries the binary verdict
(RECOMMEND_MERGE / DO_NOT_MERGE) with per-rule evidence; nothing merges
automatically while shadow mode is on. Engine credentials arrive via
environment (AGENT_API_*); they are never printed or written into reports.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import platform_drift  # noqa: E402
import release_recommendation  # noqa: E402
import review_drift_proposal  # noqa: E402
from drift_watch import AUDIT_ACTIONABLE, actionable, existing_open_issues, gh_available  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def audit_platform(platform_root: Path, rounds: int, out_dir: Path | None) -> dict[str, Any]:
    """Run L2 + review for one platform and return a redacted audit summary."""
    report = platform_drift.run(platform_root, None, False)
    platform = report["platform"]
    items = actionable(report["results"], AUDIT_ACTIONABLE)
    summary: dict[str, Any] = {
        "platform": platform,
        "audited_at_utc": utc_now(),
        "rules": [],
        "verdict": "NO_ACTIONABLE_DRIFT",
    }
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{platform}-drift-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if not items:
        return summary

    proposal = report.get("proposal")
    if not proposal or not proposal.get("changes"):
        summary["verdict"] = "MANUAL_REVIEW"
        summary["reason"] = "no-proposal-unverifiable"

        def redact(text: str) -> str:
            # Issue bodies are public; keep reason codes only, never raw content.
            cleaned = (
                str(text).split(":", 1)[-1]
                if str(text).startswith(("l2-failed:", "fetch-failed:"))
                else str(text)
            )
            return cleaned[:80]

        summary["rules"] = [
            {"rule_id": item["rule_id"], "state": item["state"], "detail": redact(item.get("error", ""))}
            for item in items
        ]
        return summary

    proposal_path = out_dir / f"{platform}-proposal.json" if out_dir else Path("/tmp") / f"{platform}-proposal.json"
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text(
        json.dumps(proposal, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    drift_report_path = out_dir / f"{platform}-drift-report.json" if out_dir else Path("/tmp") / f"{platform}-drift-report.json"
    if not drift_report_path.is_file():
        drift_report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    review = review_drift_proposal.review(proposal_path, platform_root, drift_report_path, rounds, shadow=True)
    summary["verdict"] = review["verdict"]
    summary["problems"] = review["problems"]
    summary["audit_rounds"] = [
        {"label": entry["label"], "verdict": entry.get("verdict"), "error": entry.get("error")}
        for entry in review.get("audits", [])
    ]
    summary["engine"] = review.get("engine", {})
    summary["rules"] = [
        {
            "rule_id": change["rule_id"],
            "state": change["state"],
            "new_digest": change["new_digest"],
            "reason": change.get("reason"),
        }
        for change in proposal["changes"]
    ]
    return summary


def render_issue_body(summary: dict[str, Any]) -> str:
    lines = [
        "Automated Saturday audit (L2 extraction + shadow-mode review).",
        "",
        f"- Platform: {summary['platform']}",
        f"- Overall verdict: **{summary['verdict']}**",
        f"- Audited at (UTC): {summary['audited_at_utc']}",
        "",
        "| Rule | State | New digest |",
        "| --- | --- | --- |",
    ]
    for rule in summary.get("rules", []):
        lines.append(f"| {rule['rule_id']} | {rule['state']} | {str(rule.get('new_digest', '-'))[:12]}… |")
    if summary.get("problems"):
        lines += ["", "Gate problems:"]
        lines += [f"- {problem}" for problem in summary["problems"]]
    if summary.get("audit_rounds"):
        lines += ["", "Faithfulness audit rounds:"]
        lines += [
            f"- {entry['label']}: {entry['verdict'] or entry.get('error')}" for entry in summary["audit_rounds"]
        ]
    lines += [
        "",
        "Shadow mode is ON: this verdict reports only; the author merges manually after inspecting the diff.",
        "",
        "Release recommendation right now:",
        "```",
    ]
    try:
        lines.append(release_recommendation.recommend(Path.cwd(), 1)["recommendation"])
    except Exception:
        lines.append("unavailable")
    lines += ["```"]
    return "\n".join(lines)


def emit_issues(summaries: list[dict[str, Any]], repo: str | None) -> int:
    """Open one verdict issue per audited platform; idempotent per title."""
    if not gh_available():
        print(json.dumps({"emit_issues": "skipped", "reason": "no-github-token"}, ensure_ascii=False))
        return 0
    existing = existing_open_issues("[Drift-audit]")
    opened = 0
    for summary in summaries:
        title = f"[Drift-audit] {summary['platform']}: {summary['verdict']}"
        if title in existing:
            continue
        body = render_issue_body(summary)
        command = ["gh", "issue", "create", "--title", title, "--body", body, "--label", "drift"]
        if repo:
            command += ["--repo", repo]
        result = subprocess.run(command, capture_output=True, check=False, text=True)
        if result.returncode == 0:
            opened += 1
        else:
            print(f"issue-create-failed:{summary['platform']}:{result.stderr.strip()[:200]}")
    print(json.dumps({"emit_issues": "done", "opened": opened}, ensure_ascii=False))
    return 0


def audit_targets(platforms_root: Path, only: Path | None, report: Path | None) -> tuple[list[Path], list[str]]:
    """Resolve which platform dirs to audit; manual-only platforms are never audited.

    The audit stage re-checks platforms named in the detection report (when
    provided) or under platforms/ (when not), minus manual-only layers: their
    digests are unknown by policy, so L2 against client-rendered shells is
    guaranteed to fail and would burn engine calls every scheduled run.
    """
    if only is not None:
        candidates = [only.resolve()]
    elif report is not None:
        detection = json.loads(report.read_text(encoding="utf-8"))
        names = [block["platform"] for block in detection.get("platforms", [])]
        candidates = [platforms_root / name for name in names]
    else:
        candidates = (
            sorted(p for p in platforms_root.iterdir() if p.is_dir() and (p / "rule-map.json").is_file())
            if platforms_root.is_dir()
            else []
        )
    roots: list[Path] = []
    skipped: list[str] = []
    for candidate in candidates:
        if not candidate.is_dir():
            skipped.append(f"missing-platform-dir:{candidate.name}")
            continue
        rule_map_path = candidate / "rule-map.json"
        if not rule_map_path.is_file():
            skipped.append(f"missing-rule-map:{candidate.name}")
            continue
        try:
            rule_map = json.loads(rule_map_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped.append(f"unreadable-rule-map:{candidate.name}")
            continue
        if rule_map.get("detection") == "manual-only":
            skipped.append(f"manual-only:{candidate.name}")
            continue
        roots.append(candidate)
    return roots, skipped


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-dir", type=Path, help="Audit only platforms/<name>")
    parser.add_argument("--rounds", type=int, default=3, help="Faithfulness audit rounds")
    parser.add_argument("--report", type=Path, help="Consume the detect job's drift report to bound the audit scope")
    parser.add_argument("--out-dir", type=Path, help="Directory for reports and proposals")
    parser.add_argument("--emit-issues", action="store_true", help="Open one verdict issue per platform")
    parser.add_argument("--repo", help="Optional repo (owner/name) for gh commands")
    args = parser.parse_args(argv)

    roots, skipped = audit_targets(Path.cwd() / "platforms", args.platform_dir, args.report)
    if not roots:
        print(
            json.dumps(
                {"error": "no-auditable-platforms", "skipped": skipped},
                ensure_ascii=False,
            )
        )
        return 2
    if skipped:
        print(json.dumps({"audit_skipped": skipped}, ensure_ascii=False))
    summaries = []
    for root in roots:
        try:
            summaries.append(audit_platform(root, args.rounds, args.out_dir))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            summaries.append({"platform": root.name, "verdict": "MANUAL_REVIEW", "reason": f"audit-failed:{type(exc).__name__}", "rules": []})
    payload = {"generated_at_utc": utc_now(), "summaries": summaries}
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "audit-summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if args.emit_issues:
        return emit_issues(summaries, args.repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
