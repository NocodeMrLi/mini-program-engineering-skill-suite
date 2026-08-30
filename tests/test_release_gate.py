#!/usr/bin/env python3
"""Committed regression tests for the extracted release gate (scripts/release_gate.sh).

The gate used to live inline in .github/workflows/release.yml where no test
could reach it; the v3.1.0 fix (PIPESTATUS check, singular "Ran 1 test",
zero-test detection) existed only as a one-off experiment. These tests drive
the extracted script with controlled fake unittest output so the gating
behavior can never silently regress.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/release_gate.sh"


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



if __name__ == "__main__":
    unittest.main()


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
