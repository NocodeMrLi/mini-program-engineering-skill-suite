#!/usr/bin/env python3
"""Apply approved platform drift proposals to volatile platform facts.

This script is intentionally narrow: it only updates ``platforms/<platform>/facts.md``
fact text plus the adjacent verification annotation for proposals whose audit
summary says ``PROPOSAL_CONSISTENT_WITH_EXTRACTION``. It never edits rule maps,
methodology text, scripts, tests, or package metadata.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


ANNOTATION = re.compile(
    r"^(?P<indent>\s*)<!--\s*fact:\s*(?P<id>[^\s]+)\s+verified=(?P<verified>[^\s]+)\s+"
    r"source=(?P<source>\S+)\s+digest=(?P<digest>\S+)\s*-->\s*$"
)
FACT_PREFIX = re.compile(r"^(?P<indent>\s*)-\s*事实：(?P<text>.*)$")
PASS_VERDICT = "PROPOSAL_CONSISTENT_WITH_EXTRACTION"


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json-not-object:{path}")
    return value


def approved_platforms(summary_path: Path | None) -> set[str] | None:
    if summary_path is None:
        return None
    summary = load_json(summary_path)
    approved: set[str] = set()
    for item in summary.get("summaries", []):
        if isinstance(item, dict) and item.get("verdict") == PASS_VERDICT:
            platform = item.get("platform")
            if isinstance(platform, str) and platform:
                approved.add(platform)
    return approved


def proposal_verified_date(proposal: dict[str, Any], fallback: str) -> str:
    generated = str(proposal.get("generated_at_utc") or "")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", generated):
        return generated[:10]
    return fallback


def collect_updates(proposal: dict[str, Any]) -> tuple[str, str, dict[str, dict[str, str]]]:
    if proposal.get("format_version") != 2:
        raise ValueError("proposal-format-invalid")
    platform = proposal.get("platform")
    if not isinstance(platform, str) or not platform:
        raise ValueError("proposal-platform-invalid")
    updates: dict[str, dict[str, str]] = {}
    verified_date = proposal_verified_date(proposal, utc_today())
    for change in proposal.get("changes", []):
        if not isinstance(change, dict):
            raise ValueError("proposal-change-invalid")
        rule_id = change.get("rule_id")
        official_url = change.get("official_url")
        fact_updates = change.get("proposed_fact_updates")
        if not isinstance(rule_id, str) or not isinstance(official_url, str) or not isinstance(fact_updates, dict):
            raise ValueError("proposal-change-contract-invalid")
        if set(fact_updates) != {rule_id}:
            raise ValueError(f"proposal-update-scope-invalid:{rule_id}")
        update = fact_updates[rule_id]
        if not isinstance(update, dict):
            raise ValueError(f"proposal-update-invalid:{rule_id}")
        expected_keys = {"fact_id", "current_text", "proposed_text", "source_digest"}
        if set(update) != expected_keys or update.get("fact_id") != rule_id:
            raise ValueError(f"proposal-update-contract-invalid:{rule_id}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(update.get("source_digest", ""))):
            raise ValueError(f"proposal-digest-invalid:{rule_id}")
        updates[rule_id] = {
            "current_text": str(update["current_text"]),
            "proposed_text": str(update["proposed_text"]),
            "source": official_url,
            "digest": str(update["source_digest"]),
        }
    if not updates:
        raise ValueError("proposal-empty-updates")
    return platform, verified_date, updates


def apply_updates(facts_path: Path, verified_date: str, updates: dict[str, dict[str, str]], dry_run: bool) -> list[str]:
    lines = facts_path.read_text(encoding="utf-8").splitlines(keepends=True)
    touched: list[str] = []
    seen: set[str] = set()
    for index, line in enumerate(lines):
        match = ANNOTATION.match(line.rstrip("\n"))
        if not match:
            continue
        fact_id = match.group("id")
        if fact_id not in updates:
            continue
        if index == 0:
            raise ValueError(f"fact-line-missing:{fact_id}")
        fact_match = FACT_PREFIX.match(lines[index - 1].rstrip("\n"))
        if not fact_match:
            raise ValueError(f"fact-line-invalid:{fact_id}")
        update = updates[fact_id]
        if fact_match.group("text").strip() != update["current_text"].strip():
            raise ValueError(f"fact-current-text-mismatch:{fact_id}")
        if match.group("source") != update["source"]:
            raise ValueError(f"fact-source-mismatch:{fact_id}")
        newline = "\n" if lines[index - 1].endswith("\n") else ""
        lines[index - 1] = f"{fact_match.group('indent')}- 事实：{update['proposed_text']}{newline}"
        annotation_newline = "\n" if line.endswith("\n") else ""
        lines[index] = (
            f"{match.group('indent')}<!-- fact: {fact_id} verified={verified_date} "
            f"source={update['source']} digest={update['digest']} -->{annotation_newline}"
        )
        touched.append(fact_id)
        seen.add(fact_id)
    missing = sorted(set(updates) - seen)
    if missing:
        raise ValueError("fact-annotation-missing:" + ",".join(missing))
    if touched and not dry_run:
        facts_path.write_text("".join(lines), encoding="utf-8")
    return touched


def apply_proposal(repo_root: Path, proposal_path: Path, approved: set[str] | None, dry_run: bool) -> dict[str, Any]:
    proposal = load_json(proposal_path)
    platform, verified_date, updates = collect_updates(proposal)
    if approved is not None and platform not in approved:
        return {"proposal": str(proposal_path), "platform": platform, "status": "skipped-unapproved", "updated": []}
    facts_path = repo_root / "platforms" / platform / "facts.md"
    if not facts_path.is_file():
        raise ValueError(f"facts-missing:{platform}")
    touched = apply_updates(facts_path, verified_date, updates, dry_run)
    return {"proposal": str(proposal_path), "platform": platform, "status": "applied", "updated": touched}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("proposals", nargs="*", type=Path, help="Proposal JSON files to apply")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--audit-summary", type=Path, help="audit-summary.json; only PASS platforms are applied")
    parser.add_argument("--out", type=Path, help="Write a machine-readable apply summary")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        approved = approved_platforms(args.audit_summary.resolve()) if args.audit_summary else None
        results = [
            apply_proposal(args.repo_root.resolve(), path.resolve(), approved, args.dry_run)
            for path in args.proposals
            if path.is_file()
        ]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    payload = {
        "dry_run": args.dry_run,
        "applied_count": sum(1 for item in results if item["status"] == "applied" and item["updated"]),
        "results": results,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
