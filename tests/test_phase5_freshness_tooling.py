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
            "id": "operations-spec-scope",
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


FACTS_WITH_TEXT = (
    "# facts\n\n"
    "- 事实：运营规范当前覆盖提审与发布要求，以平台当前版本为准。\n"
    "  <!-- fact: operations-spec-scope verified=2026-08-31 "
    "source=https://example-official.test/product/ digest=%s -->\n" % ("a" * 64)
)


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
        return build_default_proposal(**overrides)


def build_default_proposal(**overrides) -> dict:
    change = {
        "rule_id": "operations-spec-scope",
        "state": "updated",
        "official_url": "https://example-official.test/product/",
        "fingerprint": "a" * 64,
        "requested_verify_points": ["提审与发布流程要求"],
        "extracted_statements": {"提审与发布流程要求": "提审前须完成安全检测。"},
        "proposed_fact_updates": {
            "operations-spec-scope": {
                "fact_id": "operations-spec-scope",
                "current_text": "运营规范当前覆盖提审与发布要求，以平台当前版本为准。",
                "proposed_text": "提审与发布流程要求: 提审前须完成安全检测。",
                "source_digest": "a" * 64,
            }
        },
    }
    change.update(overrides)
    return {"format_version": 2, "platform": "wechat", "changes": [change]}

    def prepare(self, proposal: dict) -> tuple[Path, Path]:
        return prepare_proposal_fixture(proposal)


def prepare_proposal_fixture(proposal: dict) -> tuple[Path, Path]:
    """Module-level fixture builder: usable from any test class without
    instantiating a TestCase (whose addCleanup would never run — codex P3)."""
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    platform_root = write_platform(root, FACTS_WITH_TEXT)
    proposal_path = root / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    # register cleanup against any running TestCase; fall back to atexit-safe
    # explicit cleanup by returning the temp dir handle on the paths' parent.
    _ACTIVE_TEMP_DIRS.append(temp)
    return proposal_path, platform_root


_ACTIVE_TEMP_DIRS: list[tempfile.TemporaryDirectory] = []


def drain_active_temp_dirs() -> None:
    """Cleanup hook: called from tearDown of every fixture-using test class."""
    while _ACTIVE_TEMP_DIRS:
        _ACTIVE_TEMP_DIRS.pop().cleanup()


class ProposalReviewGateTests(unittest.TestCase):
    """Gate-level tests that keep using the class fixture helpers."""

    def build_proposal(self, **overrides) -> dict:
        return build_default_proposal(**overrides)

    def prepare(self, proposal: dict) -> tuple[Path, Path]:
        return prepare_proposal_fixture(proposal)

    def tearDown(self) -> None:
        drain_active_temp_dirs()

    def test_scope_and_domain_red_lines_reject_without_llm(self) -> None:
        proposal_path, platform_root = self.prepare(self.build_proposal(official_url="https://evil.test/x"))
        report = reviewer.review(proposal_path, platform_root, None, rounds=3, shadow=True)
        self.assertEqual(report["verdict"], "DO_NOT_APPLY")
        self.assertTrue(any(item.startswith("gate1:") for item in report["problems"]))

    def test_sensitive_shapes_and_digest_fail_closed(self) -> None:
        proposal_path, platform_root = self.prepare(
            self.build_proposal(fingerprint="short", page_text="smuggled official page text")
        )
        report = reviewer.review(proposal_path, platform_root, None, rounds=3, shadow=True)
        self.assertEqual(report["verdict"], "DO_NOT_APPLY")
        self.assertTrue(any("invalid-digest" in item for item in report["problems"]))
        self.assertTrue(any("page-content-in-proposal" in item for item in report["problems"]))

    def test_reproducibility_gate_requires_matching_drift_report(self) -> None:
        proposal_path, platform_root = self.prepare(self.build_proposal())
        report = reviewer.review(proposal_path, platform_root, None, rounds=3, shadow=True)
        self.assertTrue(any(item.startswith("gate2:") for item in report["problems"]))

    def test_audit_engine_failure_is_do_not_apply(self) -> None:
        proposal_path, platform_root = self.prepare(self.build_proposal())
        drift_report = platform_root.parent / "drift.json"
        drift_report.write_text(
            json.dumps(
                {
                    "platform": "wechat",
                    "results": [
                        {
                            "rule_id": "operations-spec-scope",
                            "state": "updated",
                            "fingerprint": "a" * 64,
                            "extracted_statements": {"提审与发布流程要求": "提审前须完成安全检测。"},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        with patch.object(reviewer, "run_agent", return_value=("", "agent-output-empty")):
            report = reviewer.review(proposal_path, platform_root, drift_report, rounds=2, shadow=True)
        self.assertEqual(report["verdict"], "DO_NOT_APPLY")
        self.assertTrue(any("gate5:" in item for item in report["problems"]))

    def test_shadow_mode_exit_code_is_never_merge(self) -> None:
        proposal_path, platform_root = self.prepare(self.build_proposal())
        report = reviewer.review(proposal_path, platform_root, None, rounds=3, shadow=True)
        self.assertTrue(report["shadow"])

    def test_rounds_below_one_is_rejected(self) -> None:
        # rounds=0 must never shortcut deterministic gates into a pass verdict.
        proposal_path, platform_root = self.prepare(self.build_proposal())
        report = reviewer.review(proposal_path, platform_root, None, rounds=0, shadow=True)
        self.assertEqual(report["verdict"], "DO_NOT_APPLY")
        self.assertIn("rounds-below-minimum:1", report["problems"])

    def test_missing_statements_fail_closed_before_audit(self) -> None:
        # A proposal without extracted statements has no auditable evidence;
        # gate 3 must reject it before any agent call is attempted.
        proposal_path, platform_root = self.prepare(
            self.build_proposal(extracted_statements={})
        )
        with patch.object(reviewer, "run_agent") as agent:
            report = reviewer.review(proposal_path, platform_root, None, rounds=1, shadow=True)
        agent.assert_not_called()
        self.assertEqual(report["verdict"], "DO_NOT_APPLY")
        self.assertTrue(any("missing-extracted-statements" in item for item in report["problems"]))


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
            # manual-only platforms absent in this fixture: no verification trigger
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

    def test_nested_div_inside_noisy_div_does_not_leak(self) -> None:
        # Same-tag nesting: the inner plain </div> must not close the outer
        # noisy div's skip state and leak menu text into the fingerprint.
        leak = '<html><body><div class="nav"><div>menu-inner</div></div><p>BODY</p></body></html>'
        clean = '<html><body><div class="nav"><div>other</div></div><p>BODY</p></body></html>'
        self.assertEqual(drift.normalized_fingerprint(leak), drift.normalized_fingerprint(clean))

    def test_extractor_survives_deep_and_mismatched_nesting(self) -> None:
        ok = '<html><body><div class="footer"><div><div><span>x</span></div></div></div><p>BODY</p></body></html>'
        self.assertNotEqual(drift.normalized_fingerprint(ok), "")
        stray = '<html><body><div class="header"></div></p><p>BODY</p></body></html>'
        self.assertNotEqual(drift.normalized_fingerprint(stray), "")

    def test_redirect_off_allowlist_blocked(self) -> None:
        # Real 302 to an off-allowlist host: the redirect handler must refuse
        # the hop and fetch must return a fail-closed error, never content.
        import http.server
        import threading

        class RedirectOnce(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                self.send_response(302)
                self.send_header("Location", "https://evil.test/leaked")
                self.end_headers()

            def log_message(self, *args) -> None:  # noqa: ANN002, ANN003, ARG002
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), RedirectOnce)
        host_port = f"127.0.0.1:{server.server_address[1]}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        html_text, error = drift.fetch(f"http://{host_port}/x", [host_port])
        self.assertIsNone(html_text)
        self.assertIn("redirect-off-allowlist", error)

    def test_drift_watch_mode_is_always_honest(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            report = drift_watch.run(Path(ROOT), None, no_llm=False)
        self.assertEqual(report["mode"], "deterministic")
        self.assertIn("drift_audit", report["llm_stage"])

    def test_source_cover_is_repo_only_not_package_content(self) -> None:
        vs = load_script("validate_suite")
        self.assertIn("assets/readme-cover-2000x849-v2.webp", vs.REPO_ONLY_ASSETS)
        self.assertNotIn("assets/readme-cover-2000x849-v2.webp", vs.REQUIRED_FILES)


class V317AuditFollowUpTests(unittest.TestCase):
    """Regressions for the codex sixth-audit batch (3.1.7)."""

    def tearDown(self) -> None:
        drain_active_temp_dirs()

    def _run(self, proposal) -> dict:
        proposal_path, platform_root = prepare_proposal_fixture(proposal)
        drift = platform_root.parent / "drift.json"
        drift.write_text(json.dumps({"platform": "wechat", "results": [{
            "rule_id": "operations-spec-scope", "state": "updated", "fingerprint": "a" * 64,
            "extracted_statements": {"提审与发布流程要求": "提审前须完成安全检测。"}}]}))
        with patch.object(reviewer, "run_agent", return_value=('{"consistent":"consistent","reason":"ok"}', None)):
            return reviewer.review_guarded(proposal_path, platform_root, drift, rounds=1)

    def test_cross_rule_url_rejected(self) -> None:
        # codex probe: rule A's statements + rule B's URL must fail.
        p = build_default_proposal()
        p["changes"][0]["official_url"] = "https://example-official.test/other/"
        r = self._run(p)
        self.assertEqual(r["verdict"], "DO_NOT_APPLY")
        self.assertTrue(any("official-url-not-bound-to-rule" in x for x in r["problems"]))

    def test_unknown_rule_rejected(self) -> None:
        p = build_default_proposal()
        p["changes"][0]["rule_id"] = "no-such-rule"
        r = self._run(p)
        self.assertTrue(any("unknown-rule" in x for x in r["problems"]))

    def test_malformed_updates_fail_closed_no_crash(self) -> None:
        # list updates used to raise TypeError (unhashable dict).
        p = build_default_proposal()
        p["changes"][0]["proposed_fact_updates"] = [{"fact_id": "x"}]
        r = self._run(p)  # must not raise
        self.assertEqual(r["verdict"], "DO_NOT_APPLY")

    def test_duplicated_verify_points_rejected(self) -> None:
        # duplicates used to pass after set() dedup.
        p = build_default_proposal()
        p["changes"][0]["requested_verify_points"] = ["提审与发布流程要求", "提审与发布流程要求"]
        r = self._run(p)
        self.assertTrue(any("requested-verify-points-duplicated" in x for x in r["problems"]))

    def test_null_and_numeric_inputs_fail_closed(self) -> None:
        for mutate in (
            lambda c: c["changes"][0].update(requested_verify_points=None),
            lambda c: c["changes"][0].update(extracted_statements={"p": 123}),
        ):
            p = build_default_proposal()
            mutate(p)
            r = self._run(p)
            self.assertEqual(r["verdict"], "DO_NOT_APPLY")

    def test_legitimate_proposal_passes(self) -> None:
        r = self._run(build_default_proposal())
        self.assertEqual(r["verdict"], "PROPOSAL_CONSISTENT_WITH_EXTRACTION")
        self.assertEqual(r["problems"], [])


class V316AuditFollowUpTests(unittest.TestCase):
    """Regressions for the codex fifth-audit batch (3.1.6)."""

    def tearDown(self) -> None:
        drain_active_temp_dirs()

    def test_tampered_proposal_rejected_by_gate2(self) -> None:
        # codex probe: FAKE_POINT substitution + invented fact id must NOT pass.
        proposal = build_default_proposal()
        proposal["changes"][0]["extracted_statements"] = {"FAKE_POINT": "任意"}
        proposal["changes"][0]["requested_verify_points"] = ["FAKE_POINT"]
        proposal["changes"][0]["proposed_fact_updates"]["unknown-fact"] = {
            "fact_id": "unknown-fact", "current_text": "捏造", "proposed_text": "x", "source_digest": "a" * 64
        }
        proposal_path, platform_root = prepare_proposal_fixture(proposal)
        drift_report = platform_root.parent / "drift.json"
        drift_report.write_text(json.dumps({
            "platform": "wechat",
            "results": [{
                "rule_id": "operations-spec-scope", "state": "updated", "fingerprint": "a" * 64,
                "extracted_statements": {"提审与发布流程要求": "提审前须完成安全检测。"},
            }],
        }))
        with patch.object(reviewer, "run_agent", return_value=('{"consistent":"consistent","reason":"ok"}', None)):
            report = reviewer.review(proposal_path, platform_root, drift_report, rounds=1, shadow=True)
        self.assertEqual(report["verdict"], "DO_NOT_APPLY")
        self.assertTrue(any("verify-points-not-bound-to-rule-map" in p_ for p_ in report["problems"]))
        self.assertTrue(any("fact-id-set-diverges-from-facts" in p_ for p_ in report["problems"]))
        self.assertTrue(any("extracted-statements-diverge-from-report" in p_ for p_ in report["problems"]))

    def test_legitimate_proposal_still_passes_gate2(self) -> None:
        proposal_path, platform_root = prepare_proposal_fixture(build_default_proposal())
        drift_report = platform_root.parent / "drift.json"
        drift_report.write_text(json.dumps({
            "platform": "wechat",
            "results": [{
                "rule_id": "operations-spec-scope", "state": "updated", "fingerprint": "a" * 64,
                "extracted_statements": {"提审与发布流程要求": "提审前须完成安全检测。"},
            }],
        }))
        with patch.object(reviewer, "run_agent", return_value=('{"consistent":"consistent","reason":"ok"}', None)):
            report = reviewer.review(proposal_path, platform_root, drift_report, rounds=1, shadow=True)
        self.assertEqual(report["verdict"], "PROPOSAL_CONSISTENT_WITH_EXTRACTION")
        self.assertEqual(report["problems"], [])

    def test_mixed_commit_keeps_data_class(self) -> None:
        # codex probe: scripts+facts must classify as BOTH, not just tooling.
        classes = recommendation.classify_commit_classes(["scripts/x.py", "platforms/alipay/facts.md"])
        self.assertIn("data", classes)
        self.assertIn("tooling", classes)

    def test_this_cycle_changelog_evidence_satisfies_major(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for plat in ("alipay", "douyin"):
                facts = root / "platforms" / plat / "facts.md"
                facts.parent.mkdir(parents=True)
                facts.write_text("- 事实A\n  <!-- fact: a verified=2026-08-31 source=https://x/ digest=unknown -->\n")
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## 3.1.6 - 2026-08-31\n\n- alipay/douyin facts 人工核验于 2026-08-31 (tag: v3.1.6)\n\n## 3.1.5 - 2026-08-30\n"
            )
            status = recommendation.manual_verification_status(root, "major", {}, since_tag="v3.1.5")
            self.assertFalse(status["required"])
            # and without this-cycle evidence it must be required
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## 3.1.6 - 2026-08-31\n\n- 修复。\n\n## 3.1.5 - 2026-08-30\n- alipay/douyin facts 人工核验于 2026-08-30\n"
            )
            status2 = recommendation.manual_verification_status(root, "major", {}, since_tag="v3.1.5")
            self.assertTrue(status2["required"])

    def test_extractor_unbalanced_span_inside_noise_keeps_body(self) -> None:
        # codex probe: unclosed <span> in noise must not swallow the page body.
        a = '<html><body><div class="nav"><span>menu</div><p>BODY-A</p></body></html>'
        b = '<html><body><div class="nav"><span>menu</div><p>BODY-B</p></body></html>'
        fa, fb = drift.normalized_fingerprint(a), drift.normalized_fingerprint(b)
        self.assertNotEqual(fa, fb)
        self.assertNotEqual(fa, "")


class V315AuditFollowUpTests(unittest.TestCase):
    """Regressions for the codex follow-up audit batch (3.1.5).

    Every fix is locked by the negative probe that originally proved the
    defect — the pattern the previous batch missed.
    """

    def test_l2_rejects_unrequested_points(self) -> None:
        payload = {
            "verify_points": [
                {"point": "UNREQUESTED-A", "current_statement": "x"},
                {"point": "UNREQUESTED-B", "current_statement": "y"},
            ]
        }
        self.assertFalse(drift._extract_payload_valid(payload, ["真实A", "真实B"]))

    def test_l2_rejects_missing_extra_and_duplicate_points(self) -> None:
        ok = {"verify_points": [{"point": "A", "current_statement": "s"}, {"point": "B", "current_statement": "NOT_STATED"}]}
        self.assertTrue(drift._extract_payload_valid(ok, ["A", "B"]))
        missing = {"verify_points": [{"point": "A", "current_statement": "s"}]}
        self.assertFalse(drift._extract_payload_valid(missing, ["A", "B"]))
        extra = {"verify_points": ok["verify_points"] + [{"point": "C", "current_statement": "s"}]}
        self.assertFalse(drift._extract_payload_valid(extra, ["A", "B"]))
        dup = {"verify_points": [{"point": "A", "current_statement": "s"}, {"point": "A", "current_statement": "t"}]}
        self.assertFalse(drift._extract_payload_valid(dup, ["A", "B"]))

    def test_stray_end_tag_in_noise_region_does_not_end_skip(self) -> None:
        # codex probe: <div class="nav"></p>SECRET</div> — the stray </p> must
        # not pop the real noisy div; SECRET stays excluded from the fingerprint.
        a = '<html><body><div class="nav"></p>SECRET</div><p>BODY</p></body></html>'
        b = '<html><body><div class="nav"></p>OTHER</div><p>BODY</p></body></html>'
        self.assertEqual(drift.normalized_fingerprint(a), drift.normalized_fingerprint(b))

    def test_extractor_survives_void_and_mismatched_tags(self) -> None:
        ok = '<html><body><div class="footer"><br><img src="x"><div><span>y</span></div></div><p>BODY</p></body></html>'
        self.assertNotEqual(drift.normalized_fingerprint(ok), "")

    def test_audit_schema_actually_enforced(self) -> None:
        self.assertFalse(reviewer._audit_payload_valid({"consistent": "consistent"}))
        self.assertFalse(reviewer._audit_payload_valid({"consistent": "consistent", "reason": "  "}))
        self.assertFalse(reviewer._audit_payload_valid({"consistent": "bogus", "reason": "r"}))
        self.assertFalse(reviewer._audit_payload_valid({"consistent": "consistent", "reason": "r", "extra": 1}))
        self.assertTrue(reviewer._audit_payload_valid({"consistent": "consistent", "reason": "updates stay within extraction"}))

    def test_gate3_requires_proposed_fact_updates(self) -> None:
        bad = {"changes": [{
            "rule_id": "r", "state": "updated",
            "official_url": "https://example-official.test/product/",
            "fingerprint": "a" * 64,
            "extracted_statements": {"p": "s"},
        }]}
        out = reviewer.check_change_safety(bad)
        self.assertTrue(any("missing-proposed-fact-updates" in item for item in out))

    def test_manual_verification_gate(self) -> None:
        rr = load_script("release_recommendation")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for plat in ("alipay", "douyin"):
                facts = root / "platforms" / plat / "facts.md"
                facts.parent.mkdir(parents=True)
                facts.write_text(
                    "- 事实A\n  <!-- fact: a verified=unknown source=https://x/ digest=unknown -->\n"
                )
            status = rr.manual_verification_status(root, "minor", {"data": 1})
            self.assertTrue(status["required"])
            status_patch = rr.manual_verification_status(root, "patch", {"tooling": 2})
            self.assertFalse(status_patch["required"])

    def test_i18n_presence_enforced(self) -> None:
        i18n = load_script("check_i18n_readme_structure")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "VERSION").write_text("3.1.5\n", encoding="utf-8")
            for name in i18n.README_HEADINGS:
                (root / name).write_text("# Head\n\n## Section\n", encoding="utf-8")
            errors: list[str] = []
            i18n.check_fact_alignment(root, errors)
            self.assertTrue(any("version badge missing entirely" in e for e in errors))
            self.assertTrue(any("tarball version reference missing entirely" in e for e in errors))

    def test_cross_file_anchor_validation(self) -> None:
        vs = load_script("validate_suite")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "target.md").write_text("# A\n\n## Real\n", encoding="utf-8")
            (root / "src.md").write_text("# B\n\n[bad](target.md#missing)\n[good](target.md#real)\n", encoding="utf-8")
            errors = vs.validate_links(root)
            self.assertTrue(any("broken cross-file anchor" in e for e in errors))
            self.assertEqual(len([e for e in errors if "cross-file" in e]), 1)


if __name__ == "__main__":
    unittest.main()
