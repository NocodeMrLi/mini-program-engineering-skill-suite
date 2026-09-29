#!/usr/bin/env python3
"""Contracts for the evidence-filtered 2026-09-28 Skill suite upgrade."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "artifact_nondegradation_gate.py"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def load_gate():
    spec = importlib.util.spec_from_file_location("artifact_nondegradation_gate", GATE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Tier 4 gate")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict) -> str:
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def write_blob(path: Path, value: str) -> str:
    raw = value.encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def make_bundle(root: Path, *, case_count: int = 2) -> Path:
    cases: list[dict] = []
    for case_index in range(case_count):
        case_id = f"case-{case_index + 1}"
        controls = {
            "prompt_sha256": hashlib.sha256(f"prompt:{case_id}".encode()).hexdigest(),
            "snapshot_sha256": hashlib.sha256(f"snapshot:{case_id}".encode()).hexdigest(),
            "environment_sha256": hashlib.sha256(b"fixture-environment").hexdigest(),
            "model": "fixture-model",
            "model_version": "fixture-model-1",
            "permissions_sha256": "a" * 64,
            "tools_sha256": "b" * 64,
            "time_budget_seconds": 600,
            "call_budget": 12,
            "retry_budget": 1,
            "retry_count": 0,
        }
        attestations: list[dict[str, str]] = []
        run_ids: dict[str, list[str]] = {"baseline": [], "with-skill": []}
        run_artifacts: dict[str, dict[str, str]] = {"baseline": {}, "with-skill": {}}
        for arm in ("baseline", "with-skill"):
            for repetition in (1, 2):
                run_id = f"{case_id}-{arm}-{repetition}"
                artifact_name = f"{run_id}.txt"
                artifact_sha = write_blob(root / artifact_name, f"anonymous artifact {run_id}\n")
                record = {
                    "schema_version": 1,
                    "case_id": case_id,
                    "arm": arm,
                    "run_id": run_id,
                    "repetition": repetition,
                    "controls": controls,
                    "artifact_path": artifact_name,
                    "artifact_sha256": artifact_sha,
                }
                record_name = f"{run_id}.json"
                record_sha = write_json(root / record_name, record)
                attestations.append({"record_path": record_name, "record_sha256": record_sha})
                run_ids[arm].append(run_id)
                run_artifacts[arm][run_id] = artifact_sha
        for values in run_ids.values():
            values.sort()
        judgment = {
            "schema_version": 1,
            "case_id": case_id,
            "blind": True,
            "source_labels_hidden": True,
            "artifact_order_randomized": True,
            "rubric_sha256": "c" * 64,
            "judge_engine": "fixture-judge",
            "judge_model": "fixture-judge-1",
            "generated_at_utc": "2026-09-28T00:00:00Z",
            "run_ids": run_ids,
            "run_artifacts": run_artifacts,
            "critical_errors": {"baseline": 0, "with-skill": 0},
            "target_scores": {"baseline": 70.0, "with-skill": 80.0},
            "dimensions": {
                "correctness": {"critical": True, "baseline": 90.0, "with-skill": 90.0},
                "completeness": {"critical": False, "baseline": 70.0, "with-skill": 85.0},
            },
        }
        judgment_name = f"{case_id}-judgment.json"
        judgment_sha = write_json(root / judgment_name, judgment)
        cases.append(
            {
                "id": case_id,
                "runs": attestations,
                "judgment_path": judgment_name,
                "judgment_sha256": judgment_sha,
            }
        )
    bundle = {
        "schema_version": 1,
        "candidate_tag": "v3.2.0",
        "candidate_commit": "d" * 40,
        "skill_behavior_sha256": "e" * 64,
        "evaluation_harness_sha256": "f" * 64,
        "engine": "fixture-runner",
        "model": "fixture-model",
        "model_version": "fixture-model-1",
        "generated_at_utc": "2026-09-28T00:00:00Z",
        "minimum_runs_per_arm": 2,
        "minimum_case_count": 2,
        "minimum_mean_target_gain": 5.0,
        "cases": cases,
    }
    path = root / "tier4-bundle.json"
    write_json(path, bundle)
    return path


def mutate_json(path: Path, update) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    update(value)
    write_json(path, value)


class SkillContractUpgradeTests(unittest.TestCase):
    def test_u1_u2_are_wired_into_intake_and_specification(self) -> None:
        intake = read("skills/mini-program-project-intake-skill/SKILL.md")
        relocation = read("skills/mini-program-project-intake-skill/references/relocation-and-pivot-audit.md")
        spec = read("skills/mini-program-product-spec-skill/SKILL.md")
        template = read("skills/mini-program-product-spec-skill/assets/product-specification.md")
        for marker in ("Git 顶层目录", "规范化远端", "五向基线"):
            self.assertIn(marker, intake + relocation)
        for marker in ("unresolved", "confirmed-existing", "confirmed-absent", "重复提交"):
            self.assertIn(marker, spec + template)

    def test_u3_u5_u7_are_concrete_architecture_and_release_contracts(self) -> None:
        architecture = read("skills/mini-program-architecture-skill/references/cloud-state-and-write-contracts.md")
        release = read("skills/mini-program-release-skill/references/cloud-release-operations.md")
        for marker in (
            "部分变量必须 fail-closed",
            "持久化首次成功结果",
            "作用域由服务端会话",
            "只有有效结果才可写完成态",
        ):
            self.assertIn(marker, architecture)
        for marker in ("production build", "production start", "not-verified", "发布后云环境交接"):
            self.assertIn(marker, release)

    def test_u4_u6_u8_have_execution_and_negative_boundaries(self) -> None:
        assets = read("skills/mini-program-implementation-skill/references/cloud-asset-delivery-workflow.md")
        ui = read("skills/mini-program-ui-device-skill/references/runtime-state-and-layout-contracts.md")
        quality = read("skills/mini-program-verification-skill/references/dimensional-quality-contract.md")
        for marker in ("Manifest", "Executor", "Verifier", "Report", "旧版 → 新版 → 旧版"):
            self.assertIn(marker, assets)
        for marker in ("resolved-empty", "attempt ID", "整页高度预算", "safe-area"):
            self.assertIn(marker, ui)
        for marker in ("稳定 ID", "专项维度", "`N/A`", "`check`"):
            self.assertIn(marker, quality)

    def test_audit_findings_require_reproducible_coverage_and_counterevidence(self) -> None:
        intake = read("skills/mini-program-project-intake-skill/SKILL.md")
        verification = read("skills/mini-program-verification-skill/SKILL.md")
        workflow = read("skills/mini-program-verification-skill/references/verification-workflow.md")
        for marker in ("确定性目录画像", "同一份工具清单", "已发现问题", "未发现问题", "证据不足"):
            self.assertIn(marker, intake)
        for marker in ("机制反证闭环", "调用实参", "条件求值", "实际分支/兜底", "主动查找能推翻"):
            self.assertIn(marker, verification + workflow)
        self.assertIn("空对象和空数组仍为 truthy", workflow)
        self.assertIn("降级或标记 `unknown`", workflow)

    def test_partial_snapshot_cannot_prove_repository_absence_or_release_blocker(self) -> None:
        intake = read("skills/mini-program-project-intake-skill/SKILL.md")
        workflow = read("skills/mini-program-verification-skill/references/verification-workflow.md")
        combined = intake + workflow
        for marker in (
            "部分快照",
            "完整性声明",
            "未包含",
            "真实仓库缺失",
            "构建失败",
            "发布阻断",
        ):
            self.assertIn(marker, combined)
        self.assertIn("只可标记为证据不足", workflow)
        self.assertIn("实际构建或解析失败", workflow)

    def test_evidence_quality_labels_are_required_in_final_output(self) -> None:
        verification = read("skills/mini-program-verification-skill/SKILL.md")
        minimum_output = verification.split("## 最低输出", 1)[1].split("## 停止条件", 1)[0]
        self.assertIn("`admissible / limited / not-admissible`", minimum_output)
        self.assertIn("没有专用字段", minimum_output)
        self.assertIn("不能代替证据质量标签", minimum_output)

    def test_audit_coverage_traces_each_domain_and_challenges_claims(self) -> None:
        verification = read("skills/mini-program-verification-skill/SKILL.md")
        risk_steps = verification.split("## 风险分层验证", 1)[1].split("## 状态与证据边界", 1)[0]
        minimum_output = verification.split("## 最低输出", 1)[1].split("## 停止条件", 1)[0]
        for marker in (
            "用工具枚举", "输入→写入→读取→呈现", "全称注释/承诺",
            "实际表达式", "游标走完集合并再次前进", "同一输入比较集合长度变化前后的索引",
            "非法数值", "重进", "不能只建议未来补测试", "未证实不得判无发现", "以发现为主体",
            "onLoad→onShow→onHide→onShow→onUnload", "创建、暂停、恢复、销毁", "`NaN`、无穷和小数",
        ):
            self.assertIn(marker, risk_steps)
        self.assertIn("承诺、实际表达式、边界输入或最小反例、结论", minimum_output)
        self.assertIn("页面生命周期证据和断点", minimum_output)

    def test_anonymous_audit_does_not_inherit_external_version_claims(self) -> None:
        verification = read("skills/mini-program-verification-skill/SKILL.md")
        self.assertIn("匿名快照无 Git 时填 `unknown`", verification)
        self.assertIn("不借外层提交", verification)
        self.assertIn("数量须由清单算出，否则不报", verification)

    def test_read_only_audit_uses_bounded_route_and_inventory(self) -> None:
        root = read("SKILL.md")
        route = read("references/routing-and-state-machine.md")
        verification = read("skills/mini-program-verification-skill/SKILL.md")
        audit = read("skills/mini-program-verification-skill/references/source-audit-workflow.md")
        validator = read("scripts/validate_suite.py")
        self.assertIn("源码审计短路径", root)
        self.assertIn("只读源码审计模式", route)
        self.assertIn("references/source-audit-workflow.md", verification)
        self.assertIn("scripts/audit_source_inventory.py", audit)
        self.assertIn("不声称“已读全部文件”", audit)
        self.assertIn('"scripts/audit_source_inventory.py"', validator)

    def test_new_public_references_and_tier4_gate_are_allowlisted(self) -> None:
        validator = read("scripts/validate_suite.py")
        root_skill = read("SKILL.md")
        paths = (
            "skills/mini-program-project-intake-skill/references/relocation-and-pivot-audit.md",
            "skills/mini-program-architecture-skill/references/cloud-state-and-write-contracts.md",
            "skills/mini-program-implementation-skill/references/cloud-asset-delivery-workflow.md",
            "skills/mini-program-ui-device-skill/references/runtime-state-and-layout-contracts.md",
            "skills/mini-program-verification-skill/references/dimensional-quality-contract.md",
            "skills/mini-program-release-skill/references/cloud-release-operations.md",
            "scripts/artifact_nondegradation_gate.py",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertIn(path, validator)
                self.assertIn(path, root_skill)


class ArtifactNondegradationGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_gate()

    def test_complete_paired_evidence_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            bundle = make_bundle(Path(temp))
            report = self.module.validate_bundle(bundle)
        self.assertEqual(report["verdict"], "PASS", report["problems"])
        self.assertEqual(report["stage"], "artifact-nondegradation")
        self.assertEqual(report["case_count"], 2)
        self.assertEqual(report["run_count"], 8)
        self.assertEqual(report["critical_error_count"], 0)
        self.assertEqual(report["critical_regression_count"], 0)
        self.assertGreaterEqual(report["mean_target_gain"], report["minimum_mean_target_gain"])

    def test_missing_artifact_and_control_mismatch_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = make_bundle(root)
            payload = json.loads(bundle.read_text(encoding="utf-8"))
            first_record = root / payload["cases"][0]["runs"][0]["record_path"]
            record = json.loads(first_record.read_text(encoding="utf-8"))
            (root / record["artifact_path"]).unlink()
            second = payload["cases"][0]["runs"][1]
            second_path = root / second["record_path"]
            def invalidate_controls(value: dict) -> None:
                value["controls"]["call_budget"] = 99
                value["controls"]["environment_sha256"] = "invalid"
                value["controls"]["model"] = "different-model"
                value["controls"]["model_version"] = "different-model-1"
                value["controls"]["retry_budget"] = -1
                value["controls"]["retry_count"] = 2
            mutate_json(second_path, invalidate_controls)
            second["record_sha256"] = hashlib.sha256(second_path.read_bytes()).hexdigest()
            write_json(bundle, payload)
            report = self.module.validate_bundle(bundle)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("artifact-missing" in item for item in report["problems"]))
        self.assertTrue(any("controls-not-equivalent" in item for item in report["problems"]))
        self.assertTrue(any("environment_sha256-invalid" in item for item in report["problems"]))
        self.assertTrue(any("model-mismatch" in item for item in report["problems"]))
        self.assertTrue(any("model-version-mismatch" in item for item in report["problems"]))
        self.assertTrue(any("retry_budget-invalid" in item for item in report["problems"]))
        self.assertTrue(any("retry-count-exceeds-budget" in item for item in report["problems"]))

    def test_blinding_critical_regression_and_zero_gain_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = make_bundle(root)
            payload = json.loads(bundle.read_text(encoding="utf-8"))
            judgment = root / payload["cases"][0]["judgment_path"]
            def degrade(value: dict) -> None:
                value["blind"] = False
                value["target_scores"]["with-skill"] = 70.0
                value["dimensions"]["correctness"]["with-skill"] = 80.0
            mutate_json(judgment, degrade)
            payload["cases"][0]["judgment_sha256"] = hashlib.sha256(judgment.read_bytes()).hexdigest()
            other = root / payload["cases"][1]["judgment_path"]
            mutate_json(other, lambda value: value["target_scores"].__setitem__("with-skill", 70.0))
            payload["cases"][1]["judgment_sha256"] = hashlib.sha256(other.read_bytes()).hexdigest()
            write_json(bundle, payload)
            report = self.module.validate_bundle(bundle)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("not-blind" in item for item in report["problems"]))
        self.assertTrue(any("critical-regression" in item for item in report["problems"]))
        self.assertIn("bundle:mean-target-gain-below-minimum", report["problems"])

    def test_critical_error_and_single_case_target_regression_cannot_be_averaged_away(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = make_bundle(root)
            payload = json.loads(bundle.read_text(encoding="utf-8"))
            first = root / payload["cases"][0]["judgment_path"]
            def fail_first(value: dict) -> None:
                value["critical_errors"]["with-skill"] = 1
                value["target_scores"]["with-skill"] = 60.0
            mutate_json(first, fail_first)
            payload["cases"][0]["judgment_sha256"] = hashlib.sha256(first.read_bytes()).hexdigest()
            second = root / payload["cases"][1]["judgment_path"]
            mutate_json(second, lambda value: value["target_scores"].__setitem__("with-skill", 100.0))
            payload["cases"][1]["judgment_sha256"] = hashlib.sha256(second.read_bytes()).hexdigest()
            write_json(bundle, payload)
            report = self.module.validate_bundle(bundle)
        self.assertGreaterEqual(report["mean_target_gain"], report["minimum_mean_target_gain"])
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("with-skill-critical-errors" in item for item in report["problems"]))
        self.assertTrue(any("target-regression" in item for item in report["problems"]))

    def test_baseline_error_is_a_comparator_not_a_candidate_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = make_bundle(root)
            payload = json.loads(bundle.read_text(encoding="utf-8"))
            first = root / payload["cases"][0]["judgment_path"]
            mutate_json(first, lambda value: value["critical_errors"].__setitem__("baseline", 1))
            payload["cases"][0]["judgment_sha256"] = hashlib.sha256(first.read_bytes()).hexdigest()
            write_json(bundle, payload)
            report = self.module.validate_bundle(bundle)
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["critical_error_count"], 0)

    def test_baseline_critical_error_count_must_still_be_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = make_bundle(root)
            payload = json.loads(bundle.read_text(encoding="utf-8"))
            first = root / payload["cases"][0]["judgment_path"]
            mutate_json(first, lambda value: value["critical_errors"].__setitem__("baseline", -1))
            payload["cases"][0]["judgment_sha256"] = hashlib.sha256(first.read_bytes()).hexdigest()
            write_json(bundle, payload)
            report = self.module.validate_bundle(bundle)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("baseline-critical-errors-invalid" in item for item in report["problems"]))

    def test_insufficient_runs_and_tampered_hash_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = make_bundle(root)
            payload = json.loads(bundle.read_text(encoding="utf-8"))
            removed = payload["cases"][0]["runs"].pop()
            record = json.loads((root / removed["record_path"]).read_text(encoding="utf-8"))
            artifact = root / record["artifact_path"]
            artifact.write_text("tampered\n", encoding="utf-8")
            first_record = root / payload["cases"][1]["runs"][0]["record_path"]
            first = json.loads(first_record.read_text(encoding="utf-8"))
            (root / first["artifact_path"]).write_text("tampered too\n", encoding="utf-8")
            write_json(bundle, payload)
            report = self.module.validate_bundle(bundle)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("runs-below-minimum" in item for item in report["problems"]))
        self.assertTrue(any("artifact-sha256-mismatch" in item for item in report["problems"]))

    def test_judgment_must_bind_the_exact_artifact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = make_bundle(root)
            payload = json.loads(bundle.read_text(encoding="utf-8"))
            judgment = root / payload["cases"][0]["judgment_path"]
            def replace_binding(value: dict) -> None:
                run_id = next(iter(value["run_artifacts"]["with-skill"]))
                value["run_artifacts"]["with-skill"][run_id] = "0" * 64
            mutate_json(judgment, replace_binding)
            payload["cases"][0]["judgment_sha256"] = hashlib.sha256(judgment.read_bytes()).hexdigest()
            write_json(bundle, payload)
            report = self.module.validate_bundle(bundle)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("artifact-binding-mismatch" in item for item in report["problems"]))

    def test_one_case_nonfinite_score_and_symlink_evidence_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = make_bundle(root)
            payload = json.loads(bundle.read_text(encoding="utf-8"))
            payload["cases"] = payload["cases"][:1]
            judgment = root / payload["cases"][0]["judgment_path"]
            mutate_json(judgment, lambda value: value["target_scores"].__setitem__("with-skill", float("nan")))
            payload["cases"][0]["judgment_sha256"] = hashlib.sha256(judgment.read_bytes()).hexdigest()
            first = payload["cases"][0]["runs"][0]
            record_path = root / first["record_path"]
            real_record = root / "real-record.json"
            record_path.replace(real_record)
            record_path.symlink_to(real_record)
            first["record_sha256"] = hashlib.sha256(real_record.read_bytes()).hexdigest()
            write_json(bundle, payload)
            report = self.module.validate_bundle(bundle)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertIn("bundle:cases-below-minimum", report["problems"])
        self.assertTrue(any("target-score-invalid" in item for item in report["problems"]))
        self.assertTrue(any("outside-evidence-root" in item for item in report["problems"]))

    def test_malformed_arm_and_nul_artifact_path_fail_with_a_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = make_bundle(root)
            payload = json.loads(bundle.read_text(encoding="utf-8"))
            arm_attestation = payload["cases"][0]["runs"][0]
            arm_record = root / arm_attestation["record_path"]
            mutate_json(arm_record, lambda value: value.__setitem__("arm", []))
            arm_attestation["record_sha256"] = hashlib.sha256(arm_record.read_bytes()).hexdigest()
            path_attestation = payload["cases"][0]["runs"][1]
            path_record = root / path_attestation["record_path"]
            mutate_json(path_record, lambda value: value.__setitem__("artifact_path", "\x00"))
            path_attestation["record_sha256"] = hashlib.sha256(path_record.read_bytes()).hexdigest()
            write_json(bundle, payload)
            report = self.module.validate_bundle(bundle)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("arm-invalid" in item for item in report["problems"]))
        self.assertTrue(any("artifact-path-invalid" in item for item in report["problems"]))

    def test_bundle_symlink_fails_closed_through_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = make_bundle(root)
            link = root / "tier4-bundle-link.json"
            link.symlink_to(bundle)
            result = subprocess.run(
                [sys.executable, str(GATE), str(link)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "FAIL")
        self.assertTrue(any("bundle-unreadable" in item for item in report["problems"]))

    def test_release_chain_requires_tier4_stage(self) -> None:
        evaluation_gate = read("scripts/evaluation_gate.py")
        signer = read("tests/evals/final_release_signer.py")
        judge = read("tests/evals/judge_final_release.py")
        summary = read("scripts/summarize_evaluations.py")
        evaluations = read("EVALUATIONS.md")
        for text in (evaluation_gate, signer, judge, summary, evaluations):
            self.assertIn("artifact-nondegradation", text)
        self.assertIn('"scripts/artifact_nondegradation_gate.py"', evaluation_gate)
        self.assertIn("zero critical errors or critical regressions", judge)
        self.assertIn("tier4", evaluations.lower())


if __name__ == "__main__":
    unittest.main()
