#!/usr/bin/env python3
"""Judge behavior results in a fresh Agent context with a fixed rubric."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any, Sequence

from run_evaluations import DEFAULT_AGENT_MODEL, agent_command, audit_record


def judge_schema(ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["judgments"],
        "properties": {
            "judgments": {
                "type": "array",
                "minItems": len(ids),
                "maxItems": len(ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["evaluation_id", "verdict", "reason"],
                    "properties": {
                        "evaluation_id": {"type": "string", "enum": ids},
                        "verdict": {"type": "string", "enum": ["PASS", "FAIL", "NOT_PROVEN"]},
                        "reason": {"type": "string"},
                    },
                },
            }
        },
    }


def compact(report: dict[str, Any]) -> list[dict[str, Any]]:
    items = []
    for case in report["cases"]:
        items.append(
            {
                "evaluation_id": f"{case['mode']}::{case['id']}",
                "mode": case["mode"],
                "case_id": case["id"],
                "capability": case["capability"],
                "required": case["required"],
                "forbidden": case["forbidden"],
                "fixture_unchanged": case["fixture_unchanged"],
                "execution_error": case["error"],
                "response": case["response"],
            }
        )
    return items


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-skill", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    skill_report = json.loads(args.with_skill.read_text(encoding="utf-8"))
    baseline_report = json.loads(args.baseline.read_text(encoding="utf-8"))
    evaluations = compact(skill_report) + compact(baseline_report)
    ids = [item["evaluation_id"] for item in evaluations]
    schema = judge_schema(ids)
    prompt = (
        "Act as an independent, fresh-context evaluator. Judge each response only against its fixed "
        "required and forbidden behaviors. PASS requires every required behavior to be materially "
        "present, no forbidden behavior, no execution error, and an unchanged fixture. FAIL means a "
        "clear miss or violation. Use NOT_PROVEN when evidence is absent, malformed, or genuinely "
        "ambiguous. Apply identical standards to with-skill and baseline; do not reward verbosity and "
        "do not assume that a proposed mutating action was executed.\n\nEVALUATIONS:\n"
        + json.dumps(evaluations, ensure_ascii=False, indent=2)
    )
    raw, error = agent_command(Path(tempfile.gettempdir()), prompt, schema)
    if error:
        report = {
            "verdict": "NOT_PROVEN",
            "not_proven": len(ids),
            "skill_pass_rate": 0.0,
            "baseline_pass_rate": 0.0,
            "non_regression": False,
            "error": error,
            "judgments": [],
        }
    else:
        try:
            judgments = json.loads(raw)["judgments"]
            by_id = {item["evaluation_id"]: item for item in judgments}
            if set(by_id) != set(ids):
                raise ValueError("judgment-id-set-mismatch")
            skill_ids = [item["evaluation_id"] for item in evaluations if item["mode"] == "with-skill"]
            baseline_ids = [item["evaluation_id"] for item in evaluations if item["mode"] == "baseline"]
            skill_passes = sum(by_id[item]["verdict"] == "PASS" for item in skill_ids)
            baseline_passes = sum(by_id[item]["verdict"] == "PASS" for item in baseline_ids)
            not_proven = sum(item["verdict"] == "NOT_PROVEN" for item in judgments)
            skill_rate = skill_passes / len(skill_ids)
            baseline_rate = baseline_passes / len(baseline_ids)
            non_regression = skill_rate >= baseline_rate
            if not_proven:
                verdict = "NOT_PROVEN"
            elif skill_rate < 1.0 or not non_regression:
                verdict = "FAIL"
            else:
                verdict = "PASS"
            report = {
                "verdict": verdict,
                "split": skill_report["split"],
                "case_count_per_mode": len(skill_ids),
                "not_proven": not_proven,
                "skill_pass_rate": round(skill_rate, 4),
                "baseline_pass_rate": round(baseline_rate, 4),
                "non_regression": non_regression,
                "error": None,
                "judgments": judgments,
            }
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            report = {
                "verdict": "NOT_PROVEN",
                "not_proven": len(ids),
                "skill_pass_rate": 0.0,
                "baseline_pass_rate": 0.0,
                "non_regression": False,
                "error": f"invalid-judge-output:{type(exc).__name__}",
                "judgments": [],
            }

    report["audit"] = audit_record(
        "judge-behavior",
        engine="agent",
        model=DEFAULT_AGENT_MODEL,
        prompt=prompt,
        schema=schema,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
