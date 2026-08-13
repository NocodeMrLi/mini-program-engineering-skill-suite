#!/usr/bin/env python3
"""Sign a Step 4 verdict from frozen, structured evaluation results only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence


ROUTING_MINIMUM = 0.90
HELD_OUT_MINIMUM = 1.00
BEHAVIOR_NON_REGRESSION_MINIMUM = 0.00


def read_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sign(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    not_proven: list[str] = []
    try:
        tier1 = read_report(args.tier1)
        routing_dev = read_report(args.routing_development)
        routing_held = read_report(args.routing_held_out)
        behavior_dev = read_report(args.behavior_development)
        behavior_held = read_report(args.behavior_held_out)
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        return {"verdict": "NOT_PROVEN", "errors": [], "not_proven": [f"unreadable-input:{type(exc).__name__}"]}

    if tier1.get("verdict") != "PASS":
        errors.append("tier1-not-pass")
    for label, report in (("routing-development", routing_dev), ("routing-held-out", routing_held)):
        if report.get("verdict") == "NOT_PROVEN":
            not_proven.append(label)
        elif float(report.get("accuracy", 0.0)) < ROUTING_MINIMUM:
            errors.append(f"{label}-below-threshold")

    for label, report in (("behavior-development", behavior_dev), ("behavior-held-out", behavior_held)):
        if report.get("verdict") == "NOT_PROVEN" or report.get("not_proven"):
            not_proven.append(label)
            continue
        skill_rate = float(report.get("skill_pass_rate", 0.0))
        baseline_rate = float(report.get("baseline_pass_rate", 0.0))
        if skill_rate - baseline_rate < BEHAVIOR_NON_REGRESSION_MINIMUM:
            errors.append(f"{label}-regressed-versus-baseline")
        if label == "behavior-held-out" and skill_rate < HELD_OUT_MINIMUM:
            errors.append("behavior-held-out-below-threshold")

    if not_proven:
        verdict = "NOT_PROVEN"
    elif errors:
        verdict = "FAIL"
    else:
        verdict = "PASS"
    return {
        "verdict": verdict,
        "errors": errors,
        "not_proven": not_proven,
        "thresholds": {
            "routing_minimum": ROUTING_MINIMUM,
            "held_out_minimum": HELD_OUT_MINIMUM,
            "behavior_non_regression_minimum": BEHAVIOR_NON_REGRESSION_MINIMUM,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier1", type=Path, required=True)
    parser.add_argument("--routing-development", type=Path, required=True)
    parser.add_argument("--routing-held-out", type=Path, required=True)
    parser.add_argument("--behavior-development", type=Path, required=True)
    parser.add_argument("--behavior-held-out", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = sign(args)
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
