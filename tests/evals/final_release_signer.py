#!/usr/bin/env python3
"""Sign a final suite release from fixed structured gates and an independent judgment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "tier1", "routing-development", "routing-held-out", "behavior-development", "behavior-held-out",
        "methodology-development", "methodology-held-out", "validation", "sensitive", "package-verification",
        "manifest-a", "manifest-b", "version-file", "independent-judgment",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    errors: list[str] = []
    not_proven: list[str] = []
    try:
        tier1 = load(args.tier1)
        routing = [load(args.routing_development), load(args.routing_held_out)]
        behavior = [load(args.behavior_development), load(args.behavior_held_out)]
        methodology = [load(args.methodology_development), load(args.methodology_held_out)]
        validation = load(args.validation)
        sensitive = load(args.sensitive)
        package = load(args.package_verification)
        manifest_a = load(args.manifest_a)
        manifest_b = load(args.manifest_b)
        independent = load(args.independent_judgment)
        version = args.version_file.read_text(encoding="utf-8").strip()
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        report = {"verdict": "NOT_PROVEN", "errors": [], "not_proven": [f"unreadable-input:{type(exc).__name__}"]}
    else:
        if tier1.get("verdict") != "PASS":
            errors.append("tier1-not-pass")
        for index, item in enumerate(routing, start=1):
            if item.get("verdict") == "NOT_PROVEN":
                not_proven.append(f"routing-{index}")
            elif item.get("verdict") != "PASS" or float(item.get("accuracy", 0)) < 0.90:
                errors.append(f"routing-{index}-not-pass")
        for family, reports in (("behavior", behavior), ("methodology", methodology)):
            for index, item in enumerate(reports, start=1):
                if item.get("verdict") == "NOT_PROVEN" or item.get("not_proven"):
                    not_proven.append(f"{family}-{index}")
                elif (
                    item.get("verdict") != "PASS"
                    or float(item.get("skill_pass_rate", 0)) < 1.0
                    or item.get("non_regression") is not True
                ):
                    errors.append(f"{family}-{index}-not-pass")
        if validation.get("valid") is not True or validation.get("errors"):
            errors.append("suite-validation-not-pass")
        if sensitive.get("finding_count") != 0 or sensitive.get("findings"):
            errors.append("sensitive-scan-not-clean")
        if package.get("valid") is not True or package.get("errors"):
            errors.append("package-verification-not-pass")
        if manifest_a != manifest_b:
            errors.append("public-manifest-mismatch")
        if package.get("verified_file_count") != manifest_a.get("file_count"):
            errors.append("package-file-count-mismatch")
        if version != args.expected_version:
            errors.append("version-file-mismatch")
        if manifest_a.get("suite_version") != args.expected_version:
            errors.append("manifest-version-mismatch")
        if independent.get("verdict") == "NOT_PROVEN":
            not_proven.append("independent-judgment")
        elif independent.get("verdict") != "PASS" or independent.get("blockers"):
            errors.append("independent-judgment-not-pass")
        verdict = "NOT_PROVEN" if not_proven else ("FAIL" if errors else "PASS")
        report = {
            "verdict": verdict,
            "expected_version": args.expected_version,
            "public_file_count": manifest_a.get("file_count"),
            "errors": errors,
            "not_proven": not_proven,
        }
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
