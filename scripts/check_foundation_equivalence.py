#!/usr/bin/env python3
"""Assert foundation/ stays a faithful extraction of the shared layer.

Equivalence rule: every foundation file must equal its shared/ origin byte for
byte, except (a) the foundation-source marker line and (b) generalizations
declared in DECLARED_DIFFS below. Any other difference means the extraction has
drifted from the reviewed original and must fail closed.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Sequence

MARKER = "<!-- foundation-source: evidence-first-engineering v3.0 -->"
DECLARED_DIFFS: dict[str, list[tuple[str, str]]] = {
    "guardrails/redaction-policy.md": [("真实小程序协作", "真实工程协作")],
}
PAIRS: tuple[tuple[str, str], ...] = (
    ("shared/evidence-status-model.md", "foundation/guardrails/evidence-status-model.md"),
    ("shared/engineering-guardrails.md", "foundation/guardrails/engineering-guardrails.md"),
    ("shared/decision-and-confirmation-rules.md", "foundation/guardrails/decision-and-confirmation-rules.md"),
    ("shared/redaction-policy.md", "foundation/guardrails/redaction-policy.md"),
    ("shared/templates/project-intake.md", "foundation/templates/project-intake.md"),
    ("shared/templates/implementation-plan.md", "foundation/templates/implementation-plan.md"),
    ("shared/templates/verification-report.md", "foundation/templates/verification-report.md"),
    ("shared/templates/release-checklist.md", "foundation/templates/release-checklist.md"),
)


def strip_marker(text: str) -> str:
    return text.replace("\n" + MARKER, "").replace(MARKER, "").rstrip("\n")


def check(root: Path) -> dict[str, object]:
    problems: list[str] = []
    results = []
    for origin, target in PAIRS:
        origin_path, target_path = root / origin, root / target
        if not target_path.is_file():
            problems.append(f"missing-foundation-file:{target}")
            continue
        a = origin_path.read_text(encoding="utf-8").rstrip("\n")
        b = strip_marker(target_path.read_text(encoding="utf-8"))
        key = target.split("/", 1)[1]
        allowed = [word for pair in DECLARED_DIFFS.get(key, []) for word in pair]
        if a == b:
            results.append({"target": target, "status": "equivalent"})
            continue
        diff = list(difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm=""))
        changed = [line for line in diff if line[:1] in "+-" and line[:3] not in ("+++", "---")]
        undeclared = [line for line in changed if not any(word in line for word in allowed)]
        if undeclared:
            problems.append(f"undeclared-diff:{target}:{undeclared[0][:80]}")
        else:
            results.append({"target": target, "status": "declared-only"})
    return {
        "valid": not problems,
        "checked": len(results) + len([p for p in problems if p.startswith("missing")]),
        "problems": problems,
        "results": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("."), help="Suite root")
    args = parser.parse_args(argv)
    report = check(args.root.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
