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


class ReceiverVersionBindingTests(unittest.TestCase):
    """Audit fix: the verifier must bind manifest version metadata to VERSION."""

    @classmethod
    def setUpClass(cls) -> None:
        import importlib.util
        import sys

        scripts_dir = str(ROOT / "scripts")
        sys.path.insert(0, scripts_dir)
        try:
            spec = importlib.util.spec_from_file_location(
                "verify_public_package_test", ROOT / "scripts" / "verify_public_package.py"
            )
            cls.verifier = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.verifier)
        finally:
            sys.path.remove(scripts_dir)

    def make_package(self, temp: str, manifest_version: str, file_version: str) -> Path:
        package = Path(temp) / "pkg"
        package.mkdir(parents=True, exist_ok=True)
        (package / "VERSION").write_text(file_version, encoding="utf-8")
        return package

    def test_matching_versions_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = self.make_package(temp, "3.1.4", "3.1.4\n")
            errors: set[str] = set()
            self.verifier.check_version_binding(
                package, {"suite_version": "3.1.4"}, errors
            )
        self.assertEqual(errors, set())

    def test_mismatched_manifest_version_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = self.make_package(temp, "9.9.9", "3.1.4\n")
            errors: set[str] = set()
            self.verifier.check_version_binding(
                package, {"suite_version": "9.9.9"}, errors
            )
        self.assertIn("version-metadata-mismatch", errors)

    def test_missing_version_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "empty"
            package.mkdir()
            errors: set[str] = set()
            self.verifier.check_version_binding(package, {"suite_version": "3.1.4"}, errors)
        self.assertIn("version-metadata-mismatch", errors)

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


class VerifyPackageWholePipelineTests(unittest.TestCase):
    """In-process coverage of verify_package()'s full branch set (audit P3).

    The subprocess-driven tests above exercise the CLI but are invisible to
    in-process coverage measurement; these drive the same entry directly.
    """

    @classmethod
    def setUpClass(cls) -> None:
        import importlib.util

        # validate_suite (imported by the verifier) does __import__ on sibling
        # scripts, so scripts/ must be importable in THIS process.
        scripts_dir = str(ROOT / "scripts")
        sys.path.insert(0, scripts_dir)
        cls._scripts_dir = scripts_dir
        spec = importlib.util.spec_from_file_location(
            "verify_public_package_pipeline", ROOT / "scripts/verify_public_package.py"
        )
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules["verify_public_package_pipeline"] = cls.module
        spec.loader.exec_module(cls.module)

    @classmethod
    def tearDownClass(cls) -> None:
        sys.path.remove(cls._scripts_dir)

    def _real_export(self, temp: str) -> Path:
        output = Path(temp) / "public"
        subprocess.run(
            [sys.executable, str(ROOT / "scripts/export_public_package.py"), str(ROOT), "--output", str(output)],
            check=True, capture_output=True, text=True,
        )
        return output

    def test_real_export_passes_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = self._real_export(temp)
            report = self.module.verify_package(package)
        self.assertTrue(report["valid"], report["errors"])
        self.assertGreater(report["verified_file_count"], 100)

    def test_tampered_file_hash_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = self._real_export(temp)
            target = package / "VERSION"
            target.write_text("9.9.9\n", encoding="utf-8")
            report = self.module.verify_package(package)
        self.assertFalse(report["valid"])
        self.assertTrue({"file-size-mismatch", "file-hash-mismatch", "suite-structure-invalid"} & set(report["errors"]))

    def test_unexpected_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = self._real_export(temp)
            (package / "smuggled.txt").write_text("x", encoding="utf-8")
            report = self.module.verify_package(package)
        self.assertFalse(report["valid"])
        self.assertIn("unexpected-file", report["errors"])

    def test_missing_package_and_broken_manifest_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            absent = Path(temp) / "nope"
            report = self.module.verify_package(absent)
            self.assertFalse(report["valid"])
            self.assertIn("package-invalid", report["errors"])
            broken = Path(temp) / "broken"
            broken.mkdir()
            (broken / "package-manifest.json").write_text("{not json", encoding="utf-8")
            report = self.module.verify_package(broken)
        self.assertFalse(report["valid"])
        self.assertTrue(report["errors"])

    # --- Guard-function negative paths, in-process (audit P3 coverage) ---

    def test_manifest_guard_branches(self) -> None:
        module = self.module
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp)
            (package / "package-manifest.json").write_text("{}", encoding="utf-8")
            # symlinked manifest
            link_dir = Path(temp) / "linkpkg"
            link_dir.mkdir()
            real = package / "real-manifest.json"
            real.write_text("{}", encoding="utf-8")
            (link_dir / "package-manifest.json").symlink_to(real)
            errors: set[str] = set()
            self.assertIsNone(module.load_manifest(link_dir, errors))
            self.assertIn("manifest-invalid", errors)
            # oversized manifest
            big_dir = Path(temp) / "bigpkg"
            big_dir.mkdir()
            (big_dir / "package-manifest.json").write_text("x" * 3000, encoding="utf-8")
            errors = set()
            self.assertIsNone(module.load_manifest(big_dir, errors))
            # duplicate keys
            dup_dir = Path(temp) / "duppkg"
            dup_dir.mkdir()
            (dup_dir / "package-manifest.json").write_text('{"a":1,"a":2}', encoding="utf-8")
            errors = set()
            self.assertIsNone(module.load_manifest(dup_dir, errors))
            # missing manifest
            empty_dir = Path(temp) / "emptypkg"
            empty_dir.mkdir()
            errors = set()
            self.assertIsNone(module.load_manifest(empty_dir, errors))
            self.assertIn("manifest-missing", errors)
            # non-object manifest
            arr_dir = Path(temp) / "arrpkg"
            arr_dir.mkdir()
            (arr_dir / "package-manifest.json").write_text("[]", encoding="utf-8")
            errors = set()
            self.assertIsNone(module.load_manifest(arr_dir, errors))

    def test_parse_entries_rejects_hostile_paths_and_duplicates(self) -> None:
        module = self.module
        base = {
            "format_version": 1,
            "suite_name": "mini-program-engineering-suite",
            "suite_version": "1.0.0",
            "suite_valid": True,
            "sensitive_finding_count": 0,
            "file_count": 2,
        }
        digest = "a" * 64
        cases = {
            "absolute": {"files": [{"path": "/etc/passwd", "size": 1, "sha256": digest}, {"path": "VERSION", "size": 1, "sha256": digest}]},
            "traversal": {"files": [{"path": "../escape", "size": 1, "sha256": digest}, {"path": "VERSION", "size": 1, "sha256": digest}]},
            "duplicate": {"files": [{"path": "VERSION", "size": 1, "sha256": digest}, {"path": "VERSION", "size": 1, "sha256": digest}]},
            "bad-hash": {"files": [{"path": "VERSION", "size": 1, "sha256": "zz"}, {"path": "a.md", "size": 1, "sha256": digest}]},
            "no-version": {"files": [{"path": "a.md", "size": 1, "sha256": digest}]},
            "count-mismatch": {"files": [{"path": "VERSION", "size": 1, "sha256": digest}], "file_count": 5},
        }
        for label, overrides in cases.items():
            with self.subTest(case=label):
                manifest = dict(base)
                manifest.update(overrides)
                errors: set[str] = set()
                result = module.parse_entries(manifest, errors)
                self.assertTrue(errors or result is None, label)

    def test_actual_package_files_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp)
            (package / "real.txt").write_text("x", encoding="utf-8")
            (package / "link.txt").symlink_to(package / "real.txt")
            errors: set[str] = set()
            files = self.module.actual_package_files(package, errors)
        self.assertEqual(files, {"real.txt"})
        self.assertIn("unsupported-file", errors)

    def test_version_binding_edge_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp)
            (package / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            errors: set[str] = set()
            self.module.check_version_binding(package, {"suite_version": "1.0.0"}, errors)
            self.assertEqual(errors, set())
            self.module.check_version_binding(package, {"suite_version": 7}, errors)
            self.assertIn("version-metadata-mismatch", errors)
            empty = Path(temp) / "empty"
            empty.mkdir()
            errors = set()
            self.module.check_version_binding(empty, {"suite_version": "1.0.0"}, errors)
            self.assertIn("version-metadata-mismatch", errors)


if __name__ == "__main__":
    unittest.main()
