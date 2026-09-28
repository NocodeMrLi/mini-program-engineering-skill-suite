#!/usr/bin/env python3
"""Sign a final suite release from fixed structured gates and an independent judgment."""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def audit_snapshot(named_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Copy input audit metadata into the final signature without requiring raw prompts."""
    return {
        "stage": "final-release-signer",
        "generated_at_utc": utc_now(),
        "input_audits": {
            name: report.get("audit")
            for name, report in named_reports.items()
            if isinstance(report.get("audit"), dict)
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "tier1", "routing-development", "routing-held-out", "behavior-development", "behavior-held-out",
        "methodology-development", "methodology-held-out", "artifact-nondegradation", "validation", "sensitive", "package-verification",
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
        artifact_nondegradation = load(args.artifact_nondegradation)
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
        if artifact_nondegradation.get("stage") != "artifact-nondegradation":
            errors.append("artifact-nondegradation-stage-mismatch")
        if artifact_nondegradation.get("candidate_tag") != f"v{args.expected_version}":
            errors.append("artifact-nondegradation-version-mismatch")
        if artifact_nondegradation.get("verdict") != "PASS" or artifact_nondegradation.get("problems") != []:
            errors.append("artifact-nondegradation-not-pass")
        critical_error_count = artifact_nondegradation.get("critical_error_count")
        if (
            not isinstance(critical_error_count, int)
            or isinstance(critical_error_count, bool)
            or critical_error_count != 0
        ):
            errors.append("artifact-nondegradation-critical-errors")
        critical_regression_count = artifact_nondegradation.get("critical_regression_count")
        if (
            not isinstance(critical_regression_count, int)
            or isinstance(critical_regression_count, bool)
            or critical_regression_count != 0
        ):
            errors.append("artifact-nondegradation-critical-regression")
        minimum_cases = artifact_nondegradation.get("minimum_case_count")
        case_count = artifact_nondegradation.get("case_count")
        if (
            not isinstance(minimum_cases, int)
            or isinstance(minimum_cases, bool)
            or minimum_cases < 2
            or not isinstance(case_count, int)
            or isinstance(case_count, bool)
            or case_count < minimum_cases
        ):
            errors.append("artifact-nondegradation-cases-missing")
        minimum_runs = artifact_nondegradation.get("minimum_runs_per_arm")
        run_count = artifact_nondegradation.get("run_count")
        if (
            not isinstance(minimum_runs, int)
            or isinstance(minimum_runs, bool)
            or minimum_runs < 2
            or not isinstance(run_count, int)
            or isinstance(run_count, bool)
            or not isinstance(case_count, int)
            or isinstance(case_count, bool)
            or run_count < case_count * minimum_runs * 2
        ):
            errors.append("artifact-nondegradation-runs-missing")
        mean_gain = artifact_nondegradation.get("mean_target_gain")
        minimum_gain = artifact_nondegradation.get("minimum_mean_target_gain")
        if not all(
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))
            for value in (mean_gain, minimum_gain)
        ):
            errors.append("artifact-nondegradation-gain-missing")
        elif float(minimum_gain) <= 0 or float(mean_gain) < float(minimum_gain):
            errors.append("artifact-nondegradation-gain-below-minimum")
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
        named_reports = {
            "tier1": tier1,
            "routing-development": routing[0],
            "routing-held-out": routing[1],
            "behavior-development": behavior[0],
            "behavior-held-out": behavior[1],
            "methodology-development": methodology[0],
            "methodology-held-out": methodology[1],
            "artifact-nondegradation": artifact_nondegradation,
            "validation": validation,
            "sensitive": sensitive,
            "package-verification": package,
            "independent-judgment": independent,
        }
        verdict = "NOT_PROVEN" if not_proven else ("FAIL" if errors else "PASS")
        report = {
            "verdict": verdict,
            "expected_version": args.expected_version,
            "public_file_count": manifest_a.get("file_count"),
            "errors": errors,
            "not_proven": not_proven,
            "audit": audit_snapshot(named_reports),
        }
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
