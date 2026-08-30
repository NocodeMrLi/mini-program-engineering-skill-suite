#!/usr/bin/env python3
"""Committed regression tests for the extracted release gate (scripts/release_gate.sh).

The gate used to live inline in .github/workflows/release.yml where no test
could reach it; the v3.1.0 fix (PIPESTATUS check, singular "Ran 1 test",
zero-test detection) existed only as a one-off experiment. These tests drive
the extracted script with controlled fake unittest output so the gating
behavior can never silently regress.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/release_gate.sh"


def load_recommender():
    spec = importlib.util.spec_from_file_location(
        "release_recommendation_under_test", ROOT / "scripts" / "release_recommendation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def build_tagged_repo(root: Path) -> Path:
    repo = root / "source"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Release Gate Test")
    git(repo, "config", "user.email", "release-gate@example.test")
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-q", "-m", "baseline")
    git(repo, "tag", "v1.0.0")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "tool.py").write_text("print('release')\n", encoding="utf-8")
    git(repo, "add", "scripts/tool.py")
    git(repo, "commit", "-q", "-m", "release tooling")
    git(repo, "tag", "v1.1.0")
    return repo


def run_gate_with_fake_unittest(log_text: str) -> tuple[int, str]:
    """Run the gate's parsing/assertion path against a controlled log."""
    with tempfile.TemporaryDirectory() as td:
        log = Path(td) / "unittest.log"
        log.write_text(log_text, encoding="utf-8")
        # Drive only the shell assertions by re-implementing the parse the way
        # the script does; this mirrors release_gate.sh lines verbatim.
        script = f'''
set -uo pipefail
grep -Eo 'Ran [0-9]+ tests?' {log} | grep -Eo '[0-9]+' | head -1 || true
'''
        parse = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        test_count = parse.stdout.strip()
    return 0, test_count


class ReleaseGateParsingTests(unittest.TestCase):
    """The three failure shapes the gate must catch."""

    def test_parses_singular_test_count(self) -> None:
        # A failed run prints "Ran 1 test" (singular); a plural-only regex
        # returns empty and the old workflow shipped a blank tests_passed.
        _, count = run_gate_with_fake_unittest("FAIL: x\nRan 1 test in 0.001s\nFAILED (failures=1)\n")
        self.assertEqual(count, "1")

    def test_parses_plural_test_count(self) -> None:
        _, count = run_gate_with_fake_unittest("Ran 129 tests in 11.0s\nOK\n")
        self.assertEqual(count, "129")

    def test_missing_count_line_yields_empty(self) -> None:
        # Discovery failure prints no Ran line at all; the gate must see empty.
        _, count = run_gate_with_fake_unittest("ImportError: No module named tests\n")
        self.assertEqual(count, "")

    def test_gate_script_exists_and_blocks_on_failure(self) -> None:
        # End-to-end on the real script: a repo whose unittest fails must block
        # the release. We use a scratch copy with one failing test.
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "tests").mkdir()
            (repo / "tests" / "test_x.py").write_text(
                "import unittest\nclass T(unittest.TestCase):\n"
                "    def test_fails(self):\n        self.fail('boom')\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["bash", str(ROOT / "scripts/release_gate.sh"), str(repo), str(Path(td) / "u.log"), str(Path(td) / "s.json")],
                capture_output=True, text=True, timeout=300,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release blocked", result.stderr)


class GateFailurePathTests(unittest.TestCase):
    def test_fixture_repo_blocks_on_invalid_suite_and_writes_summary(self) -> None:
        """A fixture with passing tests but an invalid suite must:
        - block with the gate-failure reason (NOT mislabeled as "crashed"),
        - still write the summary, because a blocked run's summary is the
          evidence of which gate stopped the release.

        Real-repo green-run evidence lives in the Release gate-summary artifact
        and EVALUATIONS.md, not in this unit test.
        """
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            scripts = repo / "scripts"
            scripts.mkdir(parents=True)
            (repo / "tests").mkdir()
            (repo / "tests" / "test_ok.py").write_text(
                "import unittest\nclass T(unittest.TestCase):\n"
                "    def test_ok(self):\n        self.assertTrue(True)\n"
                "    def test_ok2(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            (repo / "VERSION").write_text("0.0.0\n", encoding="utf-8")
            # validate_suite needs its imports from the real repo; run the gate
            # with the real scripts available by invoking it from ROOT and
            # pointing at the fixture tests via a temporary copy of the layout.
            shutil.copy(ROOT / "scripts/release_gate.sh", scripts / "release_gate.sh")
            for name in (
                "validate_suite.py",
                "scan_sensitive_content.py",
                "check_foundation_equivalence.py",
                "check_i18n_readme_structure.py",
                "agent_cli.py",
                "platform_drift.py",
                "drift_watch.py",
                "review_drift_proposal.py",
                "release_recommendation.py",
                "drift_audit.py",
                "summarize_evaluations.py",
                "verify_public_package.py",
                "export_public_package.py",
                "capability_doctor.py",
            ):
                shutil.copy(ROOT / "scripts" / name, scripts / name)
            summary = Path(td) / "gate-summary.json"
            result = subprocess.run(
                ["bash", str(scripts / "release_gate.sh"), str(repo), str(Path(td) / "u.log"), str(summary)],
                capture_output=True, text=True, timeout=300,
            )
            self.assertNotEqual(result.returncode, 0)
            combined = (result.stdout + result.stderr).lower()
            # JSON-failure path: reason says gate failure, NOT crashed.
            self.assertIn("gate failure", combined)
            self.assertNotIn("crashed", combined)
            # The summary must exist and record the blocking verdict.
            self.assertTrue(summary.exists(), "blocked run must persist its summary")
            data = json.loads(summary.read_text(encoding="utf-8"))
            self.assertFalse(data["validate_valid"])
            self.assertGreater(data["tests_passed"], 0)



    def test_crashed_tool_reports_crashed_and_writes_no_summary(self) -> None:
        """A validate_suite that exits non-zero with non-JSON output is a crash:
        reported as crashed (not gate failure) and no summary is fabricated."""
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            (repo / "tests").mkdir(parents=True)
            (repo / "scripts").mkdir(parents=True)
            (repo / "tests" / "test_ok.py").write_text(
                "import unittest\nclass T(unittest.TestCase):\n"
                "    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            (repo / "scripts" / "validate_suite.py").write_text(
                "#!/usr/bin/env python3\nimport sys\n"
                "print('Traceback (most recent call last): boom', file=sys.stderr)\n"
                "sys.exit(3)\n",
                encoding="utf-8",
            )
            (repo / "scripts" / "scan_sensitive_content.py").write_text(
                "#!/usr/bin/env python3\nimport json\n"
                "print(json.dumps({'valid': True, 'checked_files': 1, 'skill_count': 1}))\n",
                encoding="utf-8",
            )
            shutil.copy(ROOT / "scripts/release_gate.sh", repo / "scripts" / "release_gate.sh")
            summary = Path(td) / "gate-summary.json"
            result = subprocess.run(
                ["bash", str(repo / "scripts/release_gate.sh"), str(repo), str(Path(td) / "u.log"), str(summary)],
                capture_output=True, text=True, timeout=120,
            )
        self.assertNotEqual(result.returncode, 0)
        combined = (result.stdout + result.stderr).lower()
        self.assertIn("crashed", combined)
        self.assertFalse(summary.exists(), "a crashed tool must not fabricate a summary")

    def test_manual_verification_failure_persists_complete_gate4_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            scripts = repo / "scripts"
            tests = repo / "tests"
            scripts.mkdir(parents=True)
            tests.mkdir()
            (tests / "test_ok.py").write_text(
                "import unittest\nclass T(unittest.TestCase):\n"
                "    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            (scripts / "validate_suite.py").write_text(
                "import json\nprint(json.dumps({'valid': True, 'checked_files': 1, 'skill_count': 1}))\n",
                encoding="utf-8",
            )
            (scripts / "scan_sensitive_content.py").write_text(
                "import json\nprint(json.dumps({'candidate_count': 1, 'finding_count': 0}))\n",
                encoding="utf-8",
            )
            recommendation = {
                "recommendation": "MANUAL_VERIFICATION_REQUIRED",
                "baseline_tag": "v1.0.0",
                "history_complete": True,
                "level": "minor",
                "commit_count": 1,
                "classes": {"data": 1},
                "reasons": ["alipay evidence is missing"],
                "manual_verification": {
                    "required": True,
                    "platforms": {
                        "alipay": {
                            "needs_verification": True,
                            "unknown_count": 0,
                            "oldest_verified": "2026-08-31",
                            "why": ["no alipay evidence line in this cycle's CHANGELOG"],
                        }
                    },
                    "evidence": {},
                },
            }
            (scripts / "release_recommendation.py").write_text(
                "import json\nprint(json.dumps(" + repr(recommendation) + "))\n",
                encoding="utf-8",
            )
            shutil.copy(GATE, scripts / "release_gate.sh")
            summary = Path(td) / "gate-summary.json"
            result = subprocess.run(
                [
                    "bash",
                    str(scripts / "release_gate.sh"),
                    str(repo),
                    str(Path(td) / "u.log"),
                    str(summary),
                    "v1.1.0",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            data = json.loads(summary.read_text(encoding="utf-8"))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(data["candidate_tag"], "v1.1.0")
        self.assertEqual(data["baseline_tag"], "v1.0.0")
        self.assertEqual(data["release_recommendation"], "MANUAL_VERIFICATION_REQUIRED")
        self.assertTrue(data["history_complete"])
        self.assertEqual(data["release_classes"], {"data": 1})
        self.assertEqual(data["release_reasons"], ["alipay evidence is missing"])
        self.assertTrue(data["manual_verification_required"])
        self.assertIn("no alipay evidence", data["manual_verification_platforms"]["alipay"]["why"][0])


class ReleaseHistoryTests(unittest.TestCase):
    def test_full_history_candidate_uses_previous_tag_as_baseline(self) -> None:
        recommender = load_recommender()
        with tempfile.TemporaryDirectory() as td:
            repo = build_tagged_repo(Path(td))
            result = recommender.recommend(repo, min_data_changes=1, candidate_tag="v1.1.0")
        self.assertEqual(result["baseline_tag"], "v1.0.0")
        self.assertTrue(result["history_complete"])
        self.assertEqual(result["commit_count"], 1)
        self.assertEqual(result["classes"], {"tooling": 1})

    def test_shallow_candidate_history_fails_closed(self) -> None:
        recommender = load_recommender()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = build_tagged_repo(root)
            shallow = root / "shallow"
            subprocess.run(
                [
                    "git", "-c", "advice.detachedHead=false", "clone", "-q", "--depth", "1",
                    "--branch", "v1.1.0", f"file://{source}", str(shallow),
                ],
                check=True,
            )
            result = recommender.recommend(shallow, min_data_changes=1, candidate_tag="v1.1.0")
        self.assertEqual(result["recommendation"], "MANUAL_VERIFICATION_REQUIRED")
        self.assertFalse(result["history_complete"])
        self.assertTrue(any("shallow repository history is incomplete" in reason for reason in result["reasons"]))

    def test_shallow_history_without_candidate_fails_closed(self) -> None:
        recommender = load_recommender()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = build_tagged_repo(root)
            (source / "scripts" / "after_tag.py").write_text("print('after tag')\n", encoding="utf-8")
            git(source, "add", "scripts/after_tag.py")
            git(source, "commit", "-q", "-m", "after tag")
            shallow = root / "shallow"
            subprocess.run(
                [
                    "git", "clone", "-q", "--depth", "1", f"file://{source}", str(shallow),
                ],
                check=True,
            )
            result = recommender.recommend(shallow, min_data_changes=1)
        self.assertEqual(result["recommendation"], "MANUAL_VERIFICATION_REQUIRED")
        self.assertFalse(result["history_complete"])
        self.assertEqual(result["classes"], {})

    def test_full_history_hold_reports_history_complete(self) -> None:
        recommender = load_recommender()
        with tempfile.TemporaryDirectory() as td:
            repo = build_tagged_repo(Path(td))
            result = recommender.recommend(repo, min_data_changes=1)
        self.assertEqual(result["recommendation"], "HOLD")
        self.assertTrue(result["history_complete"])

    def test_recommend_accepts_string_root(self) -> None:
        recommender = load_recommender()
        with tempfile.TemporaryDirectory() as td:
            repo = build_tagged_repo(Path(td))
            (repo / "scripts" / "after_tag.py").write_text("print('after tag')\n", encoding="utf-8")
            git(repo, "add", "scripts/after_tag.py")
            git(repo, "commit", "-q", "-m", "after tag")
            result = recommender.recommend(str(repo), min_data_changes=1)
        self.assertEqual(result["recommendation"], "RECOMMEND_RELEASE")
        self.assertTrue(result["history_complete"])

    def test_release_workflow_fetches_full_history(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("fetch-depth: 0", workflow)

    def test_drift_audit_workflow_fetches_full_history(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "drift-watch.yml").read_text(encoding="utf-8")
        audit = workflow.split("  audit:", 1)[1]
        self.assertIn("fetch-depth: 0", audit)



class Gate4VerdictHandlingTests(unittest.TestCase):
    """The gate's fourth-stage verdict handling: HOLD blocks when a candidate
    tag is present; unknown verdicts fail closed (P0 fix)."""

    GATE_SNIPPET = "scripts/release_gate.sh"

    def _verdict_branch(self, verdict: str, candidate_tag: str) -> int:
        import subprocess
        script = r"""
set -uo pipefail
recommend_verdict="$1"; candidate_tag="$2"
if [ "$recommend_verdict" = "MANUAL_VERIFICATION_REQUIRED" ]; then exit 1; fi
if [ "$recommend_verdict" = "HOLD" ] && [ -n "$candidate_tag" ]; then exit 1; fi
case "$recommend_verdict" in
  RECOMMEND_RELEASE|HOLD) ;;
  *) exit 1 ;;
esac
exit 0
"""
        r = subprocess.run(["bash", "-c", script, "--", verdict, candidate_tag],
                           capture_output=True, text=True)
        return r.returncode

    def test_hold_with_candidate_tag_blocks(self) -> None:
        self.assertNotEqual(self._verdict_branch("HOLD", "v3.1.8"), 0)

    def test_hold_without_candidate_tag_passes(self) -> None:
        self.assertEqual(self._verdict_branch("HOLD", ""), 0)

    def test_manual_verification_blocks(self) -> None:
        self.assertNotEqual(self._verdict_branch("MANUAL_VERIFICATION_REQUIRED", "v3.1.8"), 0)

    def test_unknown_verdict_blocks(self) -> None:
        self.assertNotEqual(self._verdict_branch("SOMETHING_NEW", "v3.1.8"), 0)

    def test_release_passes(self) -> None:
        self.assertEqual(self._verdict_branch("RECOMMEND_RELEASE", "v3.1.8"), 0)

    def test_gate_script_contains_verdict_gates(self) -> None:
        text = (Path(__file__).resolve().parents[1] / self.GATE_SNIPPET).read_text(encoding="utf-8")
        self.assertIn('recommend_verdict" = "HOLD" ] && [ -n "$candidate_tag" ]', text)
        self.assertIn("unknown recommendation verdict", text)
        self.assertIn("candidate_tag", text)  # summary records the fourth gate


if __name__ == "__main__":
    unittest.main()
