#!/usr/bin/env python3
"""Judge final release evidence in a fresh, read-only Agent context."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any, Sequence

from run_evaluations import agent_command


def schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["verdict", "reason", "blockers"],
        "properties": {
            "verdict": {"type": "string", "enum": ["PASS", "FAIL", "NOT_PROVEN"]},
            "reason": {"type": "string"},
            "blockers": {"type": "array", "items": {"type": "string"}},
        },
    }


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        evidence = load(args.evidence)
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        report = {"verdict": "NOT_PROVEN", "reason": f"unreadable-evidence:{type(exc).__name__}", "blockers": []}
    else:
        prompt = (
            "Act as the final independent release-evidence reviewer for an Agent Skill suite. "
            "Use only the structured evidence below. PASS requires: deterministic tests and suite validation pass; "
            "zero sensitive findings; two public manifests are identical and independently verified; Tier 1 passes; "
            "both routing splits meet 0.90; core and methodology development/held-out judgments all pass with "
            "skill pass rate 1.0 and no regression; all anonymous fixtures remain unchanged; the suite version and "
            "frontmatter version equal the requested version; no business project, global installation, or external "
            "platform mutation occurred. FAIL for a demonstrated violation. NOT_PROVEN for missing, malformed, or "
            "ambiguous evidence. Do not infer unreported checks and do not reward volume.\n\nEVIDENCE:\n"
            + json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
        )
        raw, error = agent_command(Path(tempfile.gettempdir()), prompt, schema())
        if error:
            report = {"verdict": "NOT_PROVEN", "reason": error, "blockers": []}
        else:
            try:
                report = json.loads(raw)
            except json.JSONDecodeError as exc:
                report = {"verdict": "NOT_PROVEN", "reason": f"invalid-judge-output:{type(exc).__name__}", "blockers": []}
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
