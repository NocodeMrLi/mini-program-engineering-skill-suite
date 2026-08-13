#!/usr/bin/env python3
"""Sign Step 5 from independent judgments and frozen public manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence


HELD_OUT_MINIMUM = 1.00
DEVELOPMENT_MINIMUM = 1.00
NON_REGRESSION_MINIMUM = 0.00


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--regression-held-out", type=Path, required=True, nargs="+")
    parser.add_argument("--held-out", type=Path, required=True)
    parser.add_argument("--frozen-manifest", type=Path, required=True)
    parser.add_argument("--post-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    errors: list[str] = []
    not_proven: list[str] = []
    try:
        development = load(args.development)
        regression_held_out = [load(path) for path in args.regression_held_out]
        held_out = load(args.held_out)
        manifests_equal = args.frozen_manifest.read_bytes() == args.post_manifest.read_bytes()
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        report = {
            "verdict": "NOT_PROVEN",
            "errors": [],
            "not_proven": [f"unreadable-input:{type(exc).__name__}"],
        }
    else:
        reports = [("development", development, DEVELOPMENT_MINIMUM)]
        reports.extend(
            (f"regression-held-out-{index}", report, HELD_OUT_MINIMUM)
            for index, report in enumerate(regression_held_out, start=1)
        )
        reports.append(("held-out", held_out, HELD_OUT_MINIMUM))
        for label, report, minimum in reports:
            if report.get("verdict") == "NOT_PROVEN" or report.get("not_proven"):
                not_proven.append(label)
                continue
            skill_rate = float(report.get("skill_pass_rate", 0.0))
            baseline_rate = float(report.get("baseline_pass_rate", 0.0))
            if skill_rate < minimum:
                errors.append(f"{label}-below-minimum")
            if skill_rate - baseline_rate < NON_REGRESSION_MINIMUM:
                errors.append(f"{label}-regressed-versus-baseline")
        if not manifests_equal:
            errors.append("public-manifest-changed-after-freeze")
        verdict = "NOT_PROVEN" if not_proven else ("FAIL" if errors else "PASS")
        report = {
            "verdict": verdict,
            "errors": errors,
            "not_proven": not_proven,
            "public_manifests_equal": manifests_equal,
            "thresholds": {
                "development_minimum": DEVELOPMENT_MINIMUM,
                "held_out_minimum": HELD_OUT_MINIMUM,
                "non_regression_minimum": NON_REGRESSION_MINIMUM,
            },
        }

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
