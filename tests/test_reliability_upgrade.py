#!/usr/bin/env python3
"""Regression tests for the 1.1.0 reliability upgrade."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "shared/evidence-status-model.md"
EXPORTER = ROOT / "scripts/export_public_package.py"
SCANNER = ROOT / "scripts/scan_sensitive_content.py"
VERIFIER = ROOT / "scripts/verify_public_package.py"

STATUS_REFERENCE_FILES = (
    "shared/templates/release-checklist.md",
    "skills/mini-program-ui-device-skill/SKILL.md",
    "skills/mini-program-ui-device-skill/references/ui-device-workflow.md",
    "skills/mini-program-release-skill/SKILL.md",
    "skills/mini-program-release-skill/references/release-governance-workflow.md",
    "skills/mini-program-release-skill/assets/release-readiness-record.md",
)


def status_definitions() -> list[str]:
    """Return identifiers defined by status-table rows in the shared model."""
    return re.findall(
        r"^\| `([a-z][a-z0-9-]*)` \|",
        MODEL.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )


def body_without_frontmatter(path: Path) -> str:
    """Exclude descriptive English prose in optional YAML frontmatter."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        return text.split("---\n", 2)[2]
    return text


def copy_public_source(destination: Path) -> None:
    """Create an anonymous source fixture without internal development material."""
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(
            ".git",
            ".planning",
            "tests",
            "__pycache__",
            ".pytest_cache",
            ".DS_Store",
        ),
    )


def run_export(source: Path, output: Path) -> subprocess.CompletedProcess[str]:
    """Run the real public exporter against an isolated source fixture."""
    return subprocess.run(
        [sys.executable, str(EXPORTER), str(source), "--output", str(output)],
        capture_output=True,
        check=False,
        text=True,
    )


def run_verify(package: Path) -> subprocess.CompletedProcess[str]:
    """Run the standalone verifier without providing an original source path."""
    return subprocess.run(
        [sys.executable, str(VERIFIER), str(package)],
        capture_output=True,
        check=False,
        text=True,
    )


class EvidenceStatusContractTests(unittest.TestCase):
    """Keep every evidence-state identifier unique and resolvable."""

    def test_status_identifiers_are_unique_and_unambiguous(self) -> None:
        definitions = status_definitions()
        self.assertEqual(len(definitions), len(set(definitions)))
        self.assertTrue(
            {
                "proposal-approved",
                "implemented",
                "review-approved",
                "accepted",
                "unknown",
                "not-ready",
            }
            <= set(definitions)
        )
        self.assertNotIn("approved", definitions)
        self.assertNotIn("integrated", definitions)

    def test_state_bearing_files_do_not_use_legacy_identifiers(self) -> None:
        for relative_path in ("shared/evidence-status-model.md", *STATUS_REFERENCE_FILES):
            with self.subTest(path=relative_path):
                body = body_without_frontmatter(ROOT / relative_path)
                self.assertNotRegex(
                    body,
                    r"(?<![a-z0-9-])(?:approved|integrated)(?![a-z0-9-])",
                )

    def test_cross_file_state_references_are_defined(self) -> None:
        defined = set(status_definitions())
        references: set[str] = set()
        for relative_path in STATUS_REFERENCE_FILES:
            body = body_without_frontmatter(ROOT / relative_path)
            references.update(re.findall(r"`([a-z][a-z0-9-]*)`", body))

        self.assertLessEqual(references, defined)
        expected_locations = {
            "proposal-approved": (
                "skills/mini-program-ui-device-skill/SKILL.md",
                "skills/mini-program-ui-device-skill/references/ui-device-workflow.md",
            ),
            "implemented": (
                "skills/mini-program-ui-device-skill/SKILL.md",
                "skills/mini-program-ui-device-skill/references/ui-device-workflow.md",
            ),
            "review-approved": (
                "shared/templates/release-checklist.md",
                "skills/mini-program-release-skill/SKILL.md",
                "skills/mini-program-release-skill/references/release-governance-workflow.md",
                "skills/mini-program-release-skill/assets/release-readiness-record.md",
            ),
        }
        for status, locations in expected_locations.items():
            for relative_path in locations:
                with self.subTest(status=status, path=relative_path):
                    self.assertIn(
                        f"`{status}`",
                        body_without_frontmatter(ROOT / relative_path),
                    )

    def test_user_acceptance_is_an_independent_dimension(self) -> None:
        content = MODEL.read_text(encoding="utf-8")
        self.assertIn("## 交付生命周期", content)
        self.assertIn("## 用户验收维度", content)
        lifecycle, acceptance = content.split("## 用户验收维度", 1)
        self.assertNotIn("| `accepted` |", lifecycle)
        self.assertIn("| `accepted` |", acceptance)
        self.assertIn("不自动", acceptance)


class PublicExportFailClosedTests(unittest.TestCase):
    """Reject every source candidate that is not explicitly public."""

    def test_dangerous_and_unknown_public_candidates_are_rejected(self) -> None:
        candidates = {
            ".env": b"MODE=fixture\n",
            ".env.local": b"MODE=fixture\n",
            ".npmrc": b"registry=https://registry.invalid/\n",
            "certificate.pem": b"fixture certificate\n",
            "signing.key": b"fixture key\n",
            "certificate.crt": b"fixture certificate\n",
            "certificate.p12": b"fixture certificate bundle\n",
            "notes.unknown": b"benign unknown extension\n",
            "payload.bin": b"\x00fixture binary\xff",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            for index, (relative_path, content) in enumerate(candidates.items()):
                with self.subTest(path=relative_path):
                    source = base / f"source-{index}"
                    copy_public_source(source)
                    (source / relative_path).write_bytes(content)
                    result = run_export(source, base / f"output-{index}")
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("public allowlist", result.stdout)
                    self.assertNotIn("fixture binary", result.stdout)

    def test_private_development_boundaries_remain_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            source = base / "source"
            output = base / "output"
            copy_public_source(source)
            private_files = (
                ".planning/private.env",
                "tests/certificate.pem",
                "__pycache__/payload.bin",
                ".pytest_cache/signing.key",
                ".git/internal.crt",
            )
            for relative_path in private_files:
                path = source / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                credential_name = "to" + "ken"
                path.write_text(
                    f"{credential_name}='fixture_private_value'\n",
                    encoding="utf-8",
                )

            result = run_export(source, output)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((output / "package-manifest.json").read_text(encoding="utf-8"))
            exported = {item["path"] for item in manifest["files"]}
            self.assertEqual(manifest["file_count"], len(manifest["files"]))
            self.assertIn("scripts/capability_doctor.py", exported)
            self.assertTrue(exported.isdisjoint(private_files))

    def test_scanner_does_not_skip_dangerous_suffixes_or_binary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir)
            credential_name = "to" + "ken"
            text_secret = f"{credential_name}='fixture_secret_value'\n".encode("utf-8")
            candidates = {
                ".env": text_secret,
                ".npmrc": text_secret,
                "private.pem": b"-----BEGIN PRIVATE KEY-----\nfixture\n",
                "private.key": b"-----BEGIN PRIVATE KEY-----\nfixture\n",
                "certificate.crt": text_secret,
                "notes.unknown": text_secret,
                "payload.bin": b"\x00fixture binary\xff",
            }
            for relative_path, content in candidates.items():
                (fixture / relative_path).write_bytes(content)

            result = subprocess.run(
                [sys.executable, str(SCANNER), str(fixture), "--format", "json"],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            found_paths = {finding["path"] for finding in report["findings"]}
            self.assertEqual(found_paths, set(candidates))
            self.assertIn("binary-content", {item["rule_id"] for item in report["findings"]})
            self.assertNotIn("fixture_secret_value", result.stdout)

    def test_extensionless_allowlisted_candidate_is_scanned_before_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            source = base / "source"
            copy_public_source(source)
            secret_marker = "fixture_secret_value"
            credential_name = "to" + "ken"
            (source / "VERSION").write_text(
                f"{credential_name}='{secret_marker}'\n",
                encoding="utf-8",
            )

            result = run_export(source, base / "output")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("sensitive-content scan failed", result.stdout)
            self.assertNotIn(secret_marker, result.stdout)

    def test_public_policy_documents_the_fail_closed_boundary(self) -> None:
        policy = (ROOT / "shared/redaction-policy.md").read_text(encoding="utf-8")
        root_skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for phrase in ("公共路径 allowlist", "未知文件默认拒绝", "二进制", "私有开发目录"):
            self.assertIn(phrase, policy)
        self.assertIn("未知文件默认拒绝", root_skill)


class PublicPackageIntegrityTests(unittest.TestCase):
    """Verify a received package without consulting its source directory."""

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_directory.name)
        self.clean_package = self.base / "clean-package"
        result = run_export(ROOT, self.clean_package)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def assert_rejected(self, package: Path, error_code: str) -> str:
        """Require a redacted nonzero verifier result with one stable error code."""
        result = run_verify(package)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(error_code, result.stdout)
        self.assertNotIn(str(package), result.stdout)
        return result.stdout

    def test_clean_export_verifies_without_original_source(self) -> None:
        result = run_verify(self.clean_package)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        manifest = json.loads(
            (self.clean_package / "package-manifest.json").read_text(encoding="utf-8")
        )
        self.assertTrue(report["valid"])
        self.assertEqual(report["verified_file_count"], manifest["file_count"])
        self.assertIn("scripts/verify_public_package.py", {item["path"] for item in manifest["files"]})
        self.assertIn(
            "scripts/verify_public_package.py",
            (self.clean_package / "SKILL.md").read_text(encoding="utf-8"),
        )

    def test_modified_file_is_rejected(self) -> None:
        target = self.clean_package / "SKILL.md"
        target.write_text(target.read_text(encoding="utf-8") + "\nfixture mutation\n", encoding="utf-8")
        self.assert_rejected(self.clean_package, "file-hash-mismatch")

    def test_deleted_file_is_rejected(self) -> None:
        (self.clean_package / "SKILL.md").unlink()
        self.assert_rejected(self.clean_package, "file-missing")

    def test_unlisted_new_file_is_rejected(self) -> None:
        (self.clean_package / "unexpected.md").write_text("fixture\n", encoding="utf-8")
        output = self.assert_rejected(self.clean_package, "unexpected-file")
        self.assertNotIn("unexpected.md", output)

    def test_damaged_manifest_is_rejected(self) -> None:
        (self.clean_package / "package-manifest.json").write_text("{", encoding="utf-8")
        self.assert_rejected(self.clean_package, "manifest-invalid")

    def test_manifest_path_traversal_variants_are_rejected(self) -> None:
        malicious_paths = ("../outside.md", "/absolute.md", "nested\\escape.md", "a/./b.md")
        for index, malicious_path in enumerate(malicious_paths):
            with self.subTest(path=malicious_path):
                package = self.base / f"path-fixture-{index}"
                shutil.copytree(self.clean_package, package)
                manifest_path = package / "package-manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["files"][0]["path"] = malicious_path
                manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                output = self.assert_rejected(package, "manifest-path-invalid")
                self.assertNotIn(malicious_path, output)


if __name__ == "__main__":
    unittest.main()
