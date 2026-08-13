#!/usr/bin/env python3
"""Contract tests for implementation, UI/device, and debugging skills."""

from __future__ import annotations

import json
import subprocess
import sys
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


SKILLS = {
    "mini-program-implementation-skill": (
        "assets/implementation-handoff.md",
        "references/implementation-workflow.md",
    ),
    "mini-program-ui-device-skill": (
        "assets/ui-device-evidence-record.md",
        "references/ui-device-workflow.md",
    ),
    "mini-program-debugging-skill": (
        "assets/debugging-report.md",
        "references/debugging-workflow.md",
    ),
}


class ThirdBatchStructureTests(unittest.TestCase):
    """Validate independent packages and their public resources."""

    def test_each_skill_has_official_metadata_and_resources(self) -> None:
        for skill_name, resources in SKILLS.items():
            with self.subTest(skill=skill_name):
                skill_root = ROOT / "skills" / skill_name
                skill_file = skill_root / "SKILL.md"
                self.assertTrue(skill_file.is_file(), skill_file)
                frontmatter = parse_frontmatter(skill_file)
                self.assertEqual(set(frontmatter), {"name", "description"})
                self.assertEqual(frontmatter["name"], skill_name)
                self.assertGreaterEqual(len(frontmatter["description"]), 80)
                self.assertNotIn("TODO", skill_file.read_text(encoding="utf-8"))

                metadata = (skill_root / "agents/openai.yaml").read_text(encoding="utf-8")
                self.assertIn(f"${skill_name}", metadata)
                for resource in resources:
                    path = skill_root / resource
                    self.assertTrue(path.is_file(), path)
                    self.assertGreater(len(path.read_text(encoding="utf-8").strip()), 300)

    def test_implementation_contract_protects_scope_and_requires_verification(self) -> None:
        content = (ROOT / "skills/mini-program-implementation-skill/SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "用户已有改动",
            "改动边界",
            "RED",
            "GREEN",
            "REFACTOR",
            "生成脚本",
            "构建产物",
            "不等于正式验收",
            "停止条件",
        ):
            self.assertIn(phrase, content)

    def test_ui_device_contract_separates_preview_integration_and_device_evidence(self) -> None:
        content = (ROOT / "skills/mini-program-ui-device-skill/SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "参考目标",
            "视觉预览",
            "用户确认",
            "正式集成",
            "最窄屏",
            "最长文案",
            "安全区",
            "键盘",
            "手势冲突矩阵",
            "真机证据",
        ):
            self.assertIn(phrase, content)

    def test_debugging_contract_requires_root_cause_and_regression_evidence(self) -> None:
        content = (ROOT / "skills/mini-program-debugging-skill/SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "最小复现",
            "证据链",
            "竞争假设",
            "默认值",
            "异步时序",
            "缓存",
            "构建版本",
            "根因",
            "回归测试",
            "同类状态",
            "延长等待",
        ):
            self.assertIn(phrase, content)

    def test_each_reference_has_representative_and_non_trigger_scenarios(self) -> None:
        for skill_name, (_, reference) in SKILLS.items():
            with self.subTest(skill=skill_name):
                content = (ROOT / "skills" / skill_name / reference).read_text(encoding="utf-8")
                for heading in ("正常场景", "边界场景", "失败场景", "不应触发"):
                    self.assertIn(heading, content)
                self.assertGreaterEqual(content.count("### 场景"), 4)
                self.assertLessEqual(content.count("### 场景"), 6)


class ThirdBatchIntegrationTests(unittest.TestCase):
    """Validate suite routing and deterministic tooling after integration."""

    def test_root_routes_to_all_third_batch_skills_as_available(self) -> None:
        content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for skill_name in SKILLS:
            self.assertIn(f"skills/{skill_name}/SKILL.md", content)
        self.assertIn("第三批资源", content)
        routing_table = content.split("| 编写或修改代码", 1)[1].split("当目标组件尚未实现", 1)[0]
        self.assertNotIn("后续批次", routing_table)

    def test_suite_validator_accepts_all_seven_child_skills(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_suite.py"), str(ROOT)],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["valid"])
        self.assertGreaterEqual(report["skill_count"], 7)
        self.assertGreaterEqual(report["checked_files"], 42)


if __name__ == "__main__":
    unittest.main()
