from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SIGNER = ROOT / "tests/evals/final_release_signer.py"
JUDGE = ROOT / "tests/evals/judge_final_release.py"


class FinalReleaseSignerTests(unittest.TestCase):
    def test_public_version_matches_metadata_and_changelog(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        frontmatter = (ROOT / "SKILL.md").read_text(encoding="utf-8").split("---\n", 2)[1]
        self.assertIn(f'version: "{version}"', frontmatter)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## {version} - ", changelog)
        self.assertIn("## 1.1.0 - 2026-08-13", changelog)
        self.assertNotIn("## Unreleased", changelog)

    def test_release_actions_cannot_bundle_separate_authorizations(self) -> None:
        release = (ROOT / "skills/mini-program-release-skill/SKILL.md").read_text(encoding="utf-8")
        workflow = (
            ROOT / "skills/mini-program-release-skill/references/release-governance-workflow.md"
        ).read_text(encoding="utf-8")
        for text in (release, workflow):
            self.assertIn("每个行动条目只能包含一个外部动作", text)
            self.assertIn("不得合并授权", text)

    def test_second_behavior_held_out_is_new_and_supported(self) -> None:
        original = json.loads((ROOT / "tests/evals/behavior-held-out.json").read_text(encoding="utf-8"))
        fresh = json.loads((ROOT / "tests/evals/behavior-v2-held-out.json").read_text(encoding="utf-8"))
        self.assertEqual(fresh["split"], "held-out")
        self.assertEqual(len(fresh["cases"]), 3)
        self.assertTrue(
            {item["id"] for item in original["cases"]}.isdisjoint(item["id"] for item in fresh["cases"])
        )
        runner = (ROOT / "tests/evals/run_evaluations.py").read_text(encoding="utf-8")
        self.assertIn('"behavior-v2"', runner)

    def test_preview_without_assets_still_provides_bounded_candidates(self) -> None:
        ui = (ROOT / "skills/mini-program-ui-device-skill/SKILL.md").read_text(encoding="utf-8")
        workflow = (
            ROOT / "skills/mini-program-ui-device-skill/references/ui-device-workflow.md"
        ).read_text(encoding="utf-8")
        for text in (ui, workflow):
            self.assertIn("缺少可渲染素材时", text)
            self.assertIn("具名文字候选", text)
            self.assertIn("不等于已渲染预览", text)
            self.assertIn("自包含 SVG 或 HTML", text)
            self.assertIn("不写入项目", text)

    def test_third_behavior_held_out_is_new_and_supported(self) -> None:
        prior_ids: set[str] = set()
        for name in ("behavior-held-out.json", "behavior-v2-held-out.json"):
            payload = json.loads((ROOT / "tests/evals" / name).read_text(encoding="utf-8"))
            prior_ids.update(item["id"] for item in payload["cases"])
        fresh = json.loads((ROOT / "tests/evals/behavior-v3-held-out.json").read_text(encoding="utf-8"))
        self.assertEqual(len(fresh["cases"]), 3)
        self.assertTrue(prior_ids.isdisjoint(item["id"] for item in fresh["cases"]))
        runner = (ROOT / "tests/evals/run_evaluations.py").read_text(encoding="utf-8")
        self.assertIn('"behavior-v3"', runner)

    def make_evidence(self, root: Path, *, verdict: str = "PASS", version: str | None = None) -> list[str]:
        version = version or (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        documents = {
            "tier1.json": {"verdict": verdict},
            "routing-dev.json": {"verdict": "PASS", "accuracy": 1.0},
            "routing-held.json": {"verdict": "PASS", "accuracy": 1.0},
            "behavior-dev.json": {"verdict": "PASS", "skill_pass_rate": 1.0, "non_regression": True},
            "behavior-held.json": {"verdict": "PASS", "skill_pass_rate": 1.0, "non_regression": True},
            "method-dev.json": {"verdict": "PASS", "skill_pass_rate": 1.0, "non_regression": True},
            "method-held.json": {"verdict": "PASS", "skill_pass_rate": 1.0, "non_regression": True},
            "validate.json": {"valid": True, "errors": []},
            "sensitive.json": {"finding_count": 0, "findings": []},
            "package.json": {"valid": True, "verified_file_count": 2, "errors": []},
            "independent.json": {"verdict": "PASS", "blockers": []},
            "manifest-a.json": {"suite_version": version, "file_count": 2, "files": [{"path": "A"}, {"path": "B"}]},
        }
        documents["manifest-b.json"] = documents["manifest-a.json"]
        for name, payload in documents.items():
            (root / name).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        (root / "VERSION").write_text(version + "\n", encoding="utf-8")
        return [
            sys.executable,
            str(SIGNER),
            "--tier1", str(root / "tier1.json"),
            "--routing-development", str(root / "routing-dev.json"),
            "--routing-held-out", str(root / "routing-held.json"),
            "--behavior-development", str(root / "behavior-dev.json"),
            "--behavior-held-out", str(root / "behavior-held.json"),
            "--methodology-development", str(root / "method-dev.json"),
            "--methodology-held-out", str(root / "method-held.json"),
            "--validation", str(root / "validate.json"),
            "--sensitive", str(root / "sensitive.json"),
            "--package-verification", str(root / "package.json"),
            "--manifest-a", str(root / "manifest-a.json"),
            "--manifest-b", str(root / "manifest-b.json"),
            "--version-file", str(root / "VERSION"),
            "--expected-version", version,
            "--independent-judgment", str(root / "independent.json"),
        ]

    def test_final_judge_and_signer_exist(self) -> None:
        self.assertTrue(JUDGE.is_file())
        self.assertTrue(SIGNER.is_file())

    def test_signer_passes_complete_consistent_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            command = self.make_evidence(Path(temp))
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["verdict"], "PASS")

    def test_signer_rejects_failed_gate_version_drift_and_manifest_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            command = self.make_evidence(root, verdict="FAIL")
            (root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            manifest_b = json.loads((root / "manifest-b.json").read_text(encoding="utf-8"))
            manifest_b["files"][0]["path"] = "changed"
            (root / "manifest-b.json").write_text(json.dumps(manifest_b, sort_keys=True), encoding="utf-8")
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            report = json.loads(result.stdout)
            self.assertEqual(report["verdict"], "FAIL")
            self.assertIn("tier1-not-pass", report["errors"])
            self.assertIn("version-file-mismatch", report["errors"])
            self.assertIn("public-manifest-mismatch", report["errors"])


if __name__ == "__main__":
    unittest.main()
