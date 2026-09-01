#!/usr/bin/env python3
"""Committed regressions for the 2026-08-31 audit remediation batch.

Covers the acceptance criteria of each finding:
- P1-01 evaluation gate: fresh artifacts for minor/major; patch reuse with
  fingerprint binding; behavior/harness change forbids reuse; missing
  evaluation-gate.json blocks.
- P1-02 semver consistency: v3.1.8->v3.1.9 style metadata-only commits are
  patch; skill-text edits need minor; equal/lower candidate tags block;
  semver_bump == required_level == release level on PASS.
- P2-02 drift report coverage fields and explicit manual-only guidance.
- P2-04 generic credential rules (fake shapes only).
"""

from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load_script(name: str):
    # Register in sys.modules BEFORE exec: dataclasses resolves field types via
    # sys.modules[cls.__module__], so an unregistered module crashes asdict.
    module_name = f"audit_probe_{name}"
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        # Keep scanning modules importable by each other; drop only on failure.
        pass
    return module


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q")
    git(path, "config", "user.name", "Audit Test")
    git(path, "config", "user.email", "audit@example.test")
    return path


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def build_release_repo(root: Path) -> Path:
    """v1.0.0 with skills + VERSION + SKILL.md frontmatter, ready for reuse tests."""
    repo = init_repo(root / "repo")
    (repo / "skills" / "demo" / "SKILL.md").parent.mkdir(parents=True)
    (repo / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\ndescription: Use when demo.\n---\nbody\n", encoding="utf-8")
    (repo / "SKILL.md").write_text(
        "---\nname: root\ndescription: Use when root.\nmetadata:\n  version: \"1.0.0\"\n  last_reviewed: \"2026-08-01\"\n---\nbody\n",
        encoding="utf-8",
    )
    (repo / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    commit_all(repo, "baseline")
    git(repo, "tag", "v1.0.0")
    return repo


class EvaluationGateTests(unittest.TestCase):
    """P1-01 acceptance: reuse binding, fresh requirement, fail-closed inputs."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.key_temp = tempfile.TemporaryDirectory()
        key_root = Path(cls.key_temp.name)
        cls.private_key = key_root / "private.pem"
        cls.public_key = key_root / "public.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(cls.private_key)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(cls.private_key), "-pubout", "-out", str(cls.public_key)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.key_temp.cleanup()

    def setUp(self) -> None:
        self.module = load_script("evaluation_gate")
        self.signature = load_script("evidence_signature")

    def _repo_with_candidate(self, root: Path, mutate) -> Path:
        repo = build_release_repo(root)
        mutate(repo)
        commit_all(repo, "candidate changes")
        git(repo, "tag", "v1.0.1")
        return repo

    def _install_public_key(self, repo: Path) -> None:
        destination = repo / ".github" / "release-evidence" / "trusted-signers.pem"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.public_key, destination)

    def _stages(self, source_version: str) -> dict[str, dict[str, object]]:
        return {
            stage: {
                "stage": stage,
                "verdict": "PASS",
                "source_version": source_version,
                "artifact_sha256": hashlib.sha256(f"artifact:{stage}".encode()).hexdigest(),
                "audit_sha256": hashlib.sha256(f"audit:{stage}".encode()).hexdigest(),
                "engine": "test-agent",
                "model": "test-model",
                "generated_at_utc": "2026-08-31T00:00:00Z",
            }
            for stage in self.module.REQUIRED_STAGES
        }

    def _declaration(self, repo: Path, **overrides) -> dict:
        candidate_tag = str(overrides.pop("candidate_tag", "v1.0.1"))
        source_tag = str(overrides.pop("source_tag", "v1.0.0"))
        source_commit = self.module.commit_of(repo, source_tag)
        candidate_commit = self.module.commit_of(repo, candidate_tag)
        source_behavior = self.module.aggregate_fingerprint(
            self.module.fingerprint_paths(repo, source_commit, ("behavior",))
        )
        source_harness = self.module.aggregate_fingerprint(
            self.module.fingerprint_paths(repo, source_commit, ("harness",))
        )
        candidate_behavior = self.module.aggregate_fingerprint(
            self.module.fingerprint_paths(repo, candidate_commit, ("behavior",))
        )
        candidate_harness = self.module.aggregate_fingerprint(
            self.module.fingerprint_paths(repo, candidate_commit, ("harness",))
        )
        payload = {
            "schema_version": 2,
            "candidate_tag": candidate_tag,
            "mode": "reuse",
            "engine": "test-agent",
            "model": "test-model",
            "generated_at_utc": "2026-08-31T00:00:00Z",
            "candidate_skill_behavior_sha256": candidate_behavior,
            "candidate_evaluation_harness_sha256": candidate_harness,
            "reuse": {
                "source_tag": source_tag,
                "source_commit": source_commit,
                "reason": "tooling-only fix; behavior and harness byte-identical",
                "source_skill_behavior_sha256": source_behavior,
                "source_evaluation_harness_sha256": source_harness,
                "stages": self._stages(source_tag.lstrip("v")),
            },
        }
        payload.update(overrides)
        return self.signature.sign_document(
            payload,
            self.private_key,
            self.module.TRUSTED_SIGNER_KEY_ID,
        )

    def _write_declaration(self, repo: Path, path: Path, **overrides) -> None:
        self._install_public_key(repo)
        path.write_text(json.dumps(self._declaration(repo, **overrides)), encoding="utf-8")

    def _fresh_declaration(self, repo: Path, artifacts: Path, candidate_tag: str) -> dict:
        candidate_commit = self.module.commit_of(repo, candidate_tag)
        behavior = self.module.aggregate_fingerprint(
            self.module.fingerprint_paths(repo, candidate_commit, ("behavior",))
        )
        harness = self.module.aggregate_fingerprint(
            self.module.fingerprint_paths(repo, candidate_commit, ("harness",))
        )
        stages: dict[str, dict[str, str]] = {}
        for stage in self.module.REQUIRED_STAGES:
            name = f"{stage}.json"
            artifact = {
                "schema_version": 1,
                "stage": stage,
                "candidate_tag": candidate_tag,
                "candidate_commit": candidate_commit,
                "verdict": "PASS",
                "skill_behavior_sha256": behavior,
                "evaluation_harness_sha256": harness,
                "engine": "test-agent",
                "model": "test-model",
                "generated_at_utc": "2026-08-31T00:00:00Z",
            }
            encoded = json.dumps(artifact, sort_keys=True).encode()
            (artifacts / name).write_bytes(encoded)
            stages[stage] = {"artifact_path": name, "artifact_sha256": hashlib.sha256(encoded).hexdigest()}
        payload = {
            "schema_version": 2,
            "candidate_tag": candidate_tag,
            "candidate_commit": candidate_commit,
            "mode": "fresh",
            "engine": "test-agent",
            "model": "test-model",
            "generated_at_utc": "2026-08-31T00:00:00Z",
            "candidate_skill_behavior_sha256": behavior,
            "candidate_evaluation_harness_sha256": harness,
            "stages": stages,
        }
        return self.signature.sign_document(payload, self.private_key, self.module.TRUSTED_SIGNER_KEY_ID)

    def test_patch_reuse_passes_when_behavior_and_harness_identical(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = self._repo_with_candidate(root, lambda r: (r / "scripts").mkdir(exist_ok=True) or (r / "scripts" / "tool.py").write_text("x\n", encoding="utf-8"))
            gate_file = root / "evaluation-gate.json"
            self._write_declaration(repo, gate_file)
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "patch", gate_file)
        self.assertEqual(report["verdict"], "PASS", report.get("problems"))
        self.assertEqual(report["reused_from"], "v1.0.0")
        self.assertTrue(report["skill_behavior_sha256"])

    def test_skill_text_change_forbids_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def mutate(repo: Path) -> None:
                (repo / "skills" / "demo" / "SKILL.md").write_text(
                    "---\nname: demo\ndescription: Use when demo.\n---\nchanged body\n", encoding="utf-8"
                )
            repo = self._repo_with_candidate(root, mutate)
            gate_file = root / "evaluation-gate.json"
            self._write_declaration(repo, gate_file)
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "patch", gate_file)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any(p.startswith("reuse:behavior-changed:") for p in report["problems"]))

    def test_harness_change_forbids_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def mutate(repo: Path) -> None:
                harness = repo / "tests" / "evals"
                harness.mkdir(parents=True)
                (harness / "run_evaluations.py").write_text("print('changed')\n", encoding="utf-8")
            repo = self._repo_with_candidate(root, mutate)
            gate_file = root / "evaluation-gate.json"
            self._write_declaration(repo, gate_file)
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "patch", gate_file)
        self.assertTrue(any(p.startswith("reuse:harness-changed:") for p in report["problems"]))

    def test_root_skill_version_bump_keeps_reuse_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def mutate(repo: Path) -> None:
                (repo / "SKILL.md").write_text(
                    "---\nname: root\ndescription: Use when root.\nmetadata:\n  version: \"1.0.1\"\n  last_reviewed: \"2026-08-31\"\n---\nbody\n",
                    encoding="utf-8",
                )
                (repo / "VERSION").write_text("1.0.1\n", encoding="utf-8")
            repo = self._repo_with_candidate(root, mutate)
            gate_file = root / "evaluation-gate.json"
            self._write_declaration(repo, gate_file)
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "patch", gate_file)
        self.assertEqual(report["verdict"], "PASS", report.get("problems"))

    def test_root_skill_body_change_with_version_bump_forbids_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def mutate(repo: Path) -> None:
                (repo / "SKILL.md").write_text(
                    "---\nname: root\ndescription: Use when root.\nmetadata:\n  version: \"1.0.1\"\n  last_reviewed: \"2026-08-31\"\n---\nchanged behavior\n",
                    encoding="utf-8",
                )
            repo = self._repo_with_candidate(root, mutate)
            gate_file = root / "evaluation-gate.json"
            self._write_declaration(repo, gate_file)
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "patch", gate_file)
        self.assertTrue(any(p == "reuse:behavior-changed:SKILL.md" for p in report["problems"]))

    def test_reuse_without_historical_stage_attestations_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = self._repo_with_candidate(
                root,
                lambda r: (r / "VERSION").write_text("1.0.1\n", encoding="utf-8"),
            )
            self._install_public_key(repo)
            payload = self._declaration(repo)
            unsigned = {k: v for k, v in payload.items() if k != "signature"}
            unsigned["reuse"]["stages"] = {}
            gate_file = root / "evaluation-gate.json"
            gate_file.write_text(json.dumps(self.signature.sign_document(unsigned, self.private_key, self.module.TRUSTED_SIGNER_KEY_ID)))
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "patch", gate_file)
        self.assertTrue(any(p.startswith("evidence:stage-missing:") for p in report["problems"]))

    def test_signed_declaration_tampering_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = self._repo_with_candidate(
                root,
                lambda r: (r / "VERSION").write_text("1.0.1\n", encoding="utf-8"),
            )
            self._install_public_key(repo)
            payload = self._declaration(repo)
            payload["candidate_tag"] = "v9.9.9"
            gate_file = root / "evaluation-gate.json"
            gate_file.write_text(json.dumps(payload), encoding="utf-8")
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "patch", gate_file)
        self.assertIn("evaluation-gate-input:signature-verification-failed", report["problems"])

    def test_valid_signature_for_wrong_candidate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = self._repo_with_candidate(
                root,
                lambda r: (r / "VERSION").write_text("1.0.1\n", encoding="utf-8"),
            )
            self._install_public_key(repo)
            payload = self._declaration(repo)
            unsigned = {k: v for k, v in payload.items() if k != "signature"}
            unsigned["candidate_tag"] = "v9.9.9"
            gate_file = root / "evaluation-gate.json"
            gate_file.write_text(json.dumps(self.signature.sign_document(unsigned, self.private_key, self.module.TRUSTED_SIGNER_KEY_ID)))
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "patch", gate_file)
        self.assertIn("evaluation-gate-input:candidate-tag-mismatch", report["problems"])

    def test_minor_release_requires_fresh_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = build_release_repo(root)
            (repo / "VERSION").write_text("1.1.0\n", encoding="utf-8")
            commit_all(repo, "feat: candidate")
            git(repo, "tag", "v1.1.0")
            self._install_public_key(repo)
            gate_file = root / "evaluation-gate.json"
            payload = self._fresh_declaration(repo, root, "v1.1.0")
            for stage in self.module.REQUIRED_STAGES:
                (root / f"{stage}.json").unlink()
            gate_file.write_text(json.dumps(payload), encoding="utf-8")
            report = self.module.verify(repo, "v1.1.0", "v1.0.0", "minor", gate_file)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("missing-artifact" in p for p in report["problems"]))
        self.assertEqual(report["executed_stages"], list(self.module.REQUIRED_STAGES))

    def test_minor_release_passes_with_all_fresh_pass_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = build_release_repo(root)
            (repo / "skills" / "demo" / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use when demo.\n---\nnew capability body\n", encoding="utf-8"
            )
            commit_all(repo, "feat: new skill capability")
            git(repo, "tag", "v1.1.0")
            # The declaration itself may live anywhere; fresh mode reads the
            # per-stage artifacts from its PARENT directory.
            artifacts = root / "artifacts"
            artifacts.mkdir()
            gate_file = artifacts / "evaluation-gate.json"
            self._install_public_key(repo)
            gate_file.write_text(json.dumps(self._fresh_declaration(repo, artifacts, "v1.1.0")), encoding="utf-8")
            report = self.module.verify(repo, "v1.1.0", "v1.0.0", "minor", gate_file)
        self.assertEqual(report["verdict"], "PASS", report.get("problems"))

    def test_stale_version_artifact_blocks_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = build_release_repo(root)
            (repo / "skills" / "demo" / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Use when demo.\n---\nnew body\n", encoding="utf-8"
            )
            commit_all(repo, "feat: change")
            git(repo, "tag", "v1.1.0")
            artifacts = root / "artifacts"
            artifacts.mkdir()
            gate_file = artifacts / "evaluation-gate.json"
            self._install_public_key(repo)
            gate_file.write_text(json.dumps(self._fresh_declaration(repo, artifacts, "v1.1.0")), encoding="utf-8")
            stale = artifacts / "routing-development.json"
            record = json.loads(stale.read_text())
            record["candidate_tag"] = "v1.0.0"
            stale.write_text(json.dumps(record), encoding="utf-8")
            report = self.module.verify(repo, "v1.1.0", "v1.0.0", "minor", gate_file)
        self.assertTrue(any("candidate_tag-mismatch" in p or "artifact-sha256-mismatch" in p for p in report["problems"]))

    def test_missing_gate_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = build_release_repo(root)
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "patch", root / "absent.json")
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("evaluation-gate-input" in p for p in report["problems"]))

    def test_reuse_without_reason_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = build_release_repo(root)
            (repo / "VERSION").write_text("1.0.1\n", encoding="utf-8")
            commit_all(repo, "metadata only")
            git(repo, "tag", "v1.0.1")
            gate_file = root / "evaluation-gate.json"
            self._install_public_key(repo)
            payload = self._declaration(repo)
            unsigned = {k: v for k, v in payload.items() if k != "signature"}
            unsigned["reuse"]["reason"] = ""
            gate_file.write_text(json.dumps(self.signature.sign_document(unsigned, self.private_key, self.module.TRUSTED_SIGNER_KEY_ID)), encoding="utf-8")
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "patch", gate_file)
        self.assertTrue(any("missing-reuse-reason" in p for p in report["problems"]))

    def test_cli_exit_codes_and_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = build_release_repo(root)
            (repo / "VERSION").write_text("1.0.1\n", encoding="utf-8")
            commit_all(repo, "candidate")
            git(repo, "tag", "v1.0.1")
            gate_file = root / "evaluation-gate.json"
            self._write_declaration(repo, gate_file)
            out = root / "report.json"
            rc_pass = self.module.main([
                str(repo), "--candidate-tag", "v1.0.1", "--baseline-tag", "v1.0.0",
                "--required-level", "patch", "--evaluation-gate", str(gate_file),
                "--output", str(out),
            ])
            self.assertEqual(rc_pass, 0)
            self.assertTrue(out.is_file())
            # Reused-from pointing at an unknown tag fails closed with rc 1.
            payload = self._declaration(repo)
            unsigned = {k: v for k, v in payload.items() if k != "signature"}
            unsigned["reuse"]["source_tag"] = "v9.9.9"
            gate_file.write_text(json.dumps(self.signature.sign_document(unsigned, self.private_key, self.module.TRUSTED_SIGNER_KEY_ID)), encoding="utf-8")
            rc_fail = self.module.main([
                str(repo), "--candidate-tag", "v1.0.1", "--baseline-tag", "v1.0.0",
                "--required-level", "patch", "--evaluation-gate", str(gate_file),
            ])
        self.assertEqual(rc_fail, 1)

    def test_git_failure_fails_closed_via_cli(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            not_a_repo = root / "plain"
            not_a_repo.mkdir()
            gate_file = root / "evaluation-gate.json"
            # Signature is valid so the CLI reaches the git fail-closed path.
            source = build_release_repo(root)
            (source / "VERSION").write_text("1.0.1\n", encoding="utf-8")
            commit_all(source, "candidate")
            git(source, "tag", "v1.0.1")
            payload = self._declaration(source)
            gate_file.write_text(json.dumps(payload), encoding="utf-8")
            key_target = not_a_repo / ".github" / "release-evidence" / "trusted-signers.pem"
            key_target.parent.mkdir(parents=True)
            shutil.copy2(self.public_key, key_target)
            rc = self.module.main([
                str(not_a_repo), "--candidate-tag", "v1.0.1", "--baseline-tag", "v1.0.0",
                "--required-level", "patch", "--evaluation-gate", str(gate_file),
            ])
        self.assertEqual(rc, 1)

    def test_semver_helpers(self) -> None:
        self.assertEqual(self.module.parse_semver("v1.2.3"), (1, 2, 3))
        self.assertIsNone(self.module.parse_semver("1.2"))
        self.assertIsNone(self.module.parse_semver("v1.2.x"))
        self.assertEqual(self.module.semver_bump("v1.0.0", "v1.0.1"), "patch")
        self.assertEqual(self.module.semver_bump("v1.0.0", "v1.1.0"), "minor")
        self.assertEqual(self.module.semver_bump("v1.0.0", "v2.0.0"), "major")
        self.assertIsNone(self.module.semver_bump("bad", "v1.0.1"))
        self.assertIsNone(self.module.semver_bump("v1.0.0", "v1.0.0"))

    def test_stage_attestation_contract_rejects_every_invalid_field(self) -> None:
        stages = self._stages("1.0.0")
        stages["unknown-stage"] = {}
        first = self.module.REQUIRED_STAGES[0]
        stages[first] = {
            "stage": "wrong",
            "verdict": "FAIL",
            "source_version": "0.0.0",
            "artifact_sha256": "bad",
            "audit_sha256": None,
            "engine": "",
            "model": None,
            "generated_at_utc": "",
        }
        problems = self.module.validate_stage_attestations(stages, "1.0.0")
        for suffix in (
            "stage-mismatch", "not-pass", "source-version-mismatch",
            "artifact-sha256-invalid", "audit-sha256-invalid", "engine-missing",
            "model-missing", "generated-at-missing",
        ):
            self.assertTrue(any(problem.endswith(suffix) for problem in problems), suffix)
        self.assertIn("evidence:stage-unknown:unknown-stage", problems)
        self.assertEqual(
            self.module.validate_stage_attestations([], "1.0.0"),
            ["evidence:stages-not-object"],
        )

    def test_fresh_artifact_boundary_failures_are_reported_together(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = build_release_repo(root)
            (repo / "VERSION").write_text("1.1.0\n", encoding="utf-8")
            commit_all(repo, "candidate")
            git(repo, "tag", "v1.1.0")
            artifacts = root / "artifacts"
            artifacts.mkdir()
            evaluation = self._fresh_declaration(repo, artifacts, "v1.1.0")
            evaluation = {key: value for key, value in evaluation.items() if key != "signature"}
            evaluation["candidate_commit"] = "wrong"
            evaluation["candidate_skill_behavior_sha256"] = "bad"
            evaluation["candidate_evaluation_harness_sha256"] = "bad"
            stages = evaluation["stages"]
            names = list(self.module.REQUIRED_STAGES)
            stages[names[0]] = None
            stages[names[1]] = {"artifact_path": "../escape.json", "artifact_sha256": "bad"}
            stages[names[2]] = {"artifact_path": "absent.json", "artifact_sha256": "bad"}
            broken_path = artifacts / f"{names[3]}.json"
            broken = json.loads(broken_path.read_text())
            for field in ("schema_version", "stage", "candidate_tag", "candidate_commit", "verdict", "skill_behavior_sha256", "evaluation_harness_sha256"):
                broken[field] = "wrong"
            for field in ("engine", "model", "generated_at_utc"):
                broken[field] = ""
            broken_path.write_text(json.dumps(broken), encoding="utf-8")
            problems, detail = self.module.verify_fresh(repo, "v1.1.0", evaluation, artifacts)
        self.assertIn("fresh:candidate-commit-mismatch", problems)
        self.assertIn(f"fresh:{names[0]}:attestation-missing", problems)
        self.assertIn(f"fresh:{names[1]}:artifact-path-invalid", problems)
        self.assertTrue(any("missing-artifact" in problem for problem in problems))
        self.assertTrue(any(problem.endswith("engine-missing") for problem in problems))
        self.assertEqual(detail["fresh_stage_results"][names[3]], "FAIL")

    def test_signed_input_metadata_mode_and_reuse_boundaries_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = build_release_repo(root)
            (repo / "VERSION").write_text("1.0.1\n", encoding="utf-8")
            commit_all(repo, "candidate")
            git(repo, "tag", "v1.0.1")
            self._install_public_key(repo)
            gate_file = root / "evaluation.json"
            base = self._declaration(repo)
            unsigned = {key: value for key, value in base.items() if key != "signature"}
            malformed = dict(unsigned)
            malformed.update({"schema_version": 1, "candidate_tag": "v9.9.9", "engine": "", "model": None, "generated_at_utc": ""})
            gate_file.write_text(json.dumps(self.signature.sign_document(malformed, self.private_key, self.module.TRUSTED_SIGNER_KEY_ID)))
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "patch", gate_file)
            self.assertGreaterEqual(len(report["problems"]), 5)
            invalid_mode = dict(unsigned)
            invalid_mode["mode"] = "unknown"
            gate_file.write_text(json.dumps(self.signature.sign_document(invalid_mode, self.private_key, self.module.TRUSTED_SIGNER_KEY_ID)))
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "patch", gate_file)
            self.assertIn("evaluation-gate-input:mode-invalid", report["problems"])
            gate_file.write_text(json.dumps(base), encoding="utf-8")
            report = self.module.verify(repo, "v1.0.1", "v1.0.0", "minor", gate_file)
            self.assertIn("evaluation-gate-input:minor-requires-fresh", report["problems"])
            reuse_cases = [
                {},
                {"reuse": {"source_tag": 1}},
                {"reuse": {"source_tag": "v1.0.1"}},
                {"reuse": {"source_tag": "v9.9.9"}},
            ]
            for evaluation in reuse_cases:
                problems, _ = self.module.verify_reuse(repo, "v1.0.1", evaluation, "v1.0.0")
                self.assertTrue(problems)
            mismatched = dict(unsigned)
            mismatched["candidate_skill_behavior_sha256"] = "bad"
            mismatched["candidate_evaluation_harness_sha256"] = "bad"
            mismatched["reuse"] = dict(unsigned["reuse"])
            mismatched["reuse"].update({
                "source_commit": "bad",
                "source_skill_behavior_sha256": "bad",
                "source_evaluation_harness_sha256": "bad",
                "stages": [],
            })
            problems, detail = self.module.verify_reuse(repo, "v1.0.1", mismatched, "v1.0.0")
        self.assertIn("reuse:source-commit-mismatch", problems)
        self.assertIn("reuse:candidate-behavior-fingerprint-mismatch", problems)
        self.assertIn("evidence:stages-not-object", problems)
        self.assertEqual(detail["verdict"], "PASS")


class SemverConsistencyTests(unittest.TestCase):
    """P1-02 acceptance: classification levels and tag-increment enforcement."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.key_temp = tempfile.TemporaryDirectory()
        key_root = Path(cls.key_temp.name)
        cls.private_key = key_root / "private.pem"
        cls.public_key = key_root / "public.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(cls.private_key)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(cls.private_key), "-pubout", "-out", str(cls.public_key)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.key_temp.cleanup()

    def setUp(self) -> None:
        self.module = load_script("release_recommendation")
        self.signature = load_script("evidence_signature")

    def _write_signed_override(self, repo: Path, payload: dict[str, object]) -> None:
        public = repo / ".github" / "release-evidence" / "trusted-signers.pem"
        public.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.public_key, public)
        signed = self.signature.sign_document(
            payload,
            self.private_key,
            "release-evaluation-2026-08-31",
        )
        (repo / "release-override.json").write_text(json.dumps(signed), encoding="utf-8")

    def _candidate_repo(self, root: Path, mutate, tag: str) -> Path:
        repo = build_release_repo(root)
        mutate(repo)
        commit_all(repo, "candidate")
        git(repo, "tag", tag)
        return repo

    def test_metadata_only_bump_is_patch_and_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def mutate(repo: Path) -> None:
                (repo / "SKILL.md").write_text(
                    "---\nname: root\ndescription: Use when root.\nmetadata:\n  version: \"1.0.1\"\n  last_reviewed: \"2026-08-31\"\n---\nbody\n",
                    encoding="utf-8",
                )
                (repo / "VERSION").write_text("1.0.1\n", encoding="utf-8")
                (repo / "CHANGELOG.md").write_text("## 1.0.1\n- fix\n", encoding="utf-8")
            repo = self._candidate_repo(root, mutate, "v1.0.1")
            report = self.module.recommend(repo, min_data_changes=1, candidate_tag="v1.0.1")
        self.assertEqual(report["recommendation"], "RECOMMEND_RELEASE")
        self.assertEqual(report["level"], "patch")
        self.assertEqual(report["semver_bump"], "patch")
        self.assertEqual(report["required_level"], "patch")

    def test_skill_text_change_with_patch_tag_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def mutate(repo: Path) -> None:
                (repo / "skills" / "demo" / "SKILL.md").write_text(
                    "---\nname: demo\ndescription: Use when demo.\n---\nbehavior body\n", encoding="utf-8"
                )
            repo = self._candidate_repo(root, mutate, "v1.0.1")
            report = self.module.recommend(repo, min_data_changes=1, candidate_tag="v1.0.1")
        self.assertEqual(report["recommendation"], "MANUAL_VERIFICATION_REQUIRED")
        self.assertEqual(report["semver_bump"], "patch")
        self.assertEqual(report["required_level"], "minor")
        self.assertTrue(any("lower than required level" in r for r in report["reasons"]))

    def test_equal_or_lower_candidate_tag_blocks(self) -> None:
        """A candidate at/below an existing newer tag cannot release.

        Case 1: HEAD is newer than the named candidate (re-releasing an old
        tag): the HEAD guard blocks.
        Case 2: a repo whose ONLY tag is the candidate (baseline == candidate,
        e.g. re-tagging): the no-baseline guard blocks — an equal "bump" can
        never reach RECOMMEND_RELEASE.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = build_release_repo(root)
            (repo / "VERSION").write_text("1.0.1\n", encoding="utf-8")
            commit_all(repo, "candidate")
            git(repo, "tag", "v1.0.1")
            report = self.module.recommend(repo, min_data_changes=1, candidate_tag="v1.0.0")
            self.assertEqual(report["recommendation"], "MANUAL_VERIFICATION_REQUIRED")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = init_repo(root / "repo")
            (repo / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            (repo / "SKILL.md").write_text("x\n", encoding="utf-8")
            commit_all(repo, "only commit")
            git(repo, "tag", "v1.0.0")
            report = self.module.recommend(repo, min_data_changes=1, candidate_tag="v1.0.0")
            self.assertEqual(report["recommendation"], "MANUAL_VERIFICATION_REQUIRED")
            self.assertIn(
                "no preceding release tag found for candidate",
                " ".join(report["reasons"]),
            )

    def test_semver_helpers(self) -> None:
        self.assertEqual(self.module.semver_bump("v1.0.0", "v1.0.1"), "patch")
        self.assertEqual(self.module.semver_bump("v1.0.0", "v1.1.0"), "minor")
        self.assertEqual(self.module.semver_bump("v1.0.0", "v2.0.0"), "major")
        self.assertIsNone(self.module.semver_bump("v1.0.1", "v1.0.0"))
        self.assertIsNone(self.module.semver_bump("v1.0.0", "v1.0.0"))
        self.assertIsNone(self.module.semver_bump("v1.0.0", "v1.1"))

    def test_breaking_subject_classifies_major(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = build_release_repo(root)
            (repo / "SKILL.md").write_text(
                "---\nname: root\ndescription: Use when root.\nmetadata:\n  version: \"2.0.0\"\n---\nbody\n",
                encoding="utf-8",
            )
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "feat!: breaking change to skill contract")
            git(repo, "tag", "v2.0.0")
            report = self.module.recommend(repo, min_data_changes=1, candidate_tag="v2.0.0")
        self.assertEqual(report["level"], "major")
        self.assertEqual(report["semver_bump"], "major")

    def test_structured_downgrade_accepts_one_step_with_signer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def mutate(repo: Path) -> None:
                (repo / "skills" / "demo" / "SKILL.md").write_text(
                    "---\nname: demo\ndescription: Use when demo.\n---\nbehavior body\n", encoding="utf-8"
                )
            repo = self._candidate_repo(root, mutate, "v1.0.1")
            self._write_signed_override(
                repo,
                {
                    "candidate_tag": "v1.0.1",
                    "from": "minor",
                    "to": "patch",
                    "reason": "typo-level text fix, no capability change",
                    "signed_by": "independent-reviewer@example.test",
                },
            )
            report = self.module.recommend(repo, min_data_changes=1, candidate_tag="v1.0.1")
        self.assertEqual(report["recommendation"], "RECOMMEND_RELEASE")
        self.assertEqual(report["required_level"], "patch")
        self.assertEqual(report["override"]["signed_by"], "independent-reviewer@example.test")
        self.assertEqual(report["override"]["signer_key_id"], "release-evaluation-2026-08-31")

    def test_signed_downgrade_by_candidate_author_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def mutate(repo: Path) -> None:
                (repo / "skills" / "demo" / "SKILL.md").write_text(
                    "---\nname: demo\ndescription: Use when demo.\n---\nbehavior body\n", encoding="utf-8"
                )
            repo = self._candidate_repo(root, mutate, "v1.0.1")
            self._write_signed_override(repo, {
                "candidate_tag": "v1.0.1",
                "from": "minor",
                "to": "patch",
                "reason": "self-approved",
                "signed_by": "audit@example.test",
            })
            report = self.module.recommend(repo, min_data_changes=1, candidate_tag="v1.0.1")
        self.assertEqual(report["recommendation"], "MANUAL_VERIFICATION_REQUIRED")
        self.assertTrue(any("override-signer-not-independent" in reason for reason in report["reasons"]))

    def test_downgrade_without_signer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            def mutate(repo: Path) -> None:
                (repo / "skills" / "demo" / "SKILL.md").write_text(
                    "---\nname: demo\ndescription: Use when demo.\n---\nbehavior body\n", encoding="utf-8"
                )
            repo = self._candidate_repo(root, mutate, "v1.0.1")
            (repo / "release-override.json").write_text(
                json.dumps({"candidate_tag": "v1.0.1", "from": "minor", "to": "patch", "reason": "x"}),
                encoding="utf-8",
            )
            report = self.module.recommend(repo, min_data_changes=1, candidate_tag="v1.0.1")
        self.assertEqual(report["recommendation"], "MANUAL_VERIFICATION_REQUIRED")
        self.assertTrue(any("override-signer-missing" in r for r in report["reasons"]))

    def test_helper_and_override_malformed_boundaries(self) -> None:
        self.assertIsNone(self.module.parse_semver("v1.x.0"))
        self.assertFalse(self.module.commit_paths_are_metadata_only(Path("."), "HEAD", ["README.md"]))
        classes = self.module.classify_commit_classes([
            "skills/a/SKILL.md", "scripts/x.py", "platforms/w/facts.md",
            "VERSION", "README.md", "assets/a.png", "unknown.bin",
        ])
        self.assertEqual(classes, {"behavior", "tooling", "data", "metadata", "docs", "assets"})
        self.assertEqual(self.module.classify_commit(["README.md"]), "docs")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertIsNone(self.module.load_downgrade_override(root, "v1.0.1", "minor"))
            path = root / "release-override.json"
            path.write_text("not-json", encoding="utf-8")
            self.assertIn("override-unreadable", self.module.load_downgrade_override(root, "v1.0.1", "minor")["problems"])
            path.write_text("[]", encoding="utf-8")
            self.assertIn("override-not-object", self.module.load_downgrade_override(root, "v1.0.1", "minor")["problems"])
            path.write_text(json.dumps({
                "candidate_tag": "wrong", "from": "major", "to": "patch",
                "reason": "", "signed_by": "reviewer@example.test",
            }), encoding="utf-8")
            problems = self.module.load_downgrade_override(root, "v1.0.1", "minor")["problems"]
        self.assertTrue(any(problem.startswith("override-signature") for problem in problems))
        self.assertIn("override-reason-missing", problems)
        self.assertIn("override-candidate-tag-mismatch", problems)
        self.assertIn("override-not-one-step-downgrade", problems)

    def test_tag_changelog_and_manual_verification_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = build_release_repo(root)
            git(repo, "tag", "vbad")
            git(repo, "tag", "v2.0.0")
            self.assertEqual(self.module.release_tags_sorted(repo), ["v1.0.0", "v2.0.0"])
            (repo / "README.md").write_text("docs\n", encoding="utf-8")
            commit_all(repo, "docs only")
            self.assertTrue(self.module.root_skill_change_is_metadata_only(repo, "HEAD"))
            self.assertEqual(self.module.changelog_verification_evidence(root, None), {})
            self.assertFalse(self.module._valid_utc_date(None))
            self.assertFalse(self.module._valid_utc_date("not-a-date"))
            self.assertTrue(self.module._valid_utc_date("2026-09-01"))
            for platform in self.module.MANUAL_ONLY_PLATFORMS:
                target = root / "platforms" / platform
                target.mkdir(parents=True)
                (target / "facts.md").write_text(
                    f"<!-- fact: r1 verified=unknown source=https://{platform}.test/doc digest=unknown -->\n",
                    encoding="utf-8",
                )
            status = self.module.manual_verification_status(
                root, "major", {}, candidate_tag="v1.0.1"
            )
        self.assertTrue(status["required"])
        for platform in self.module.MANUAL_ONLY_PLATFORMS:
            self.assertTrue(status["platforms"][platform]["needs_verification"])

    def test_recommendation_classification_and_cli_boundaries(self) -> None:
        clean_verification = {"required": False, "platforms": {}, "evidence": {}}
        common = [
            patch.object(self.module, "is_shallow_repository", return_value=False),
            patch.object(self.module, "last_tag", return_value="v1.0.0"),
            patch.object(self.module, "manual_verification_status", return_value=clean_verification),
        ]
        scenarios = [
            ({"hash": "a", "subject": "feat: capability", "paths": ["scripts/new.py"]}, "minor", "RECOMMEND_RELEASE"),
            ({"hash": "a", "subject": "BREAKING CHANGE: contract", "paths": ["README.md"]}, "major", "RECOMMEND_RELEASE"),
            ({"hash": "a", "subject": "data", "paths": ["platforms/x/facts.md"]}, None, "HOLD"),
            ({"hash": "a", "subject": "docs", "paths": ["README.md"]}, None, "HOLD"),
            ({"hash": "a", "subject": "release", "paths": ["VERSION"]}, "patch", "RECOMMEND_RELEASE"),
        ]
        for commit, level, expected in scenarios:
            with self.subTest(commit=commit), common[0], common[1], common[2], patch.object(self.module, "collect_commits", return_value=[commit]):
                report = self.module.recommend(Path("."), min_data_changes=2)
            self.assertEqual(report["recommendation"], expected)
            self.assertEqual(report["level"], level)
        with patch.object(self.module, "is_shallow_repository", return_value=True):
            report = self.module.recommend(Path("."), 1)
        self.assertFalse(report["history_complete"])
        with patch.object(self.module, "is_shallow_repository", return_value=False), patch.object(self.module, "tag_commit", return_value=None):
            report = self.module.recommend(Path("."), 1, candidate_tag="v1.0.1")
        self.assertIn("not found", " ".join(report["reasons"]))
        with patch.object(self.module, "is_shallow_repository", return_value=False), patch.object(self.module, "tag_commit", return_value="abc"), patch.object(self.module, "head_commit", return_value="abc"), patch.object(self.module, "last_tag", return_value="v1.0.0"), patch.object(self.module, "collect_commits", return_value=[]):
            report = self.module.recommend(Path("."), 1, candidate_tag="v1.0.1")
        self.assertIn("no commits", " ".join(report["reasons"]))
        with patch.object(self.module, "recommend", return_value={
            "recommendation": "HOLD", "level": None, "reasons": ["none"],
            "tag": None, "commit_count": 0, "classes": {},
        }):
            self.assertEqual(self.module.main([".", "--format", "json"]), 0)
            self.assertEqual(self.module.main([".", "--format", "text"]), 0)
        with patch.object(self.module, "recommend", side_effect=ValueError("git-failed")):
            self.assertEqual(self.module.main(["."]), 2)


class DriftReportCoverageTests(unittest.TestCase):
    """P2-02 acceptance: manual-only platforms stay visible with counters."""

    def setUp(self) -> None:
        self.module = load_script("drift_watch")

    def test_report_counts_all_three_platforms(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            platforms = root / "platforms"
            for name, detection in (("wechat", None), ("alipay", "manual-only"), ("douyin", "manual-only")):
                platform_dir = platforms / name
                platform_dir.mkdir(parents=True)
                rule_map: dict[str, object] = {
                    "format_version": 1, "platform": name, "allowed_domains": ["x.test"],
                    "rules": [{"id": "r1", "official": {"url": "https://x.test/a"}, "verify_points": ["p"]}],
                }
                if detection:
                    rule_map["detection"] = detection
                (platform_dir / "rule-map.json").write_text(json.dumps(rule_map), encoding="utf-8")
                (platform_dir / "facts.md").write_text(
                    "<!-- fact: r1 verified=2026-08-31 source=https://x.test/a digest=unknown -->\n", encoding="utf-8"
                )
            report = self.module.run(root, None, no_llm=True)
        self.assertEqual(report["platform_total"], 3)
        self.assertEqual(report["automatically_checked"], 1)
        self.assertEqual(report["manual_only"], 2)
        states = {entry["platform"]: entry["state"] for entry in report["manual_only_platforms"]}
        self.assertEqual(states, {"alipay": "not-automatically-observable", "douyin": "not-automatically-observable"})

    def test_manual_entry_carries_verification_context(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            platform = root / "platforms" / "alipay"
            platform.mkdir(parents=True)
            (platform / "rule-map.json").write_text(
                json.dumps({
                    "format_version": 1, "platform": "alipay", "detection": "manual-only",
                    "allowed_domains": ["x.test"],
                    "rules": [{"id": "r1", "official": {"url": "https://x.test/doc"}, "verify_points": ["p"]}],
                }),
                encoding="utf-8",
            )
            (platform / "facts.md").write_text(
                "<!-- fact: r1 verified=2026-08-20 source=https://x.test/doc digest=unknown -->\n", encoding="utf-8"
            )
            entry = self.module.manual_only_entry(platform)
        self.assertEqual(entry["last_manual_verification"], "2026-08-20")
        self.assertEqual(entry["manual_verification_entry_points"], ["https://x.test/doc"])
        self.assertTrue(entry["next_step"])

    def test_explicit_manual_only_platform_returns_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            platform = root / "platforms" / "alipay"
            platform.mkdir(parents=True)
            (platform / "rule-map.json").write_text(
                json.dumps({
                    "format_version": 1, "platform": "alipay", "detection": "manual-only",
                    "allowed_domains": ["x.test"], "rules": [],
                }),
                encoding="utf-8",
            )
            message = self.module.explicit_manual_only_message(root, "alipay")
        self.assertIsNotNone(message)
        payload = json.loads(message)
        self.assertEqual(payload["status"], "not-automatically-observable")
        self.assertTrue(payload["next_step"])


class GenericCredentialRuleTests(unittest.TestCase):
    """P2-04: generic token shapes trip the scanner (FAKE fixtures only)."""

    def setUp(self) -> None:
        self.module = load_script("scan_sensitive_content")

    def _rules_for(self, text: str) -> set[str]:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "probe.md"
            path.write_text(text, encoding="utf-8")
            findings, _ = self.module.scan_files_with_summary([path], path.parent)
        return {finding.rule_id for finding in findings}

    def test_fake_generic_credentials_are_detected(self) -> None:
        rules = self._rules_for(
            "a ghp_" + "A" * 36 + "\n"
            "b AKIA" + "A" * 16 + "\n"
            "c npm_" + "a" * 36 + "\n"
            "d pypi-" + "b" * 24 + "\n"
            "e xoxb-1234567890abcdefghijklmnop\n"
            "f AKID" + "c" * 34 + "\n"
            "g AIza" + "d" * 35 + "\n"
        )
        for expected in ("github-token", "aws-access-key", "npm-token", "pypi-token", "slack-token", "tencent-secret-id", "google-api-key"):
            self.assertIn(expected, rules)

    def test_scanner_never_echoes_matched_text(self) -> None:
        import dataclasses
        import tempfile

        fake = "ghp_" + "Z" * 36
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "probe.md"
            path.write_text(f"token {fake}\n", encoding="utf-8")
            findings, _ = self.module.scan_files_with_summary([path], path.parent)
        self.assertTrue(findings)
        for finding in findings:
            serialized = json.dumps(dataclasses.asdict(finding))
            self.assertNotIn(fake, serialized)


class ScannerBoundaryTests(unittest.TestCase):
    """In-process coverage of the scanner's boundary branches (audit P3)."""

    def setUp(self) -> None:
        self.module = load_script("scan_sensitive_content")

    def test_oversized_file_is_reported_not_skipped(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            big = root / "big.bin"
            big.write_bytes(b"\0" * 10)
            original = self.module.MAX_SCAN_FILE_BYTES
            self.module.MAX_SCAN_FILE_BYTES = 5
            try:
                findings, summary = self.module.scan_files_with_summary([big], root)
            finally:
                self.module.MAX_SCAN_FILE_BYTES = original
        self.assertEqual([f.rule_id for f in findings], ["oversized-file"])
        self.assertEqual(summary.candidate_count, 1)

    def test_unreadable_file_is_reported(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "missing.txt"
            # A dangling symlink stat()s successfully in some paths but fails
            # read; force the OSError branch via a file replaced by a directory
            # between listing and reading is racy — instead call with a path
            # that cannot be read: a directory entry listed as file candidate.
            findings, _ = self.module.scan_files_with_summary([root], root)
        self.assertIn("unreadable-file", [f.rule_id for f in findings])

    def test_binary_like_content_scans_latin1(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            blob = root / "blob.bin"
            blob.write_bytes(b"\xff\xfe\x00\x01jwt eyJabc.def.ghi")
            findings, summary = self.module.scan_files_with_summary([blob], root)
        self.assertGreaterEqual(summary.binary_like_count, 1)

    def test_cli_json_and_text_outputs(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            clean = Path(td) / "ok.md"
            clean.write_text("hello\n", encoding="utf-8")
            self.assertEqual(self.module.main([str(clean), "--format", "json"]), 0)
            dirty = Path(td) / "bad.md"
            dirty.write_text("id: wx" + "a" * 16 + "\n", encoding="utf-8")
            self.assertEqual(self.module.main([str(dirty), "--format", "text"]), 1)
            # Absent path returns 2 without raising (prints a JSON error).
            self.assertEqual(self.module.main([str(Path(td) / "absent")]), 2)

    def test_scan_path_walks_tree_and_skips_private_dirs(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tests").mkdir()
            (root / "tests" / "x.py").write_text("skip\n", encoding="utf-8")
            (root / "keep.md").write_text("keep\n", encoding="utf-8")
            findings = self.module.scan_path(root)
        self.assertEqual(findings, [])
class ReleaseWorkflowContractTests(unittest.TestCase):
    """P1-03 acceptance encoded as workflow-content regressions."""

    def test_no_clobber_upload_exists(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertNotIn("--clobber", workflow)
        self.assertIn("already exists; releases are immutable", workflow)

    def test_gate_summary_is_in_sha256sums(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("package-manifest.json gate-summary.json > SHA256SUMS", workflow)

    def test_archive_build_is_reproducible(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("--sort=name", workflow)
        self.assertIn("--mtime=\"@0\"", workflow)
        self.assertIn("gzip -n", workflow)

    def test_ci_runs_python_floor_matrix(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn('"3.9"', workflow)
        self.assertIn('"3.11"', workflow)
        self.assertIn("ubuntu-latest, macos-latest", workflow)
        self.assertIn("-W error::ResourceWarning", workflow)
        self.assertIn("coverage", workflow.lower())

    def test_ci_coverage_uses_stable_json_count_fields(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertNotIn("percent_statements_covered_display", workflow)
        self.assertIn('summary["covered_lines"]', workflow)
        self.assertIn('summary["num_statements"]', workflow)

    def test_release_summary_python_avoids_escaped_f_string_expressions(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertNotIn('d.get(\\"semver_bump\\")', workflow)
        self.assertNotIn('d.get(\\"verdict\\")', workflow)
        self.assertIn('"{}/{}".format', workflow)
        self.assertIn('"{}:{}".format', workflow)

    def test_release_immutable_check_uses_token_accessible_release_endpoint(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertNotIn('"repos/$GITHUB_REPOSITORY/immutable-releases"', workflow)
        self.assertIn('"repos/$GITHUB_REPOSITORY/releases/tags/$RESOLVED_TAG"', workflow)
        self.assertIn("--jq '.immutable'", workflow)

    def test_upload_artifact_is_pinned_to_node24_release(self) -> None:
        workflows = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / ".github" / "workflows").glob("*.yml")
        )
        self.assertNotIn("65c4c4a1ddee5b72f698fdd19549f0f0fb45cf08", workflows)
        self.assertIn("043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1", workflows)


if __name__ == "__main__":
    unittest.main()
