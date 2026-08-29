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
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "--allow-empty", "-m", "init"], check=True)
            (repo / "platforms").mkdir()
            (repo / "platforms" / "facts.md").write_text("fact", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "data"],
                check=True,
            )
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


if __name__ == "__main__":
    unittest.main()
