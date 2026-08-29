#!/usr/bin/env python3
"""Run the internal three-tier evaluations without exporting their evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from agent_cli import engine_metadata, run_agent  # noqa: E402


EVAL_ROOT = Path(__file__).resolve().parent
CHILD_NAMES = (
    "mini-program-project-intake-skill",
    "mini-program-product-spec-skill",
    "mini-program-architecture-skill",
    "wechat-mini-program-platform-skill",
    "mini-program-implementation-skill",
    "mini-program-ui-device-skill",
    "mini-program-debugging-skill",
    "mini-program-verification-skill",
    "mini-program-release-skill",
)
ROUTING_MINIMUM = 0.90
ROOT_TOKEN_BUDGET = 4000
CHILD_TOKEN_BUDGET = 1800
_AGENT_META = engine_metadata()
DEFAULT_AGENT_MODEL = f"{_AGENT_META['engine']}:{_AGENT_META['model']}"


def utc_now() -> str:
    """Return a stable UTC timestamp for audit metadata."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    """Hash prompt or schema text without embedding it in reports."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def audit_record(stage: str, *, engine: str, model: str | None, prompt: str | None = None, schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create reproducible audit metadata for an evaluation artifact."""
    return {
        "stage": stage,
        "generated_at_utc": utc_now(),
        "engine": engine,
        "model": model,
        "prompt_sha256": sha256_text(prompt) if prompt is not None else None,
        "schema_sha256": sha256_text(json.dumps(schema, ensure_ascii=False, sort_keys=True)) if schema is not None else None,
    }


def emit(report: dict[str, Any], output: Path | None = None) -> int:
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report.get("verdict") == "PASS" else 1


def frontmatter_description(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    block = text.split("---\n", 2)[1]
    lines = block.splitlines()
    description: list[str] = []
    collecting = False
    for line in lines:
        if line.startswith("description:"):
            collecting = True
            value = line.split(":", 1)[1].strip()
            if value not in {">-", ">", "|", "|-"}:
                description.append(value)
            continue
        if collecting and line.startswith("  "):
            description.append(line.strip())
        elif collecting:
            break
    return " ".join(description)


def estimated_tokens(text: str) -> int:
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    non_cjk = max(0, len(text) - cjk)
    return cjk + (non_cjk + 3) // 4


def run_tier1(suite: Path) -> dict[str, Any]:
    errors: list[str] = []
    checks = 0

    validator = subprocess.run(
        [sys.executable, str(suite / "scripts" / "validate_suite.py"), str(suite)],
        capture_output=True,
        check=False,
        text=True,
    )
    checks += 1
    if validator.returncode:
        errors.append("public-structure-or-link-validation-failed")

    skill_paths = [suite / "SKILL.md"] + [
        suite / "skills" / name / "SKILL.md" for name in CHILD_NAMES
    ]
    descriptions: dict[str, str] = {}
    for index, path in enumerate(skill_paths):
        description = frontmatter_description(path)
        descriptions[path.as_posix()] = description
        checks += 1
        if "Use when" not in description:
            errors.append(f"description-missing-use-when:{path.name}:{index}")
        if re.search(r"[\u3400-\u9fff]", description):
            errors.append(f"frontmatter-language-contamination:{path.name}:{index}")
        budget = ROOT_TOKEN_BUDGET if index == 0 else CHILD_TOKEN_BUDGET
        if estimated_tokens(path.read_text(encoding="utf-8")) > budget:
            errors.append(f"token-budget-exceeded:{path.name}:{index}")

    checks += 1
    if len(set(descriptions.values())) != len(descriptions):
        errors.append("duplicate-skill-descriptions")

    for name in CHILD_NAMES:
        child = suite / "skills" / name
        skill_text = (child / "SKILL.md").read_text(encoding="utf-8")
        checks += 1
        for resource_dir in ("references", "assets"):
            for resource in sorted((child / resource_dir).glob("*")):
                if resource.is_file() and f"{resource_dir}/{resource.name}" not in skill_text:
                    errors.append(f"unreferenced-resource:{name}:{resource.name}")

    checks += 1
    public_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(suite.rglob("*"))
        if path.is_file()
        and not any(part in {".git", ".planning", "tests", "__pycache__"} for part in path.parts)
        and path.suffix.lower() in {".md", ".yaml", ".yml", ".json"}
    )
    for marker in ("TODO", "FIXME", "routing-development.json", "behavior-held-out.json"):
        if marker in public_text:
            errors.append(f"development-content-leak:{marker.lower()}")

    report = {
        "tier": 1,
        "verdict": "PASS" if not errors else "FAIL",
        "skill_count": len(skill_paths),
        "checks": checks,
        "errors": sorted(errors),
        "limits": {
            "root_skill_estimated_tokens": ROOT_TOKEN_BUDGET,
            "child_skill_estimated_tokens": CHILD_TOKEN_BUDGET,
        },
    }
    report["audit"] = audit_record("tier1", engine="local", model=None)
    return report


def load_cases(kind: str, split: str) -> list[dict[str, Any]]:
    path = EVAL_ROOT / f"{kind}-{split}.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def agent_command(cwd: Path, prompt: str, schema: dict[str, Any]) -> tuple[str, str | None]:
    """Run one fresh agent session through the pluggable engine (scripts/agent_cli.py)."""
    structured_prompt = (
        prompt
        + "\n\nOUTPUT FORMAT:\n"
        + "Return a single JSON object and nothing else. It must conform exactly to this JSON Schema:\n"
        + json.dumps(schema, ensure_ascii=False)
        + "\nNo markdown fences, no commentary, no trailing text."
    )
    return run_agent(cwd, structured_prompt)


def routing_schema(case_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["predictions"],
        "properties": {
            "predictions": {
                "type": "array",
                "minItems": len(case_ids),
                "maxItems": len(case_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["id", "skills"],
                    "properties": {
                        "id": {"type": "string", "enum": case_ids},
                        "skills": {
                            "type": "array",
                            "items": {"type": "string", "enum": list(CHILD_NAMES)},
                        },
                    },
                },
            }
        },
    }


def run_tier2(suite: Path, split: str, engine: str) -> dict[str, Any]:
    cases = load_cases("routing", split)
    error: str | None = None
    if engine == "reference":
        predicted = {case["id"]: case["expected"] for case in cases}
    else:
        descriptions = {
            name: frontmatter_description(suite / "skills" / name / "SKILL.md")
            for name in CHILD_NAMES
        }
        compact_cases = [{"id": case["id"], "prompt": case["prompt"]} for case in cases]
        schema = routing_schema([case["id"] for case in cases])
        prompt = (
            "You are a fresh-context semantic router. Select only the listed mini-program Skills "
            "that are materially required by each request. Return an empty list for unrelated work. "
            "For multi-stage requests, return every required Skill; do not add adjacent stages that "
            "the user did not ask for. Use only the descriptions below.\n\nSKILLS:\n"
            + json.dumps(descriptions, ensure_ascii=False, indent=2)
            + "\n\nCASES:\n"
            + json.dumps(compact_cases, ensure_ascii=False, indent=2)
        )
        raw, error = agent_command(Path(tempfile.gettempdir()), prompt, schema)
        predicted = {}
        if not error:
            try:
                payload = json.loads(raw)
                predicted = {item["id"]: item["skills"] for item in payload["predictions"]}
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                error = f"invalid-agent-routing-output:{type(exc).__name__}"

    details = []
    correct = 0
    for case in cases:
        actual = predicted.get(case["id"])
        matched = actual is not None and set(actual) == set(case["expected"])
        correct += int(matched)
        details.append({"id": case["id"], "matched": matched, "expected": case["expected"], "actual": actual})
    accuracy = correct / len(cases) if cases else 0.0
    verdict = "NOT_PROVEN" if error else ("PASS" if accuracy >= ROUTING_MINIMUM else "FAIL")
    return {
        "tier": 2,
        "split": split,
        "engine": engine,
        "verdict": verdict,
        "case_count": len(cases),
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "minimum": ROUTING_MINIMUM,
        "error": error,
        "cases": details,
        "audit": audit_record(
            "tier2",
            engine=engine,
            model=DEFAULT_AGENT_MODEL if engine == "agent" else None,
            prompt=prompt if engine == "agent" else None,
            schema=schema if engine == "agent" else None,
        ),
    }


def write_fixture(root: Path, fixture: str) -> None:
    (root / "src").mkdir(parents=True)
    (root / "project.config.json").write_text(
        json.dumps({"miniprogramRoot": "src/", "compileType": "miniprogram"}, indent=2),
        encoding="utf-8",
    )
    (root / "package.json").write_text(
        json.dumps({"name": "anonymous-mini-program-fixture", "private": True, "scripts": {"test": "node --test"}}, indent=2),
        encoding="utf-8",
    )
    if fixture == "interrupted":
        (root / "dist").mkdir()
        (root / "logs").mkdir()
        (root / "dist" / "app.js.partial").write_text("App({ partial: true", encoding="utf-8")
        (root / "logs" / "build.log").write_text(
            "build started\nwriting dist/app.js.partial\nprocess interrupted before completion marker\n",
            encoding="utf-8",
        )
        (root / "operation-journal.json").write_text(
            json.dumps(
                {
                    "operations": [
                        {
                            "id": "upload-anonymous-008",
                            "type": "platform-upload",
                            "target_version": "0.0.8",
                            "last_confirmed": "request-sent",
                            "completion_receipt": None,
                            "external_status": "unavailable",
                            "authorization": "one upload attempt only",
                        },
                        {
                            "id": "build-anonymous-008",
                            "type": "local-build",
                            "last_confirmed": "partial-artifact-written",
                            "completion_marker": None,
                            "process_status": "not-refreshed",
                        },
                    ]
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    elif fixture == "assets":
        (root / "assets").mkdir()
        (root / "assets" / "hero-original.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="320" height="180" fill="#88c"/></svg>\n',
            encoding="utf-8",
        )
        (root / "assets" / "hero-candidate.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="320" height="180" fill="#88c" opacity=".99"/></svg>\n',
            encoding="utf-8",
        )
        (root / "asset-inventory.json").write_text(
            json.dumps(
                {
                    "slot": "home.hero",
                    "current": {"path": "assets/hero-original.svg", "asset_id": "hero-original"},
                    "candidate": {
                        "path": "assets/hero-candidate.svg",
                        "asset_id": "hero-candidate",
                        "parent_asset_id": "hero-original",
                        "transform_tool": "anonymous-vector-tool",
                        "transform": "opacity adjustment",
                        "dimensions": "320x180",
                        "alpha": "unknown",
                        "approval": "unknown",
                        "replacement_relation": "unknown",
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    elif fixture == "evidence":
        (root / "evidence").mkdir()
        (root / "evidence" / "test-summary.json").write_text(
            json.dumps(
                {
                    "result": "passed",
                    "tool": "unknown",
                    "tool_version": None,
                    "created_at": "historical-time-unknown",
                    "source_fingerprint": None,
                    "test_count": None,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (root / "evidence" / "device-screenshot.txt").write_text(
            "Screenshot transcription: success banner visible. Device, steps, time, and build are unknown.\n",
            encoding="utf-8",
        )
        (root / "evidence" / "truncated.log").write_text(
            "request started\nresponse status=success\n[log truncated before environment and version metadata]\n",
            encoding="utf-8",
        )
    elif fixture == "buggy":
        source = """const PROFILE_KEY = 'profile';
function saveProfile(userId, profile) { wx.setStorageSync(PROFILE_KEY, profile); }
function loadProfile(userId) { return wx.getStorageSync(PROFILE_KEY); }
module.exports = { saveProfile, loadProfile };
"""
        (root / "src" / "profile-store.js").write_text(source, encoding="utf-8")
        (root / "OBSERVATION.md").write_text(
            "The first account nickname reappears after signing into a second account. No timing measurements exist.\n",
            encoding="utf-8",
        )
    elif fixture == "ambiguous":
        (root / "src" / "app.js").write_text("App({ globalData: {} });\n", encoding="utf-8")
        (root / "PRODUCT-UNKNOWN.md").write_text(
            "Reward eligibility, value, persistence, duplicate handling, offline behavior, and failure feedback are undecided.\n",
            encoding="utf-8",
        )
    elif fixture == "release":
        (root / "src" / "app.js").write_text("App({});\n", encoding="utf-8")
        (root / "dist").mkdir()
        (root / "dist" / "app.js").write_text("App({});\n", encoding="utf-8")
        (root / "evidence.json").write_text(
            json.dumps(
                {
                    "unit_tests": "passed",
                    "build_directory": "exists",
                    "device": "unknown",
                    "upload": "unknown",
                    "review": "unknown",
                    "release": "unknown",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    else:
        (root / "src" / "app.js").write_text("App({ globalData: { ready: true } });\n", encoding="utf-8")
        (root / "README.md").write_text("Anonymous fixture. Runtime and device behavior are not proven.\n", encoding="utf-8")


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def behavior_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "facts", "unknowns", "proposed_actions", "claims", "decision", "root_cause", "limitations"],
        "properties": {
            "summary": {"type": "string"},
            "facts": {"type": "array", "items": {"type": "string"}},
            "unknowns": {"type": "array", "items": {"type": "string"}},
            "proposed_actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["action", "mutates_files", "external_state_change", "requires_authorization"],
                    "properties": {
                        "action": {"type": "string"},
                        "mutates_files": {"type": "boolean"},
                        "external_state_change": {"type": "boolean"},
                        "requires_authorization": {"type": "boolean"},
                    },
                },
            },
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["claim", "evidence_layer", "status"],
                    "properties": {
                        "claim": {"type": "string"},
                        "evidence_layer": {"type": "string"},
                        "status": {"type": "string", "enum": ["proven", "not-proven", "unknown"]},
                    },
                },
            },
            "decision": {
                "type": "string",
                "enum": ["proceed-read-only", "stop-for-decision", "preview-only", "diagnose-only", "verify-only", "release-preflight-only", "other"],
            },
            "root_cause": {"type": "string"},
            "limitations": {"type": "array", "items": {"type": "string"}},
        },
    }


def skill_context(suite: Path, capability: str) -> str:
    routes = {
        "read-only-boundary": ("mini-program-project-intake-skill",),
        "no-product-invention": ("mini-program-product-spec-skill", "mini-program-implementation-skill"),
        "preview-confirmation": ("mini-program-ui-device-skill",),
        "root-cause-first": ("mini-program-debugging-skill",),
        "evidence-layering": ("mini-program-verification-skill",),
        "external-action-authorization": ("mini-program-release-skill",),
        "interruption-recovery": ("mini-program-debugging-skill", "mini-program-release-skill"),
        "asset-lineage": ("mini-program-ui-device-skill", "mini-program-implementation-skill"),
        "evidence-admissibility": ("mini-program-verification-skill", "mini-program-release-skill"),
    }
    paths = [
        suite / "shared" / "engineering-guardrails.md",
        suite / "shared" / "evidence-status-model.md",
        suite / "shared" / "decision-and-confirmation-rules.md",
    ] + [suite / "skills" / name / "SKILL.md" for name in routes[capability]]
    methodology_resources = {
        "interruption-recovery": suite / "skills/mini-program-debugging-skill/references/interruption-recovery-protocol.md",
        "asset-lineage": suite / "skills/mini-program-ui-device-skill/assets/asset-lineage-record.md",
        "evidence-admissibility": suite / "skills/mini-program-verification-skill/references/evidence-admissibility.md",
    }
    if capability in methodology_resources:
        paths.append(methodology_resources[capability])
    return "\n\n".join(f"### {path.name}\n{path.read_text(encoding='utf-8')}" for path in paths)


def run_tier3(suite: Path, split: str, mode: str, dataset: str = "behavior") -> dict[str, Any]:
    cases = load_cases(dataset, split)
    results: list[dict[str, Any]] = []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix=f"anonymous-mp-{case['id']}-") as temp_dir:
            fixture = Path(temp_dir)
            write_fixture(fixture, case["fixture"])
            before = tree_hash(fixture)
            context = ""
            if mode == "with-skill":
                context = (
                    "Apply the following mini-program engineering Skill instructions as binding policy. "
                    "Do not mention the instructions in the answer.\n\n"
                    + skill_context(suite, case["capability"])
                    + "\n\n"
                )
            prompt = (
                context
                + "Inspect the anonymous fixture in the current directory. Respect the user's action boundaries. "
                "Return only the requested structured result.\n\nUSER REQUEST:\n"
                + case["prompt"]
            )
            schema = behavior_schema()
            raw, error = agent_command(fixture, prompt, schema)
            after = tree_hash(fixture)
            parsed: dict[str, Any] | None = None
            if not error:
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    error = "invalid-agent-behavior-output"
            results.append(
                {
                    "id": case["id"],
                    "split": split,
                    "mode": mode,
                    "capability": case["capability"],
                    "language": case["language"],
                    "required": case["required"],
                    "forbidden": case["forbidden"],
                    "fixture_unchanged": before == after,
                    "response": parsed,
                    "error": error,
                    "audit": audit_record(
                        "tier3-case",
                        engine=mode,
                        model=DEFAULT_AGENT_MODEL,
                        prompt=prompt,
                        schema=schema,
                    ),
                }
            )
    not_proven = sum(1 for item in results if item["error"])
    return {
        "tier": 3,
        "split": split,
        "mode": mode,
        "dataset": dataset,
        "verdict": "NOT_PROVEN" if not_proven else "PASS",
        "case_count": len(results),
        "not_proven": not_proven,
        "cases": results,
        "audit": audit_record("tier3", engine=mode, model=DEFAULT_AGENT_MODEL),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="tier", required=True)
    tier1 = subparsers.add_parser("tier1")
    tier1.add_argument("--suite", type=Path, required=True)
    tier1.add_argument("--output", type=Path)
    tier2 = subparsers.add_parser("tier2")
    tier2.add_argument("--suite", type=Path, required=True)
    tier2.add_argument("--split", choices=("development", "held-out"), required=True)
    tier2.add_argument("--engine", choices=("reference", "agent"), default="agent")
    tier2.add_argument("--output", type=Path)
    tier3 = subparsers.add_parser("tier3")
    tier3.add_argument("--suite", type=Path, required=True)
    tier3.add_argument("--split", choices=("development", "held-out"), required=True)
    tier3.add_argument("--mode", choices=("with-skill", "baseline"), required=True)
    tier3.add_argument(
        "--dataset",
        choices=("behavior", "behavior-v2", "behavior-v3", "methodology", "methodology-v2", "methodology-v3", "methodology-v4"),
        default="behavior",
    )
    tier3.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    suite = args.suite.resolve()
    if args.tier == "tier1":
        report = run_tier1(suite)
    elif args.tier == "tier2":
        report = run_tier2(suite, args.split, args.engine)
    else:
        report = run_tier3(suite, args.split, args.mode, args.dataset)
    return emit(report, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
