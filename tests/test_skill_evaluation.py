#!/usr/bin/env python3
"""Deterministic contracts for the internal three-tier Skill evaluation suite."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = ROOT / "tests" / "evals"
ROUTING_FILES = (
    EVAL_ROOT / "routing-development.json",
    EVAL_ROOT / "routing-held-out.json",
)
BEHAVIOR_FILES = (
    EVAL_ROOT / "behavior-development.json",
    EVAL_ROOT / "behavior-held-out.json",
)
RUNNER = EVAL_ROOT / "run_evaluations.py"
SIGNER = EVAL_ROOT / "independent_signer.py"
BEHAVIOR_JUDGE = EVAL_ROOT / "judge_behavior.py"

SKILLS = {
    "mini-program-project-intake-skill",
    "mini-program-product-spec-skill",
    "mini-program-architecture-skill",
    "wechat-mini-program-platform-skill",
    "mini-program-implementation-skill",
    "mini-program-ui-device-skill",
    "mini-program-debugging-skill",
    "mini-program-verification-skill",
    "mini-program-release-skill",
}
BEHAVIOR_CAPABILITIES = {
    "read-only-boundary",
    "no-product-invention",
    "preview-confirmation",
    "root-cause-first",
    "evidence-layering",
    "external-action-authorization",
}


def load_cases(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


class EvaluationAssetsTests(unittest.TestCase):
    def test_internal_eval_assets_exist(self) -> None:
        for path in (*ROUTING_FILES, *BEHAVIOR_FILES, RUNNER, SIGNER, BEHAVIOR_JUDGE):
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())

    def test_routing_corpus_has_required_coverage_and_disjoint_splits(self) -> None:
        development, held_out = (load_cases(path) for path in ROUTING_FILES)
        development_ids = {str(case["id"]) for case in development}
        held_out_ids = {str(case["id"]) for case in held_out}
        self.assertFalse(development_ids & held_out_ids)

        all_cases = development + held_out
        self.assertGreaterEqual(len(all_cases), 54)
        self.assertEqual({str(case["language"]) for case in all_cases}, {"zh", "en"})
        self.assertEqual(
            {str(case["kind"]) for case in all_cases},
            {"positive", "negative", "boundary", "collision"},
        )
        for split in (development, held_out):
            for skill in SKILLS:
                for language in ("zh", "en"):
                    with self.subTest(skill=skill, language=language):
                        self.assertTrue(
                            any(
                                case["kind"] == "positive"
                                and case["language"] == language
                                and case["expected"] == [skill]
                                for case in split
                            )
                        )

        for case in all_cases:
            self.assertIsInstance(case["prompt"], str)
            self.assertTrue(str(case["prompt"]).strip())
            expected = case["expected"]
            self.assertIsInstance(expected, list)
            self.assertLessEqual(set(expected), SKILLS)
            if case["kind"] == "negative":
                self.assertEqual(expected, [])
            if case["kind"] == "collision":
                self.assertGreaterEqual(len(expected), 2)

    def test_behavior_corpus_covers_guardrails_and_disjoint_splits(self) -> None:
        development, held_out = (load_cases(path) for path in BEHAVIOR_FILES)
        development_ids = {str(case["id"]) for case in development}
        held_out_ids = {str(case["id"]) for case in held_out}
        self.assertFalse(development_ids & held_out_ids)
        all_cases = development + held_out
        self.assertEqual({str(case["capability"]) for case in all_cases}, BEHAVIOR_CAPABILITIES)
        self.assertEqual({str(case["language"]) for case in all_cases}, {"zh", "en"})
        for case in all_cases:
            self.assertIn(case["fixture"], {"healthy", "ambiguous", "buggy", "release"})
            self.assertTrue(case["required"])
            self.assertTrue(case["forbidden"])

    def test_eval_material_is_not_in_public_allowlist(self) -> None:
        validator = (ROOT / "scripts" / "validate_suite.py").read_text(encoding="utf-8")
        exporter = (ROOT / "scripts" / "export_public_package.py").read_text(encoding="utf-8")
        for marker in ("tests/evals", "routing-development", "behavior-held-out"):
            self.assertNotIn(marker, validator)
            self.assertNotIn(marker, exporter)


class EvaluationRunnerTests(unittest.TestCase):
    def test_tier1_passes_current_suite(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RUNNER), "tier1", "--suite", str(ROOT)],
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["tier"], 1)
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["skill_count"], 10)
        self.assertGreaterEqual(report["checks"], 5)

    def test_reference_routing_replays_both_splits(self) -> None:
        for split in ("development", "held-out"):
            with self.subTest(split=split):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(RUNNER),
                        "tier2",
                        "--suite",
                        str(ROOT),
                        "--split",
                        split,
                        "--engine",
                        "reference",
                    ],
                    capture_output=True,
                    check=False,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["verdict"], "PASS")
                self.assertEqual(report["accuracy"], 1.0)
                self.assertGreater(report["case_count"], 0)

    def test_independent_signer_uses_three_verdicts_and_fixed_thresholds(self) -> None:
        source = SIGNER.read_text(encoding="utf-8")
        for verdict in ("PASS", "FAIL", "NOT_PROVEN"):
            self.assertIn(verdict, source)
        self.assertIn("ROUTING_MINIMUM", source)
        self.assertIn("BEHAVIOR_NON_REGRESSION_MINIMUM", source)
        self.assertIn("HELD_OUT_MINIMUM", source)


if __name__ == "__main__":
    unittest.main()
