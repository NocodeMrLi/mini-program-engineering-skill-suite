#!/usr/bin/env python3
"""Summarize release-gate evaluation artifacts into a redacted Markdown report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence


GATE_ORDER = (
    ("tier1", "tier1 结构、预算与资源引用"),
    ("routing-development", "tier2 路由评测（development）"),
    ("routing-held-out", "tier2 路由评测（held-out）"),
    ("behavior-development", "tier3 行为评测（development）"),
    ("behavior-held-out", "tier3 行为评测（held-out）"),
    ("methodology-development", "tier3 方法论评测（development）"),
    ("methodology-held-out", "tier3 方法论评测（held-out）"),
    ("validation", "结构校验"),
    ("sensitive", "敏感信息扫描"),
    ("package-verification", "公共包清单复验"),
    ("independent-judgment", "独立判定"),
    ("final-signature", "独立终审签署"),
)


def load_report(path: Path) -> dict[str, Any]:
    """Load one evaluation artifact with a bounded size budget."""
    if not path.is_file():
        raise ValueError(f"unreadable-input:{path.name}:missing")
    if path.stat().st_size > 20_000_000:
        raise ValueError(f"unreadable-input:{path.name}:oversized")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable-input:{path.name}:{type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"unreadable-input:{path.name}:not-object")
    return value


def fingerprint(value: Any) -> str:
    """Return a short display fingerprint without exposing underlying text."""
    if not isinstance(value, str) or not value:
        return "n/a"
    return value[:12]


def verdict_of(report: dict[str, Any]) -> str:
    verdict = report.get("verdict")
    if isinstance(verdict, str) and verdict:
        return verdict
    if report.get("valid") is True:
        return "PASS"
    if report.get("valid") is False:
        return "FAIL"
    if "finding_count" in report:
        return "PASS" if report.get("finding_count") == 0 and not report.get("findings") else "FAIL"
    return "NOT_PROVEN"


def metrics_of(report: dict[str, Any]) -> str:
    """Describe one gate with counts and rates only; never case contents."""
    parts: list[str] = []
    if "accuracy" in report:
        correct = report.get("correct")
        case_count = report.get("case_count")
        ratio = f"{report['accuracy']:.2f}"
        if isinstance(correct, int) and isinstance(case_count, int):
            parts.append(f"accuracy {ratio} ({correct}/{case_count})")
        else:
            parts.append(f"accuracy {ratio}")
        if isinstance(report.get("minimum"), (int, float)):
            parts.append(f"最低 {report['minimum']:.2f}")
    if isinstance(report.get("case_count"), int) and "accuracy" not in report:
        parts.append(f"cases {report['case_count']}")
        if isinstance(report.get("not_proven"), int):
            parts.append(f"not-proven {report['not_proven']}")
    if isinstance(report.get("skill_pass_rate"), (int, float)):
        parts.append(f"skill {report['skill_pass_rate']:.2f}")
    if isinstance(report.get("baseline_pass_rate"), (int, float)):
        parts.append(f"baseline {report['baseline_pass_rate']:.2f}")
    if isinstance(report.get("non_regression"), bool):
        parts.append(f"non-regression {str(report['non_regression']).lower()}")
    if isinstance(report.get("checks"), int):
        parts.append(f"checks {report['checks']}")
    if isinstance(report.get("skill_count"), int):
        parts.append(f"skills {report['skill_count']}")
    if isinstance(report.get("verified_file_count"), int):
        parts.append(f"files {report['verified_file_count']}")
    if isinstance(report.get("finding_count"), int):
        parts.append(f"findings {report['finding_count']}")
    if isinstance(report.get("candidate_count"), int) and isinstance(report.get("scanned_count"), int):
        parts.append(f"scanned {report['scanned_count']}/{report['candidate_count']}")
    if "judgments" in report and isinstance(report["judgments"], list):
        counts: dict[str, int] = {}
        for item in report["judgments"]:
            if isinstance(item, dict) and isinstance(item.get("verdict"), str):
                counts[item["verdict"]] = counts.get(item["verdict"], 0) + 1
        rendered = ", ".join(f"{key} {count}" for key, count in sorted(counts.items())) or "none"
        parts.append(f"judgments {len(report['judgments'])} ({rendered})")
    if "errors" in report and isinstance(report["errors"], list) and report["errors"]:
        parts.append(f"errors {len(report['errors'])}")
    return "; ".join(parts) if parts else "n/a"


def audit_of(report: dict[str, Any]) -> str:
    """Render audit metadata; fingerprints only, never prompt or schema text."""
    audit = report.get("audit")
    if not isinstance(audit, dict):
        return "n/a"
    parts: list[str] = []
    for key in ("generated_at_utc", "engine", "model"):
        if isinstance(audit.get(key), str) and audit[key]:
            parts.append(f"{key}={audit[key]}")
    if audit.get("prompt_sha256"):
        parts.append(f"prompt_sha256={fingerprint(audit.get('prompt_sha256'))}")
    if audit.get("schema_sha256"):
        parts.append(f"schema_sha256={fingerprint(audit.get('schema_sha256'))}")
    return "; ".join(parts) if parts else "n/a"


def render_summary(version: str, gates: list[tuple[str, dict[str, Any]]]) -> str:
    """Render the redacted public summary for one release."""
    lines = [
        f"# 评测摘要（v{version}）",
        "",
        "本页只记录各发布门禁的结论、关键指标与审计元数据。提示词、模型回复、",
        "夹具内容和逐案例明细保留在内部评测目录，不进入公开摘要。",
        "",
        "| 门禁 | 结论 | 关键指标 | 审计元数据 |",
        "| --- | --- | --- | --- |",
    ]
    for label, report in gates:
        lines.append(f"| {label} | {verdict_of(report)} | {metrics_of(report)} | {audit_of(report)} |")
    lines.extend(
        [
            "",
            "## 复现方式",
            "",
            "评测产物由内部评测流程生成后，使用以下命令生成本页表格：",
            "",
            "```bash",
            "python3 scripts/summarize_evaluations.py \\",
            "  --tier1 <tier1-report.json> \\",
            "  --routing-development <report.json> --routing-held-out <report.json> \\",
            "  --behavior-development <report.json> --behavior-held-out <report.json> \\",
            "  --methodology-development <report.json> --methodology-held-out <report.json> \\",
            "  --validation <validate-report.json> --sensitive <scan-report.json> \\",
            "  --package-verification <verify-report.json> --independent-judgment <judge-report.json> \\",
            "  [--final-signature <signer-report.json>] --version <VERSION>",
            "```",
            "",
            "## 证据边界",
            "",
            "- `tier1` 为本地静态检查，不调用模型；`tier2`/`tier3` 与判定、签署依赖本地 Agent 运行器。",
            "- 路由评测的 accuracy 只说明该批用例上的路由命中率，不推出真实任务成功率。",
            "- 行为与方法论评测的 `PASS` 表示该批匿名夹具上必需行为成立、禁止行为未出现、夹具未被修改；不推出更广任务的表现。",
            "- 本页不构成对任何真实小程序项目的验收、审核通过或正式发布证据。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    for name, _ in GATE_ORDER:
        required = name != "final-signature"
        parser.add_argument(f"--{name}", type=Path, required=required, help=f"Report JSON for {name}")
    parser.add_argument("--version", default="", help="Suite version label, for example 1.4.0")
    parser.add_argument("--output", type=Path, help="Write Markdown here instead of stdout")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    gates: list[tuple[str, dict[str, Any]]] = []
    try:
        for name, label in GATE_ORDER:
            argument = getattr(args, name.replace("-", "_"))
            if argument is None:
                continue
            gates.append((label, load_report(argument)))
    except ValueError as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    version = args.version.strip() or "unknown"
    summary = render_summary(version, gates)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(summary, encoding="utf-8")
    else:
        print(summary, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
