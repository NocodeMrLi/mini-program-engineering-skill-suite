#!/usr/bin/env python3
"""Behavior tests for the first delivery batch of the skill suite."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_frontmatter(path: Path) -> dict[str, str]:
    """Parse the flat name/description frontmatter used by this suite."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    block = text.split("---\n", 2)[1]
    result: dict[str, str] = {}
    current_key: str | None = None
    for line in block.splitlines():
        if line.startswith("  ") and current_key:
            result[current_key] = f"{result[current_key]} {line.strip()}".strip()
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        result[current_key] = value.strip().removesuffix(">-").strip()
    return result


class SkillContractTests(unittest.TestCase):
    """Validate the public contracts of the root and intake skills."""

    def test_root_skill_is_actionable_and_has_official_frontmatter(self) -> None:
        skill = ROOT / "SKILL.md"
        content = skill.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(skill)

        self.assertEqual(set(frontmatter), {"name", "description", "license", "compatibility", "metadata"})
        self.assertEqual(frontmatter["name"], "mini-program-engineering-suite")
        self.assertGreaterEqual(len(frontmatter["description"]), 80)
        self.assertNotIn("TODO", content)
        self.assertIn("shared/engineering-guardrails.md", content)
        self.assertIn("skills/mini-program-project-intake-skill/SKILL.md", content)
        self.assertIn("中途问题", content)

    def test_project_intake_skill_is_read_only_and_evidence_first(self) -> None:
        skill = ROOT / "skills/mini-program-project-intake-skill/SKILL.md"
        content = skill.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(skill)

        self.assertEqual(set(frontmatter), {"name", "description"})
        self.assertEqual(frontmatter["name"], "mini-program-project-intake-skill")
        self.assertNotIn("TODO", content)
        for required in ("只读", "事实源", "未知项", "改动边界", "不修改代码"):
            self.assertIn(required, content)

    def test_shared_guardrails_and_templates_exist(self) -> None:
        required_files = [
            "shared/engineering-guardrails.md",
            "shared/evidence-status-model.md",
            "shared/decision-and-confirmation-rules.md",
            "shared/redaction-policy.md",
            "shared/documentation-boundaries.md",
            "shared/templates/project-intake.md",
            "shared/templates/implementation-plan.md",
            "shared/templates/verification-report.md",
            "shared/templates/release-checklist.md",
        ]
        for relative_path in required_files:
            path = ROOT / relative_path
            self.assertTrue(path.is_file(), relative_path)
            content = path.read_text(encoding="utf-8")
            self.assertNotIn("TODO", content, relative_path)
            self.assertGreater(len(content.strip()), 100, relative_path)


class ScriptBehaviorTests(unittest.TestCase):
    """Exercise deterministic validation and redaction gates."""

    def test_suite_validator_accepts_the_first_batch(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_suite.py"), str(ROOT)],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["valid"])
        self.assertEqual(report["errors"], [])

    def test_sensitive_scanner_distinguishes_clean_and_sensitive_content(self) -> None:
        scanner = ROOT / "scripts/scan_sensitive_content.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir)
            (fixture / "clean.md").write_text(
                "Use /path/to/project and read credentials from an environment variable.\n",
                encoding="utf-8",
            )
            clean = subprocess.run(
                [sys.executable, str(scanner), str(fixture), "--format", "json"],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
            self.assertEqual(json.loads(clean.stdout)["findings"], [])

            secret_value = "wx0123456789abcdef"
            (fixture / "private.md").write_text(
                f"appid: {secret_value}\nlocal: /Users/example/private-project\n",
                encoding="utf-8",
            )
            sensitive = subprocess.run(
                [sys.executable, str(scanner), str(fixture), "--format", "json"],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(sensitive.returncode, 1, sensitive.stdout + sensitive.stderr)
            report = json.loads(sensitive.stdout)
            rule_ids = {finding["rule_id"] for finding in report["findings"]}
            self.assertIn("wechat-appid", rule_ids)
            self.assertIn("absolute-user-path", rule_ids)
            self.assertNotIn(secret_value, sensitive.stdout)


if __name__ == "__main__":
    unittest.main()
