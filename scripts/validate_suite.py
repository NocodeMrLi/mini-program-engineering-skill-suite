#!/usr/bin/env python3
"""Validate the public structure and links of the skill suite."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Sequence


REQUIRED_FILES = (
    "README.md",
    "README.en.md",
    "LICENSE",
    "CHANGELOG.md",
    "COMPATIBILITY.md",
    "assets/readme-cover.png",
    "assets/readme-promo.mp4",
    "assets/readme-promo-poster.png",
    "assets/wordpet-origin-case.png",
    "SKILL.md",
    "agents/openai.yaml",
    "references/routing-and-state-machine.md",
    "shared/engineering-guardrails.md",
    "shared/evidence-status-model.md",
    "shared/decision-and-confirmation-rules.md",
    "shared/redaction-policy.md",
    "shared/documentation-boundaries.md",
    "shared/templates/project-intake.md",
    "shared/templates/implementation-plan.md",
    "shared/templates/verification-report.md",
    "shared/templates/release-checklist.md",
    "skills/mini-program-project-intake-skill/SKILL.md",
    "skills/mini-program-project-intake-skill/agents/openai.yaml",
    "skills/mini-program-project-intake-skill/references/intake-workflow.md",
    "skills/mini-program-project-intake-skill/assets/project-fact-map.md",
    "skills/mini-program-product-spec-skill/SKILL.md",
    "skills/mini-program-product-spec-skill/agents/openai.yaml",
    "skills/mini-program-product-spec-skill/references/specification-workflow.md",
    "skills/mini-program-product-spec-skill/assets/product-specification.md",
    "skills/mini-program-architecture-skill/SKILL.md",
    "skills/mini-program-architecture-skill/agents/openai.yaml",
    "skills/mini-program-architecture-skill/references/architecture-workflow.md",
    "skills/mini-program-architecture-skill/assets/architecture-decision-record.md",
    "skills/wechat-mini-program-platform-skill/SKILL.md",
    "skills/wechat-mini-program-platform-skill/agents/openai.yaml",
    "skills/wechat-mini-program-platform-skill/references/platform-evidence-layers.md",
    "skills/wechat-mini-program-platform-skill/assets/wechat-platform-checklist.md",
    "skills/wechat-mini-program-platform-skill/assets/privacy-permission-matrix.md",
    "skills/mini-program-implementation-skill/SKILL.md",
    "skills/mini-program-implementation-skill/agents/openai.yaml",
    "skills/mini-program-implementation-skill/references/implementation-workflow.md",
    "skills/mini-program-implementation-skill/assets/implementation-handoff.md",
    "skills/mini-program-ui-device-skill/SKILL.md",
    "skills/mini-program-ui-device-skill/agents/openai.yaml",
    "skills/mini-program-ui-device-skill/references/ui-device-workflow.md",
    "skills/mini-program-ui-device-skill/assets/ui-device-evidence-record.md",
    "skills/mini-program-ui-device-skill/assets/asset-lineage-record.md",
    "skills/mini-program-ui-device-skill/assets/accessibility-matrix.md",
    "skills/mini-program-debugging-skill/SKILL.md",
    "skills/mini-program-debugging-skill/agents/openai.yaml",
    "skills/mini-program-debugging-skill/references/debugging-workflow.md",
    "skills/mini-program-debugging-skill/references/interruption-recovery-protocol.md",
    "skills/mini-program-debugging-skill/assets/debugging-report.md",
    "skills/mini-program-verification-skill/SKILL.md",
    "skills/mini-program-verification-skill/agents/openai.yaml",
    "skills/mini-program-verification-skill/references/verification-workflow.md",
    "skills/mini-program-verification-skill/references/evidence-admissibility.md",
    "skills/mini-program-verification-skill/references/verification-capability-matrix.md",
    "skills/mini-program-verification-skill/assets/verification-evidence-report.md",
    "skills/mini-program-verification-skill/assets/quality-evidence-matrix.md",
    "skills/mini-program-release-skill/SKILL.md",
    "skills/mini-program-release-skill/agents/openai.yaml",
    "skills/mini-program-release-skill/references/release-governance-workflow.md",
    "skills/mini-program-release-skill/assets/release-readiness-record.md",
    "VERSION",
    "scripts/export_public_package.py",
    "scripts/capability_doctor.py",
    "scripts/scan_sensitive_content.py",
    "scripts/verify_public_package.py",
    "scripts/validate_suite.py",
)
EXCLUDED_PARTS = {".git", ".planning", "__pycache__", "tests"}
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def parse_frontmatter(path: Path) -> tuple[dict[str, str], list[str]]:
    """Parse and validate the flat official Codex frontmatter contract."""
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return {}, [f"{path}: missing YAML frontmatter delimiters"]
    block = text.split("---\n", 2)[1]
    result: dict[str, str] = {}
    current_key: str | None = None
    for line in block.splitlines():
        if line.startswith("  ") and current_key:
            result[current_key] = f"{result[current_key]} {line.strip()}".strip()
            continue
        if ":" not in line:
            errors.append(f"{path}: unsupported frontmatter line: {line}")
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        result[current_key] = value.strip().removesuffix(">-").strip()
    return result, errors


def validate_skill(path: Path, expected_name: str, *, root_skill: bool = False) -> list[str]:
    """Validate one SKILL.md against the official minimal contract."""
    errors: list[str] = []
    frontmatter, parse_errors = parse_frontmatter(path)
    errors.extend(parse_errors)
    expected_keys = {"name", "description", "license", "compatibility", "metadata"} if root_skill else {
        "name",
        "description",
    }
    if set(frontmatter) != expected_keys:
        errors.append(f"{path}: frontmatter keys do not match the supported contract")
    if frontmatter.get("name") != expected_name:
        errors.append(f"{path}: name must be {expected_name}")
    description = frontmatter.get("description", "")
    if not 80 <= len(description) <= 1024:
        errors.append(f"{path}: description length must be between 80 and 1024 characters")
    if root_skill:
        if frontmatter.get("license") != "MIT":
            errors.append(f"{path}: root license must be MIT")
        compatibility = frontmatter.get("compatibility", "")
        if not 10 <= len(compatibility) <= 500:
            errors.append(f"{path}: compatibility length must be between 10 and 500 characters")
        version = (path.parent / "VERSION").read_text(encoding="utf-8").strip()
        content_block = path.read_text(encoding="utf-8").split("---\n", 2)[1]
        if f'version: "{version}"' not in content_block:
            errors.append(f"{path}: metadata version must match VERSION")
    content = path.read_text(encoding="utf-8")
    if "TODO" in content:
        errors.append(f"{path}: unresolved TODO placeholder")
    if len(content.splitlines()) >= 500:
        errors.append(f"{path}: SKILL.md must stay below 500 lines")
    return errors


def validate_links(root: Path) -> list[str]:
    """Check relative Markdown links in public package files."""
    errors: list[str] = []
    for path in sorted(root.rglob("*.md")):
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        content = path.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(content):
            if target.startswith(("http://", "https://", "#")):
                continue
            clean_target = target.split("#", 1)[0]
            if clean_target and not (path.parent / clean_target).resolve().exists():
                errors.append(f"{path}: broken link {target}")
    return errors


def validate_openai_yaml(path: Path, skill_name: str) -> list[str]:
    """Check required UI metadata without adding a YAML dependency."""
    if not path.is_file():
        return [f"{path}: missing"]
    content = path.read_text(encoding="utf-8")
    errors = []
    for key in ("display_name:", "short_description:", "default_prompt:"):
        if key not in content:
            errors.append(f"{path}: missing {key.removesuffix(':')}")
    if f"${skill_name}" not in content:
        errors.append(f"{path}: default_prompt must mention ${skill_name}")
    return errors


def validate(root: Path) -> dict[str, object]:
    """Return a machine-readable validation report."""
    errors: list[str] = []
    for relative_path in REQUIRED_FILES:
        if not (root / relative_path).is_file():
            errors.append(f"missing required file: {relative_path}")

    root_skill = root / "SKILL.md"
    child_names = (
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
    if root_skill.is_file():
        errors.extend(validate_skill(root_skill, "mini-program-engineering-suite", root_skill=True))
    errors.extend(validate_openai_yaml(root / "agents/openai.yaml", "mini-program-engineering-suite"))
    for child_name in child_names:
        child_root = root / "skills" / child_name
        child_skill = child_root / "SKILL.md"
        if child_skill.is_file():
            errors.extend(validate_skill(child_skill, child_name))
        errors.extend(validate_openai_yaml(child_root / "agents/openai.yaml", child_name))
    errors.extend(validate_links(root))

    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if path.suffix.lower() in {".md", ".yaml", ".yml", ".json"} and "TODO" in path.read_text(encoding="utf-8"):
            errors.append(f"{path}: unresolved TODO placeholder")

    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "checked_files": len(REQUIRED_FILES),
        "skill_count": len(child_names),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Validate one suite directory and emit JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Suite root")
    args = parser.parse_args(argv)
    root = args.path.resolve()
    if not root.is_dir():
        print(json.dumps({"valid": False, "errors": ["suite path is not a directory"]}))
        return 2
    report = validate(root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
