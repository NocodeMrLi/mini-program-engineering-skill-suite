#!/usr/bin/env python3
"""Contract tests for verification, release governance, and safe export."""

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


SKILLS = {
    "mini-program-verification-skill": (
        "assets/verification-evidence-report.md",
        "references/verification-workflow.md",
    ),
    "mini-program-release-skill": (
        "assets/release-readiness-record.md",
        "references/release-governance-workflow.md",
    ),
}


class FourthBatchStructureTests(unittest.TestCase):
    """Validate independent packages and evidence boundaries."""

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

    def test_verification_contract_calibrates_evidence_layers(self) -> None:
        content = (ROOT / "skills/mini-program-verification-skill/SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "静态检查", "单元测试", "集成测试", "状态矩阵", "真机验证", "云端验证",
            "发布验证", "已执行", "未执行", "残余风险", "版本指纹", "不等于正式验收",
        ):
            self.assertIn(phrase, content)

    def test_release_contract_separates_external_states_and_authority(self) -> None:
        content = (ROOT / "skills/mini-program-release-skill/SKILL.md").read_text(encoding="utf-8")
        for phrase in (
            "当前分支", "版本", "源码", "构建产物", "代码推送", "平台上传", "审核提交",
            "正式发布", "测试开关", "敏感信息", "权限", "隐私", "回滚", "明确授权",
        ):
            self.assertIn(phrase, content)
        self.assertIn("不得自动", content)

    def test_references_include_representative_and_non_trigger_scenarios(self) -> None:
        for skill_name, (_, reference) in SKILLS.items():
            with self.subTest(skill=skill_name):
                content = (ROOT / "skills" / skill_name / reference).read_text(encoding="utf-8")
                for heading in ("正常场景", "边界场景", "失败场景", "不应触发"):
                    self.assertIn(heading, content)
                self.assertGreaterEqual(content.count("### 场景"), 4)
                self.assertLessEqual(content.count("### 场景"), 6)


class FourthBatchIntegrationTests(unittest.TestCase):
    """Validate suite routing, versioning, and deterministic export."""

    def test_root_routes_to_all_fourth_batch_skills(self) -> None:
        content = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for skill_name in SKILLS:
            self.assertIn(f"skills/{skill_name}/SKILL.md", content)
        self.assertIn("能力地图", content)
        self.assertIn("维护脚本与公开包", content)
        self.assertNotIn("第四批，勿声称已安装", content)

    def test_suite_validator_accepts_nine_children(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_suite.py"), str(ROOT)],
            capture_output=True, check=False, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["valid"])
        self.assertEqual(report["skill_count"], 9)
        self.assertGreaterEqual(report["checked_files"], 52)

    def test_version_is_semantic(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        parts = version.split(".")
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(part.isdigit() for part in parts))

    def test_source_project_is_not_used_for_circular_skill_validation(self) -> None:
        guardrails = (ROOT / "shared/engineering-guardrails.md").read_text(encoding="utf-8")
        for phrase in ("来源项目", "循环验证", "匿名夹具", "隔离副本"):
            self.assertIn(phrase, guardrails)
        for path in ROOT.rglob("*.md"):
            if ".planning" in path.parts or "tests" in path.parts:
                continue
            if path.name in {"README.md", "README.en.md"}:
                continue
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertNotIn("语宠精灵", path.read_text(encoding="utf-8"))

    def test_export_is_deterministic_redacted_and_excludes_private_material(self) -> None:
        exporter = ROOT / "scripts/export_public_package.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            outputs = [base / "one", base / "two"]
            manifests = []
            for output in outputs:
                result = subprocess.run(
                    [sys.executable, str(exporter), str(ROOT), "--output", str(output)],
                    capture_output=True, check=False, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                manifest = json.loads((output / "package-manifest.json").read_text(encoding="utf-8"))
                manifests.append(manifest)
                self.assertEqual(manifest["suite_version"], (ROOT / "VERSION").read_text().strip())
                self.assertEqual(manifest["sensitive_finding_count"], 0)
                self.assertTrue(manifest["suite_valid"])
                self.assertFalse(any(Path(item["path"]).is_absolute() for item in manifest["files"]))
                for excluded in (".git", ".planning", "tests", "__pycache__", ".DS_Store"):
                    self.assertFalse(any(excluded in item["path"].split("/") for item in manifest["files"]))
            self.assertEqual(manifests[0], manifests[1])


if __name__ == "__main__":
    unittest.main()
