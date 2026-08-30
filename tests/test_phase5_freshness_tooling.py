#!/usr/bin/env python3
"""Tier-1 static tests for the 2.0 phase-5 freshness tooling (zero LLM calls)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


drift = load_script("platform_drift")
reviewer = load_script("review_drift_proposal")
recommendation = load_script("release_recommendation")
drift_watch = load_script("drift_watch")
agent_cli = load_script("agent_cli")


RULE_MAP = {
    "format_version": 1,
    "platform": "wechat",
    "allowed_domains": ["example-official.test"],
    "rules": [
        {
            "id": "release-review-operations",
            "step_class": "upload/review/release",
            "ttl_days": 0,
            "official": {
                "url": "https://example-official.test/product/",
                "title": "Operations Spec",
                "section": "review",
            },
            "verify_points": ["提审与发布流程要求"],
        }
    ],
}


def write_platform(root: Path, facts_body: str) -> Path:
    platform_root = root / "platforms" / "wechat"
    platform_root.mkdir(parents=True)
    (platform_root / "rule-map.json").write_text(json.dumps(RULE_MAP), encoding="utf-8")
    (platform_root / "facts.md").write_text(facts_body, encoding="utf-8")
    return platform_root


def with_page_server(handler) -> tempfile.TemporaryDirectory:
    raise NotImplementedError


class DriftNormalizationTests(unittest.TestCase):
    def test_fingerprint_ignores_dynamic_noise_but_tracks_content(self) -> None:
        base = "<html><body><h1>Operations Spec</h1><p>Rule A: submit review before release.</p></body></html>"
        noisy = (
            "<html><head><script>var ts=1234567890;</script><style>.x{}</style></head>"
            "<body><div class='banner'>promo banner</div><h1>Operations Spec</h1>"
            "<p>Rule A:  submit   review\nbefore release.</p>"
            "<div class='nav'>menu</div></body></html>"
        )
        changed = base.replace("submit review before release", "submit review after approval")
        self.assertEqual(drift.normalized_fingerprint(base), drift.normalized_fingerprint(noisy))
        self.assertNotEqual(drift.normalized_fingerprint(base), drift.normalized_fingerprint(changed))

    def test_fact_annotations_parsed_and_unverified_flagged(self) -> None:
        facts_body = (
            "# facts\n\n"
            "- 事实A\n  <!-- fact: rule-a verified=unknown source=https://example-official.test/product/ digest=unknown -->\n"
            "- 事实B\n  <!-- fact: rule-b verified=2026-08-30T00:00:00Z source=https://example-official.test/other/ digest=abc12345 -->\n"
        )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "facts.md"
            path.write_text(facts_body, encoding="utf-8")
            annotations = drift.load_fact_annotations(path)
        self.assertIn("unknown", annotations["rule-a"]["verified"])
        self.assertEqual(annotations["rule-b"]["digest"], "abc12345")


class DriftFetchTests(unittest.TestCase):
    def test_domain_allowlist_enforced_fail_closed(self) -> None:
        html_text, error = drift.fetch("https://evil.example/product/", ["example-official.test"])
        self.assertIsNone(html_text)
        self.assertIn("domain-not-allowlisted", error)

    def test_unverifiable_states_never_mean_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            platform_root = write_platform(Path(temp), "# facts\n")
            rule = RULE_MAP["rules"][0]
            with patch.object(drift, "fetch", return_value=(None, "fetch-failed:URLError")):
                result = drift.check_rule(rule, {}, RULE_MAP["allowed_domains"], force_l2=False)
        self.assertEqual(result["state"], "unverifiable")
        self.assertIn("fetch-failed", result["error"])

    def test_title_missing_is_unverifiable(self) -> None:
        page = "<html><body><h1>Something Else Entirely</h1></body></html>"
        with tempfile.TemporaryDirectory() as temp:
            write_platform(Path(temp), "# facts\n")
            rule = RULE_MAP["rules"][0]
            with patch.object(drift, "fetch", return_value=(page, None)):
                result = drift.check_rule(rule, {}, RULE_MAP["allowed_domains"], force_l2=False)
        self.assertEqual(result["state"], "unverifiable")
        self.assertEqual(result["error"], "expected-title-missing")


class ProposalReviewTests(unittest.TestCase):
    def build_proposal(self, **overrides) -> dict:
        change = {
            "rule_id": "release-review-operations",
            "state": "updated",
            "source": "https://example-official.test/product/",
            "new_digest": "a" * 64,
        }
        change.update(overrides)
        return {"format_version": 1, "platform": "wechat", "changes": [change]}

    def prepare(self, proposal: dict) -> tuple[Path, Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        platform_root = write_platform(root, "# facts\n")
        proposal_path = root / "proposal.json"
        proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
        self.addCleanup(temp.cleanup)
        return proposal_path, platform_root

    def test_scope_and_domain_red_lines_reject_without_llm(self) -> None:
        proposal_path, platform_root = self.prepare(self.build_proposal(source="https://evil.test/x"))
        report = reviewer.review(proposal_path, platform_root, None, rounds=3, shadow=True)
        self.assertEqual(report["verdict"], "DO_NOT_MERGE")
        self.assertTrue(any(item.startswith("gate1:") for item in report["problems"]))

    def test_sensitive_shapes_and_digest_fail_closed(self) -> None:
        proposal_path, platform_root = self.prepare(
            self.build_proposal(new_digest="short", page_text="smuggled official page text")
        )
        report = reviewer.review(proposal_path, platform_root, None, rounds=3, shadow=True)
        self.assertEqual(report["verdict"], "DO_NOT_MERGE")
        self.assertTrue(any("invalid-digest" in item for item in report["problems"]))
        self.assertTrue(any("page-content-in-proposal" in item for item in report["problems"]))

    def test_reproducibility_gate_requires_matching_drift_report(self) -> None:
        proposal_path, platform_root = self.prepare(self.build_proposal())
        report = reviewer.review(proposal_path, platform_root, None, rounds=3, shadow=True)
        self.assertTrue(any(item.startswith("gate2:") for item in report["problems"]))

    def test_audit_engine_failure_is_do_not_merge(self) -> None:
        proposal_path, platform_root = self.prepare(self.build_proposal())
        drift_report = platform_root.parent / "drift.json"
        drift_report.write_text(
            json.dumps(
                {
                    "platform": "wechat",
                    "results": [
                        {
                            "rule_id": "release-review-operations",
                            "state": "updated",
                            "fingerprint": "a" * 64,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        with patch.object(reviewer, "run_agent", return_value=("", "agent-output-empty")):
            report = reviewer.review(proposal_path, platform_root, drift_report, rounds=2, shadow=True)
        self.assertEqual(report["verdict"], "DO_NOT_MERGE")
        self.assertTrue(any("gate5:" in item for item in report["problems"]))

    def test_shadow_mode_exit_code_is_never_merge(self) -> None:
        proposal_path, platform_root = self.prepare(self.build_proposal())
        report = reviewer.review(proposal_path, platform_root, None, rounds=3, shadow=True)
        self.assertTrue(report["shadow"])


class ReleaseRecommendationTests(unittest.TestCase):
    def test_classification_rules(self) -> None:
        self.assertEqual(recommendation.classify_commit(["platforms/wechat/facts.md"]), "data")
        self.assertEqual(recommendation.classify_commit(["skills/x/SKILL.md"]), "behavior")
        self.assertEqual(recommendation.classify_commit(["scripts/validate_suite.py"]), "tooling")
        self.assertEqual(recommendation.classify_commit(["README.md"]), "docs")

    def test_data_only_commits_yield_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            # CI runners have no global git identity; set a repo-local one so commits work anywhere.
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "test"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "init"], check=True)
            (repo / "platforms").mkdir()
            (repo / "platforms" / "facts.md").write_text("fact", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "data"], check=True)
            report = recommendation.recommend(repo, min_data_changes=1)
        self.assertEqual(report["recommendation"], "RECOMMEND_RELEASE")
        self.assertEqual(report["level"], "patch")


class HttpEngineTests(unittest.TestCase):
    def test_http_engine_requires_config(self) -> None:
        with patch.dict(os.environ, {"EVAL_ENGINE": "http"}, clear=False):
            os.environ.pop("AGENT_API_BASE_URL", None)
            os.environ.pop("AGENT_API_KEY", None)
            with self.assertRaises(ValueError):
                agent_cli.resolve_engine()

    def test_http_engine_metadata_reports_unset_model(self) -> None:
        with patch.dict(
            os.environ,
            {"EVAL_ENGINE": "http", "AGENT_API_BASE_URL": "https://api.example.test/v1", "AGENT_API_KEY": "k"},
        ):
            os.environ.pop("AGENT_API_MODEL", None)
            meta = agent_cli.engine_metadata()
        self.assertEqual(meta["engine"], "http")


class DriftWatchTests(unittest.TestCase):
    def test_manual_only_platforms_are_skipped(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            auto = root / "platforms" / "wechat"
            manual = root / "platforms" / "alipay"
            auto.mkdir(parents=True)
            manual.mkdir(parents=True)
            (auto / "rule-map.json").write_text(
                json.dumps({"format_version": 1, "platform": "wechat", "allowed_domains": ["a.test"], "rules": []}),
                encoding="utf-8",
            )
            (manual / "rule-map.json").write_text(
                json.dumps(
                    {
                        "format_version": 1,
                        "platform": "alipay",
                        "allowed_domains": ["b.test"],
                        "detection": "manual-only",
                        "rules": [],
                    }
                ),
                encoding="utf-8",
            )
            dirs = drift_watch.platform_dirs(root, None)
        self.assertEqual([p.name for p in dirs], ["wechat"])

    def test_bundled_platform_layers_present_and_valid(self) -> None:
        for platform, detection in (("wechat", None), ("alipay", "manual-only"), ("douyin", "manual-only")):
            rule_map = json.loads(
                (ROOT / "platforms" / platform / "rule-map.json").read_text(encoding="utf-8")
            )
            self.assertEqual(rule_map["platform"], platform)
            self.assertEqual(rule_map.get("detection"), detection)
            self.assertTrue((ROOT / "platforms" / platform / "facts.md").is_file())
            for rule in rule_map["rules"]:
                self.assertTrue(rule["official"]["url"].startswith("https://"))
                domain = rule["official"]["url"].split("/")[2]
                self.assertIn(domain, rule_map["allowed_domains"])


class DriftAuditUnitTests(unittest.TestCase):
    """Zero-LLM lockups for the audit orchestration semantics (2.1.1)."""

    def test_audit_actionable_includes_full_l2_vocabulary(self) -> None:
        from drift_watch import AUDIT_ACTIONABLE, DETECTION_ACTIONABLE, actionable

        results = [
            {"rule_id": "a", "state": "unchanged"},
            {"rule_id": "b", "state": "fingerprint-changed"},
            {"rule_id": "c", "state": "unverifiable"},
            {"rule_id": "d", "state": "updated"},
            {"rule_id": "e", "state": "conflicting"},
        ]
        detection_ids = [item["rule_id"] for item in actionable(results)]
        audit_ids = [item["rule_id"] for item in actionable(results, AUDIT_ACTIONABLE)]
        self.assertEqual(detection_ids, ["b", "c"])
        self.assertEqual(audit_ids, ["b", "c", "d", "e"])
        self.assertEqual(DETECTION_ACTIONABLE, {"fingerprint-changed", "unverifiable"})

    def test_audit_targets_skip_manual_only_and_honor_detection_report(self) -> None:
        drift_audit = load_script("drift_audit")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            platforms = root / "platforms"
            for name, detection in (("wechat", None), ("alipay", "manual-only"), ("douyin", "manual-only")):
                platform_dir = platforms / name
                platform_dir.mkdir(parents=True)
                rule_map: dict[str, object] = {
                    "format_version": 1,
                    "platform": name,
                    "allowed_domains": ["x.test"],
                    "rules": [],
                }
                if detection:
                    rule_map["detection"] = detection
                (platform_dir / "rule-map.json").write_text(json.dumps(rule_map), encoding="utf-8")

            # Without a detection report: every non-manual platform is a target.
            roots, skipped = drift_audit.audit_targets(platforms, None, None)
            self.assertEqual([p.name for p in roots], ["wechat"])
            self.assertEqual(sorted(skipped), ["manual-only:alipay", "manual-only:douyin"])

            # With a detection report: only the platforms it scanned are audited.
            report = root / "drift-report.json"
            report.write_text(json.dumps({"platforms": [{"platform": "wechat"}]}), encoding="utf-8")
            roots, skipped = drift_audit.audit_targets(platforms, None, report)
            self.assertEqual([p.name for p in roots], ["wechat"])
            self.assertEqual(skipped, [])

            # Even an explicit manual-only --platform-dir is refused (double guard
            # against guaranteed-failing L2 on client-rendered shells).
            roots, skipped = drift_audit.audit_targets(platforms, platforms / "alipay", None)
            self.assertEqual(roots, [])
            self.assertEqual(skipped, ["manual-only:alipay"])

    def test_audit_targets_report_with_only_manual_platforms_yields_no_targets(self) -> None:
        drift_audit = load_script("drift_audit")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            platforms = root / "platforms"
            platforms.mkdir(parents=True)
            (platforms / "alipay").mkdir()
            (platforms / "alipay" / "rule-map.json").write_text(
                json.dumps(
                    {
                        "format_version": 1,
                        "platform": "alipay",
                        "allowed_domains": ["x.test"],
                        "detection": "manual-only",
                        "rules": [],
                    }
                ),
                encoding="utf-8",
            )
            report = root / "drift-report.json"
            report.write_text(json.dumps({"platforms": [{"platform": "alipay"}]}), encoding="utf-8")
            roots, skipped = drift_audit.audit_targets(platforms, None, report)
            self.assertEqual(roots, [])
            self.assertEqual(skipped, ["manual-only:alipay"])

    def test_shared_url_facts_with_mixed_digests_fail_closed(self) -> None:
        rule = {"id": "r1", "official": {"url": "https://x.test/a", "title": "T"}}
        annotations = {
            "f1": {"verified": "2026-01-01", "source": "https://x.test/a", "digest": "a" * 64},
            "f2": {"verified": "2026-01-01", "source": "https://x.test/a", "digest": "b" * 64},
        }
        outcome = drift.check_rule(rule, annotations, ["x.test"], force_l2=False)
        self.assertEqual(outcome["state"], "unverifiable")
        self.assertEqual(outcome["error"], "inconsistent-baseline-digests")

    def test_agent_errors_never_carry_raw_model_output(self) -> None:
        # When the engine replies with non-JSON prose containing a secret-looking
        # payload, the returned error must carry a length marker only, never the text.
        with patch.object(agent_cli, "resolve_engine", return_value="claude"):
            with patch.object(
                agent_cli,
                "build_command",
                return_value=["true"],
            ):
                with patch.object(
                    agent_cli.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess(
                        args=[], returncode=0, stdout="here is a raw secret-looking reply", stderr=""
                    ),
                ):
                    agent_cli.os.environ.pop("EVAL_ENGINE", None)
                    _, error = agent_cli.run_agent(Path("/tmp"), "PROMPT", attempts=1)
        self.assertIsNotNone(error)
        self.assertIn("agent-output-not-json:len=", error)
        self.assertNotIn("raw secret-looking", error)


class AuditFixRegressionTests(unittest.TestCase):
    """Regressions for the codex-audit fix batch (release gates, uni matching, extractor stack)."""

    def test_uni_detection_uses_word_boundary(self) -> None:
        import json as _json
        doctor = load_script("capability_doctor")
        with tempfile.TemporaryDirectory() as td:
            for i, (value, expect) in enumerate(
                [("npm run unit", "unknown"), ("echo community-modules", "unknown"), ("uni build -p mp-weixin", "uni-app")]
            ):
                root = Path(td) / f"u{i}"
                root.mkdir()
                (root / "package.json").write_text(_json.dumps({"scripts": {"w": value}}), encoding="utf-8")
                self.assertEqual(doctor.inspect_project(root)["framework"], expect, value)

    def test_extractor_stack_does_not_swallow_content_after_noisy_span(self) -> None:
        a = '<html><body><span class="nav">m</span><p>RULE ONE</p><p>MORE</p></body></html>'
        b = '<html><body><span class="nav">m</span><p>RULE ONE</p><p>DIFF</p></body></html>'
        self.assertNotEqual(drift.normalized_fingerprint(a), drift.normalized_fingerprint(b))

    def test_extractor_still_strips_noise_and_scripts(self) -> None:
        c = '<html><body><span class="nav">NAV1</span><p>BODY</p></body></html>'
        d = '<html><body><span class="menu">NAV2</span><p>BODY</p></body></html>'
        self.assertEqual(drift.normalized_fingerprint(c), drift.normalized_fingerprint(d))
        e = '<html><head><script>var a=1</script></head><body><p>X</p></body></html>'
        f = '<html><head><script>var b=2</script></head><body><p>X</p></body></html>'
        self.assertEqual(drift.normalized_fingerprint(e), drift.normalized_fingerprint(f))

    def test_drift_watch_mode_is_always_honest(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            report = drift_watch.run(Path(ROOT), None, no_llm=False)
        self.assertEqual(report["mode"], "deterministic")
        self.assertIn("drift_audit", report["llm_stage"])

    def test_source_cover_is_repo_only_not_package_content(self) -> None:
        vs = load_script("validate_suite")
        self.assertIn("assets/readme-cover-2000x849-v2.webp", vs.REPO_ONLY_ASSETS)
        self.assertNotIn("assets/readme-cover-2000x849-v2.webp", vs.REQUIRED_FILES)


if __name__ == "__main__":
    unittest.main()
