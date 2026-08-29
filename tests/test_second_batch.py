#!/usr/bin/env python3
"""Contract tests for the product, architecture, and WeChat platform skills."""

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
    "mini-program-product-spec-skill": (
        "assets/product-specification.md",
        "references/specification-workflow.md",
    ),
    "mini-program-architecture-skill": (
        "assets/architecture-decision-record.md",
        "references/architecture-workflow.md",
    ),
    "wechat-mini-program-platform-skill": (),
}


class SecondBatchStructureTests(unittest.TestCase):
    """Validate independent packages and their public resources."""

    def test_each_skill_has_official_frontmatter_metadata_and_resources(self) -> None:
        for skill_name, resources in SKILLS.items():
            with self.subTest(skill=skill_name):
                skill_root = ROOT / "skills" / skill_name
                skill_file = skill_root / "SKILL.md"
                self.assertTrue(skill_file.is_file(), skill_file)
                frontmatter = parse_frontmatter(skill_file)
                self.assertEqual(set(frontmatter), {"name", "description"})
                self.assertEqual(frontmatter["name"], skill_name)
                self.assertGreaterEqual(len(frontmatter["description"]), 80)

                metadata = (skill_root / "agents/openai.yaml").read_text(encoding="utf-8")
                self.assertIn(f"${skill_name}", metadata)
                for resource in resources:
                    path = skill_root / resource
                    self.assertTrue(path.is_file(), path)
                    self.assertGreater(len(path.read_text(encoding="utf-8").strip()), 300)

    def test_wechat_platform_facts_live_in_platform_layer(self) -> None:
        platform_dir = ROOT / "platforms" / "wechat"
        for name in (
            "platform-evidence-layers.md",
            "wechat-platform-checklist.md",
            "privacy-permission-matrix.md",
            "facts.md",
            "rule-map.json",
        ):
            path = platform_dir / name
            self.assertTrue(path.is_file(), path)
        skill = (ROOT / "skills/wechat-mini-program-platform-skill/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("../../platforms/wechat/", skill)
        rule_map = json.loads((platform_dir / "rule-map.json").read_text(encoding="utf-8"))
        self.assertEqual(rule_map["format_version"], 1)
        self.assertEqual(rule_map["platform"], "wechat")
        for rule in rule_map["rules"]:
            self.assertTrue(rule["official"]["url"].startswith("https://"))
            self.assertGreaterEqual(rule["ttl_days"], 0)

    def test_product_spec_contract_prevents_invented_product_logic(self) -> None:
        content = (ROOT / "skills/mini-program-product-spec-skill/SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "目标用户",
            "主流程",
            "异常流程",
            "状态矩阵",
            "验收标准",
            "不发明",
            "不决定代码结构",
            "停止条件",
        ):
            self.assertIn(phrase, content)

    def test_architecture_contract_covers_operational_risks_without_changing_product(self) -> None:
        content = (ROOT / "skills/mini-program-architecture-skill/SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "状态源",
            "数据模型",
            "权限",
            "幂等",
            "并发",
            "迁移",
            "回滚",
            "ADR",
            "不改变产品语义",
        ):
            self.assertIn(phrase, content)

    def test_platform_contract_separates_evidence_layers_and_current_rules(self) -> None:
        content = (ROOT / "skills/wechat-mini-program-platform-skill/SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "源码",
            "构建产物",
            "开发者工具",
            "真机",
            "体验版",
            "审核版",
            "正式版",
            "微信官方",
            "时效性",
            "AppID",
            "Secret",
        ):
            self.assertIn(phrase, content)

    def test_each_reference_has_representative_and_non_trigger_scenarios(self) -> None:
        references = {
            "mini-program-product-spec-skill": "skills/mini-program-product-spec-skill/references/specification-workflow.md",
            "mini-program-architecture-skill": "skills/mini-program-architecture-skill/references/architecture-workflow.md",
            "wechat-mini-program-platform-skill": "platforms/wechat/platform-evidence-layers.md",
        }
        for skill_name, reference in references.items():
            with self.subTest(skill=skill_name):
                content = (ROOT / reference).read_text(encoding="utf-8")
                for heading in ("正常场景", "边界场景", "失败场景", "不应触发"):
                    self.assertIn(heading, content)
                self.assertGreaterEqual(content.count("### 场景"), 4)
                self.assertLessEqual(content.count("### 场景"), 6)


class SecondBatchIntegrationTests(unittest.TestCase):
    """Validate suite routing and deterministic tooling after integration."""

    def test_root_routes_to_all_second_batch_skills_as_available(self) -> None:
        content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for skill_name in SKILLS:
            self.assertIn(f"skills/{skill_name}/SKILL.md", content)
        self.assertIn("能力地图", content)
        self.assertIn("共享模板与门禁", content)
        second_batch_table = content.split("| 梳理产品", 1)[1].split("| 编码", 1)[0]
        self.assertNotIn("后续批次", second_batch_table)

    def test_suite_validator_keeps_all_second_batch_children(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_suite.py"), str(ROOT)],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["valid"])
        self.assertGreaterEqual(report["skill_count"], 4)
        self.assertGreaterEqual(report["checked_files"], 30)


if __name__ == "__main__":
    unittest.main()
