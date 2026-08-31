#!/usr/bin/env python3
"""Boundary coverage for release governance and drift failure paths.

These tests intentionally exercise fail-closed branches.  They are not filler:
each case represents an input or infrastructure fault that must never be
mistaken for a passing release or a clean platform-drift result.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load_script(name: str):
    module_name = f"quality_boundary_{name}"
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self.payload


class EvidenceSignatureBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cls.private = root / "private.pem"
        cls.public = root / "public.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(cls.private)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["openssl", "pkey", "-in", str(cls.private), "-pubout", "-out", str(cls.public)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def setUp(self) -> None:
        self.module = load_script("evidence_signature")

    def test_every_malformed_signature_shape_is_rejected(self) -> None:
        cases = [
            ({}, "signature-missing"),
            ({"signature": {}}, "signature-algorithm-invalid"),
            ({"signature": {"algorithm": "rsa-sha256"}}, "signature-key-id-missing"),
            ({"signature": {"algorithm": "rsa-sha256", "key_id": "other", "value": "x"}}, "signature-key-id-untrusted"),
            ({"signature": {"algorithm": "rsa-sha256", "key_id": "trusted"}}, "signature-value-missing"),
        ]
        for document, expected in cases:
            with self.subTest(expected=expected), self.assertRaisesRegex(self.module.SignatureError, expected):
                self.module.verify_signed_document(document, self.public, expected_key_id="trusted")
        valid_shape = {"signature": {"algorithm": "rsa-sha256", "key_id": "trusted", "value": "%%%"}}
        with self.assertRaisesRegex(self.module.SignatureError, "trusted-public-key-missing"):
            self.module.verify_signed_document(valid_shape, Path(self.temp.name) / "absent.pem", expected_key_id="trusted")
        with self.assertRaisesRegex(self.module.SignatureError, "signature-base64-invalid"):
            self.module.verify_signed_document(valid_shape, self.public, expected_key_id="trusted")

    def test_crypto_process_failures_are_closed(self) -> None:
        signed = self.module.sign_document({"value": 1}, self.private, "trusted")
        signed["value"] = 2
        with self.assertRaisesRegex(self.module.SignatureError, "signature-verification-failed"):
            self.module.verify_signed_document(signed, self.public, expected_key_id="trusted")
        with self.assertRaisesRegex(self.module.SignatureError, "private-key-missing"):
            self.module.sign_document({}, Path(self.temp.name) / "absent.pem", "trusted")
        with patch.object(self.module.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(self.module.SignatureError, "openssl-not-available"):
                self.module._run_openssl([])
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"failed")
        with patch.object(self.module, "_run_openssl", return_value=failed):
            with self.assertRaisesRegex(self.module.SignatureError, "signature-generation-failed"):
                self.module.sign_document({}, self.private, "trusted")


class PlatformDriftBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_script("platform_drift")
        self.rule = {
            "id": "r1",
            "official": {"url": "https://docs.test/rule", "title": "Expected"},
            "verify_points": ["point-a"],
        }

    def test_fetch_failures_and_size_limit_are_fail_closed(self) -> None:
        self.assertIn("domain-not-allowlisted", self.module.fetch("https://evil.test/x", ["docs.test"])[1])
        opener = Mock()
        opener.open.side_effect = self.module.RedirectBlocked("redirect-off-allowlist:evil.test")
        with patch.object(self.module.urllib.request, "build_opener", return_value=opener):
            self.assertEqual(self.module.fetch("https://docs.test/x", ["docs.test"])[1], "redirect-off-allowlist:evil.test")
        opener.open.side_effect = urllib.error.URLError("redirect-off-allowlist:evil.test")
        with patch.object(self.module.urllib.request, "build_opener", return_value=opener):
            self.assertEqual(self.module.fetch("https://docs.test/x", ["docs.test"])[1], "redirect-off-allowlist:evil.test")
        opener.open.side_effect = TimeoutError()
        with patch.object(self.module.urllib.request, "build_opener", return_value=opener):
            self.assertEqual(self.module.fetch("https://docs.test/x", ["docs.test"])[1], "fetch-failed:TimeoutError")
        opener.open.side_effect = None
        opener.open.return_value = _Response(b"x" * 11)
        with patch.object(self.module, "MAX_PAGE_BYTES", 10), patch.object(self.module.urllib.request, "build_opener", return_value=opener):
            self.assertEqual(self.module.fetch("https://docs.test/x", ["docs.test"])[1], "page-too-large")
        opener.open.return_value = _Response(b"Expected body")
        with patch.object(self.module.urllib.request, "build_opener", return_value=opener):
            self.assertEqual(self.module.fetch("https://docs.test/x", ["docs.test"]), ("Expected body", None))

    def test_extract_schema_and_engine_boundaries(self) -> None:
        invalid = [
            None,
            {},
            {"verify_points": []},
            {"verify_points": ["bad"]},
            {"verify_points": [{"point": 1, "current_statement": "x"}]},
            {"verify_points": [{"point": "", "current_statement": "x"}]},
            {"verify_points": [{"point": "point-a", "current_statement": "x"}] * 2},
            {"verify_points": [{"point": "other", "current_statement": "x"}]},
        ]
        for payload in invalid:
            self.assertFalse(self.module._extract_payload_valid(payload, ["point-a"]))
        valid = {"verify_points": [{"point": "point-a", "current_statement": "current"}]}
        self.assertTrue(self.module._extract_payload_valid(valid, ["point-a"]))
        with patch.object(self.module, "run_agent", return_value=("", "engine-down")):
            self.assertEqual(self.module.l2_extract("u", ["point-a"], "page")[1], "extract-engine-failed")
        with patch.object(self.module, "run_agent", return_value=("not-json", None)):
            self.assertIn("invalid-extract-output", self.module.l2_extract("u", ["point-a"], "page")[1])
        with patch.object(self.module, "run_agent", return_value=(json.dumps({"verify_points": []}), None)):
            self.assertEqual(self.module.l2_extract("u", ["point-a"], "page")[1], "extract-output-shape-invalid")
        with patch.object(self.module, "run_agent", return_value=(json.dumps(valid), None)):
            self.assertEqual(self.module.l2_extract("u", ["point-a"], "page"), (valid, None))

    def test_rule_state_machine_covers_all_verdicts(self) -> None:
        annotations = {"f1": {"source": "https://docs.test/rule", "digest": "unknown", "verified": "unknown", "text": "old"}}
        with patch.object(self.module, "fetch", return_value=(None, "fetch-failed")):
            self.assertEqual(self.module.check_rule(self.rule, annotations, ["docs.test"], False)["state"], "unverifiable")
        with patch.object(self.module, "fetch", return_value=("other page", None)):
            self.assertEqual(self.module.check_rule(self.rule, annotations, ["docs.test"], False)["error"], "expected-title-missing")
        empty_title = dict(self.rule)
        empty_title["official"] = {"url": "https://docs.test/rule", "title": ""}
        with patch.object(self.module, "fetch", return_value=("<script>x</script>", None)):
            self.assertEqual(self.module.check_rule(empty_title, annotations, ["docs.test"], False)["error"], "empty-normalized-text")
        page = "<p>Expected current body</p>"
        digest = self.module.normalized_fingerprint(page)
        known = {"f1": {**annotations["f1"], "digest": digest, "verified": "2026-01-01"}}
        with patch.object(self.module, "fetch", return_value=(page, None)):
            self.assertEqual(self.module.check_rule(self.rule, known, ["docs.test"], False)["state"], "unchanged")
        with patch.object(self.module, "fetch", return_value=(page, None)), patch.object(self.module, "l2_extract", return_value=(None, "bad")):
            self.assertIn("l2-failed", self.module.check_rule(self.rule, annotations, ["docs.test"], False)["error"])
        updated = {"verify_points": [{"point": "point-a", "current_statement": "now"}]}
        with patch.object(self.module, "fetch", return_value=(page, None)), patch.object(self.module, "l2_extract", return_value=(updated, None)):
            self.assertEqual(self.module.check_rule(self.rule, annotations, ["docs.test"], False)["state"], "updated")
        conflict = {"verify_points": [{"point": "point-a", "current_statement": "NOT_STATED"}]}
        with patch.object(self.module, "fetch", return_value=(page, None)), patch.object(self.module, "l2_extract", return_value=(conflict, None)):
            self.assertEqual(self.module.check_rule(self.rule, annotations, ["docs.test"], False)["state"], "conflicting")

    def test_run_proposal_and_cli_error_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "rule-map.json").write_text(json.dumps({"platform": "demo", "allowed_domains": ["docs.test"], "rules": [self.rule]}))
            (root / "facts.md").write_text("- 事实：old\n<!-- fact: f1 verified=unknown source=https://docs.test/rule digest=unknown -->\n")
            outcome = {"rule_id": "r1", "state": "updated", "url": "https://docs.test/rule", "fingerprint": "a" * 64, "reason": "changed", "extracted_statements": {"point-a": "now"}}
            with patch.object(self.module, "check_rule", return_value=outcome):
                report = self.module.run(root, None, False)
            self.assertEqual(report["proposal"]["changes"][0]["proposed_fact_updates"]["f1"]["current_text"], "old")
            with self.assertRaisesRegex(ValueError, "unknown-rule"):
                self.module.run(root, "absent", False)
            proposal = root / "proposal.json"
            with patch.object(self.module, "run", return_value=report), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.module.main([str(root), "--format", "md", "--proposal-out", str(proposal)]), 0)
            self.assertTrue(proposal.is_file())
            with patch.object(self.module, "run", side_effect=ValueError("bad")), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.module.main([str(root)]), 2)


class DriftWatchBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_script("drift_watch")

    def _platform(self, root: Path, name: str, detection: str | None = None) -> Path:
        target = root / "platforms" / name
        target.mkdir(parents=True)
        data = {"platform": name, "allowed_domains": ["docs.test"], "rules": [{"id": "r1", "official": {"url": "https://docs.test/r"}}]}
        if detection:
            data["detection"] = detection
        (target / "rule-map.json").write_text(json.dumps(data))
        (target / "facts.md").write_text("<!-- fact: r1 verified=unknown source=https://docs.test/r digest=unknown -->\n")
        return target

    def test_directory_filters_explicit_scope_and_blocked_l2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            auto = self._platform(root, "auto")
            self._platform(root, "manual", "manual-only")
            self.assertEqual([p.name for p in self.module.platform_dirs(root, None)], ["auto"])
            self.assertEqual([p.name for p in self.module.manual_only_platforms(root)], ["manual"])
            self.assertEqual(self.module.platform_dirs(root, "absent"), [])
            with patch.object(self.module, "check_rule", side_effect=self.module.L2Blocked):
                report = self.module.deterministic_check(auto)
            self.assertEqual(report["counts"], {"fingerprint-changed": 1})
            scoped = self.module.run(root, "manual", True)
            self.assertEqual(scoped["manual_only"], 1)
            self.assertIn("auto", scoped["skipped_platforms"])
        self.assertEqual(self.module.platform_dirs(Path(td), None), [])
        self.assertEqual(self.module.manual_only_platforms(Path(td)), [])

    def test_issue_emission_reports_notification_failures(self) -> None:
        report = {"platforms": [{"platform": "demo", "results": [{"rule_id": "r1", "state": "unverifiable", "url": "u", "error": "x"}]}]}
        with patch.object(self.module, "gh_available", return_value=False), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.emit_issues(report, None), 0)
        with patch.object(self.module, "gh_available", return_value=True), patch.object(self.module, "existing_open_issues", return_value={"[Drift] demo: r1 -> unverifiable"}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.emit_issues(report, None), 0)
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="denied")
        with patch.object(self.module, "gh_available", return_value=True), patch.object(self.module, "existing_open_issues", return_value=set()), patch.object(self.module.subprocess, "run", return_value=failed), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.emit_issues(report, "o/r"), 1)
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="url", stderr="")
        with patch.object(self.module, "gh_available", return_value=True), patch.object(self.module, "existing_open_issues", return_value=set()), patch.object(self.module.subprocess, "run", return_value=ok), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.emit_issues(report, None), 0)

    def test_issue_listing_and_cli_return_codes(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(self.module.gh_available())
        bad = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        with patch.object(self.module.subprocess, "run", return_value=bad):
            self.assertEqual(self.module.existing_open_issues("x"), set())
        malformed = subprocess.CompletedProcess(args=[], returncode=0, stdout="bad", stderr="")
        with patch.object(self.module.subprocess, "run", return_value=malformed):
            self.assertEqual(self.module.existing_open_issues("x"), set())
        valid = subprocess.CompletedProcess(args=[], returncode=0, stdout='[{"title":"one"}]', stderr="")
        with patch.object(self.module.subprocess, "run", return_value=valid):
            self.assertEqual(self.module.existing_open_issues("x"), {"one"})
        clean = {"actionable_count": 0, "platforms": []}
        dirty = {"actionable_count": 1, "platforms": []}
        with patch.object(self.module, "run", return_value=clean), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.main([]), 0)
        with patch.object(self.module, "run", return_value=dirty), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.main([]), 1)
        with patch.object(self.module, "run", return_value=None), patch.object(self.module, "explicit_manual_only_message", return_value="manual"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.main(["--platform-dir", "manual"]), 3)
        with patch.object(self.module, "run", return_value=None), patch.object(self.module, "explicit_manual_only_message", return_value=None), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.main([]), 2)


class DriftAuditBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_script("drift_audit")

    def test_audit_platform_no_drift_manual_and_review_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            platform = Path(td) / "demo"
            platform.mkdir()
            no_drift = {"platform": "demo", "results": [], "proposal": None}
            with patch.object(self.module.platform_drift, "run", return_value=no_drift):
                self.assertEqual(self.module.audit_platform(platform, 1, None)["verdict"], "NO_ACTIONABLE_DRIFT")
            item = {"rule_id": "r1", "state": "unverifiable", "error": "fetch-failed:TimeoutError"}
            manual = {"platform": "demo", "results": [item], "proposal": None}
            with patch.object(self.module.platform_drift, "run", return_value=manual):
                result = self.module.audit_platform(platform, 1, Path(td) / "out")
            self.assertEqual(result["verdict"], "MANUAL_REVIEW")
            self.assertNotIn("fetch-failed", result["rules"][0]["detail"])
            change = {"rule_id": "r1", "state": "updated", "fingerprint": "a" * 64, "reason": "changed"}
            proposal = {"changes": [change]}
            report = {"platform": "demo", "results": [change], "proposal": proposal}
            review = {"verdict": "PROPOSAL_CONSISTENT_WITH_EXTRACTION", "problems": [], "audits": [{"label": "r1", "verdict": "PASS"}], "engine": {"name": "test"}}
            with patch.object(self.module.platform_drift, "run", return_value=report), patch.object(self.module.review_drift_proposal, "review", return_value=review):
                result = self.module.audit_platform(platform, 2, None)
            self.assertEqual(result["verdict"], "PROPOSAL_CONSISTENT_WITH_EXTRACTION")
            self.assertEqual(result["audit_rounds"][0]["verdict"], "PASS")

    def test_render_issue_and_emit_failure_paths(self) -> None:
        summary = {"platform": "demo", "verdict": "MANUAL_REVIEW", "audited_at_utc": "now", "rules": [{"rule_id": "r1", "state": "updated", "fingerprint": "a" * 64}], "problems": ["p"], "audit_rounds": [{"label": "one", "verdict": None, "error": "e"}]}
        with patch.object(self.module.release_recommendation, "recommend", return_value={"recommendation": "HOLD"}):
            self.assertIn("HOLD", self.module.render_issue_body(summary))
        with patch.object(self.module.release_recommendation, "recommend", side_effect=ValueError):
            self.assertIn("unavailable", self.module.render_issue_body(summary))
        with patch.object(self.module, "gh_available", return_value=False), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.emit_issues([summary], None), 0)
        title = "[Drift-audit] demo: MANUAL_REVIEW"
        with patch.object(self.module, "gh_available", return_value=True), patch.object(self.module, "existing_open_issues", return_value={title}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.emit_issues([summary], None), 0)
        failed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="denied")
        with patch.object(self.module, "gh_available", return_value=True), patch.object(self.module, "existing_open_issues", return_value=set()), patch.object(self.module.subprocess, "run", return_value=failed), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.emit_issues([summary], "o/r"), 1)
        ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="url", stderr="")
        with patch.object(self.module, "gh_available", return_value=True), patch.object(self.module, "existing_open_issues", return_value=set()), patch.object(self.module.subprocess, "run", return_value=ok), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.module.emit_issues([summary], None), 0)

    def test_target_validation_and_cli_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            platforms = root / "platforms"
            missing = platforms / "missing"
            bad = platforms / "bad"
            no_map = platforms / "no-map"
            bad.mkdir(parents=True)
            no_map.mkdir()
            (bad / "rule-map.json").write_text("not-json")
            roots, skipped = self.module.audit_targets(platforms, None, None)
            self.assertEqual(roots, [])
            self.assertIn("unreadable-rule-map:bad", skipped)
            roots, skipped = self.module.audit_targets(platforms, missing, None)
            self.assertEqual(skipped, ["missing-platform-dir:missing"])
            roots, skipped = self.module.audit_targets(platforms, no_map, None)
            self.assertEqual(skipped, ["missing-rule-map:no-map"])
            with patch.object(self.module, "audit_targets", return_value=([], ["manual-only:x"])), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.module.main([]), 2)
            out = root / "out"
            target = platforms / "demo"
            target.mkdir()
            with patch.object(self.module, "audit_targets", return_value=([target], ["skip"])), patch.object(self.module, "audit_platform", side_effect=ValueError("bad")), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.module.main(["--out-dir", str(out)]), 0)
            payload = json.loads((out / "audit-summary.json").read_text())
            self.assertEqual(payload["summaries"][0]["verdict"], "MANUAL_REVIEW")
            with patch.object(self.module, "audit_targets", return_value=([target], [])), patch.object(self.module, "audit_platform", return_value={"platform": "demo", "verdict": "PASS", "rules": []}), patch.object(self.module, "emit_issues", return_value=1), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.module.main(["--emit-issues"]), 1)


class ScannerTraversalBoundaryTests(unittest.TestCase):
    def test_single_file_skip_nul_and_skipped_entries(self) -> None:
        module = load_script("scan_sensitive_content")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            skipped = root / ".DS_Store"
            skipped.write_text("ignored")
            self.assertEqual(list(module.iter_scannable_files(skipped)), [])
            keep = root / "keep.bin"
            keep.write_bytes(b"hello\x00world")
            nested = root / "nested"
            nested.mkdir()
            (nested / ".DS_Store").write_text("ignored")
            files = list(module.iter_scannable_files(root))
            self.assertEqual(files, [keep])
            findings, summary = module.scan_files_with_summary(files, root)
            self.assertEqual(findings, [])
            self.assertEqual(summary.binary_like_count, 1)


if __name__ == "__main__":
    unittest.main()
