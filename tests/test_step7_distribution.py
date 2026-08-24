from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOT_DOCS = ("README.md", "LICENSE", "CHANGELOG.md", "COMPATIBILITY.md")


class DistributionContractTests(unittest.TestCase):
    def test_root_has_one_copy_of_distribution_documents(self) -> None:
        for name in ROOT_DOCS:
            self.assertTrue((ROOT / name).is_file(), name)
            self.assertEqual(list((ROOT / "skills").rglob(name)), [], name)

    def test_root_frontmatter_uses_allowed_open_fields(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        block = text.split("---\n", 2)[1]
        for key in ("name:", "description:", "license:", "compatibility:", "metadata:"):
            self.assertIn(key, block)
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertIn(f'version: "{version}"', block)
        for key in ("author:", "created:", "last_reviewed:", "review_interval_days:"):
            self.assertIn(key, block)
        self.assertNotIn("activation:", block)
        self.assertNotIn("provenance:", block)

    def test_docs_cover_source_integrity_compatibility_and_rollback(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for term in ("可信来源", "VERSION", "package-manifest.json", "verify_public_package.py", "SHA-256", "回滚"):
            self.assertIn(term, readme)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("1.1.0", changelog)
        self.assertIn("1.0.0", changelog)
        compatibility = (ROOT / "COMPATIBILITY.md").read_text(encoding="utf-8")
        for term in ("Python 3.9", "原生微信小程序", "Taro", "uni-app", "可选", "不自动安装"):
            self.assertIn(term, compatibility)
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Permission is hereby granted", license_text)

    def test_validator_and_exporter_accept_distribution_files(self) -> None:
        validation = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_suite.py"), str(ROOT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "public"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/export_public_package.py"), str(ROOT), "--output", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((output / "package-manifest.json").read_text(encoding="utf-8"))
            exported = {item["path"] for item in manifest["files"]}
            self.assertTrue(set(ROOT_DOCS).issubset(exported))
            self.assertFalse(any(item.startswith(("tests/", ".planning/")) for item in exported))

    def test_public_docs_do_not_contain_private_project_or_user_paths(self) -> None:
        content = "\n".join((ROOT / name).read_text(encoding="utf-8") for name in ROOT_DOCS)
        for forbidden in ("/Users/", ".planning/", "tests/evals/"):
            self.assertNotIn(forbidden, content)

    def test_readme_may_show_authorized_origin_case_without_private_material(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("真实项目来源：语宠精灵", readme)
        self.assertIn("assets/wordpet-origin-case.png", readme)
        for phrase in ("不包含该小程序源码", "AppID", "云资源", "私有配置", "业务数据", "审核状态"):
            self.assertIn(phrase, readme)


if __name__ == "__main__":
    unittest.main()
