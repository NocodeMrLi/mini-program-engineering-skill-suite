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
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "shared/evidence-status-model.md"
EXPORTER = ROOT / "scripts/export_public_package.py"
I18N_CHECKER = ROOT / "scripts/check_i18n_readme_structure.py"
INSTALLER = ROOT / "install.sh"
SCANNER = ROOT / "scripts/scan_sensitive_content.py"
VALIDATOR = ROOT / "scripts/validate_suite.py"
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

    def test_root_planning_debris_is_not_silently_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            source = base / "source"
            copy_public_source(source)
            (source / "task_plan.md").write_text("local planning debris\n", encoding="utf-8")

            result = run_export(source, base / "output")

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("public allowlist", result.stdout)

    def test_single_planning_named_file_is_still_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir) / "task_plan.md"
            credential_name = "to" + "ken"
            secret_marker = "fixture_secret_value"
            fixture.write_text(f"{credential_name}='{secret_marker}'\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCANNER), str(fixture), "--format", "json"],
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["scanned_count"], 1)
        self.assertEqual(report["finding_count"], 1)
        self.assertEqual(report["findings"][0]["path"], "task_plan.md")
        self.assertNotIn(secret_marker, result.stdout)

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
                "payload.bin": text_secret + b"\xff",
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
            self.assertEqual(report["candidate_count"], len(candidates))
            self.assertEqual(report["scanned_count"], len(candidates))
            self.assertGreaterEqual(report["binary_like_count"], 1)
            self.assertEqual(report["unreadable_file_count"], 0)
            found_paths = {finding["path"] for finding in report["findings"]}
            self.assertEqual(found_paths, set(candidates))
            self.assertEqual(report["finding_count"], len(candidates))
            by_path = {finding["path"]: finding for finding in report["findings"]}
            self.assertEqual(by_path["payload.bin"]["rule_id"], "credential-assignment")
            self.assertEqual(
                by_path["payload.bin"]["display_rule_id"],
                "binary-file:credential-assignment",
            )
            self.assertEqual(by_path["payload.bin"]["source_kind"], "binary-like")
            self.assertNotIn("fixture_secret_value", result.stdout)

    def test_scanner_detects_mini_program_cloud_and_account_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = Path(temp_dir) / "release-notes.md"
            sensitive_lines = [
                "env" + "Id=cloud1-" + "fixtureenv123",
                "owner=" + "keeper" + "@example.invalid",
                "phone=" + "138" + "00138000",
                "jwt=eyJ" + "aaaaaaaaaaaa.bbbbbbbbbbbb.cccccccccccc",
                "bucket=" + "demo-" + "12345.cos.ap-shanghai.myqcloud.com",
            ]
            fixture.write_text("\n".join(sensitive_lines) + "\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCANNER), str(fixture), "--format", "json"],
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        rule_ids = {finding["rule_id"] for finding in report["findings"]}
        self.assertGreaterEqual(
            rule_ids,
            {
                "cloud-env-id",
                "email-address",
                "mainland-phone-number",
                "jwt-token",
                "cos-bucket-host",
            },
        )
        for sensitive_value in sensitive_lines:
            self.assertNotIn(sensitive_value, result.stdout)

    def test_capability_doctor_survives_unreadable_root_entries(self) -> None:
        from scripts.capability_doctor import inspect_project

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "package.json").write_text("{\"scripts\":{}}", encoding="utf-8")
            with patch.object(Path, "iterdir", side_effect=OSError("denied")):
                report = inspect_project(root)

        self.assertEqual(report["framework"], "unknown")
        self.assertIn("unreadable-root-directory", report["warnings"])

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

    def test_promo_duration_validator_ignores_unrelated_seconds_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            copy_public_source(source)
            readme = source / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8") + "\n补充说明：首屏目标加载时间为 3 秒。\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(VALIDATOR), str(source)],
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_promo_duration_validator_rejects_video_context_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source"
            copy_public_source(source)
            readme = source / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace("32 秒说明视频", "30 秒说明视频"),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(VALIDATOR), str(source)],
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("README promo video duration says 30", result.stdout)

    def test_i18n_readme_structure_checker_accepts_current_readmes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(I18N_CHECKER), str(ROOT)],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["valid"])
        self.assertEqual(report["checked_readmes"], 6)

    def test_installer_uses_verified_public_payload_without_manifest_debris(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            fake_home = base / "home"
            target_parent = fake_home / ".agents" / "skills"
            target_parent.mkdir(parents=True)

            result = subprocess.run(
                [
                    "bash",
                    str(INSTALLER),
                    "--target",
                    "agents",
                    "--home",
                    str(fake_home),
                    "--source",
                    str(ROOT),
                ],
                capture_output=True,
                check=False,
                text=True,
            )

            installed = target_parent / "mini-program-engineering-suite"
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertTrue((installed / "scripts" / "verify_public_package.py").is_file())
            self.assertFalse((installed / "package-manifest.json").exists())

    def test_installer_codex_and_agents_targets_match_public_docs(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("~/.codex/skills/mini-program-engineering-suite", readme)
        self.assertIn("~/.agents/skills/mini-program-engineering-suite", readme)
        self.assertIn("codex  Install to ~/.codex/skills", installer)
        self.assertIn("agents Install to ~/.agents/skills", installer)

        with tempfile.TemporaryDirectory() as temp_dir:
            fake_home = Path(temp_dir) / "home"
            for target, expected in (
                ("codex", fake_home / ".codex" / "skills" / "mini-program-engineering-suite"),
                ("agents", fake_home / ".agents" / "skills" / "mini-program-engineering-suite"),
            ):
                result = subprocess.run(
                    [
                        "bash",
                        str(INSTALLER),
                        "--target",
                        target,
                        "--home",
                        str(fake_home),
                        "--source",
                        str(ROOT),
                        "--dry-run",
                    ],
                    capture_output=True,
                    check=False,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(str(expected), result.stdout)


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
        self.assertFalse((self.clean_package / "scripts" / "__pycache__").exists())

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
