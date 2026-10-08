"""Instruction distribution, source independence and closed evaluation contracts.

These checks protect document/loading contracts, not live platform behavior.
Scenario responses are measured separately by run_upgrade02.py.
"""
import copy
import contextlib
import io
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("upgrade02_eval", ROOT / "tests/evals/run_upgrade02.py")
EVAL = importlib.util.module_from_spec(spec)
spec.loader.exec_module(EVAL)


class ScenarioJudgeTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads((ROOT / "tests/evals/upgrade02-scenarios.json").read_text())["cases"]
        self.answer = {"decisions": [dict(id=c["id"], choice=c["expected"], reason="test observation") for c in self.cases]}

    def test_complete_schema_and_wrong_decision_fail(self):
        self.assertEqual(EVAL.judge(self.cases, self.answer)["passed"], 28)
        self.answer["decisions"][0]["choice"] = next(x for x in "ABC" if x != self.cases[0]["expected"])
        result = EVAL.judge(self.cases, self.answer)
        self.assertTrue(result["valid"])
        self.assertEqual(result["passed"], 27)
        self.assertFalse(result["cases"][0]["passed"])

    def test_missing_duplicate_extra_or_malformed_fail_closed(self):
        invalid = [None, [], {"decisions": []}, {**self.answer, "verdict": "PASS"}]
        for mutation in ("missing", "duplicate", "extra", "unknown", "bad-choice", "no-reason", "bad-type"):
            obj = copy.deepcopy(self.answer)
            rows = obj["decisions"]
            if mutation == "missing": rows.pop()
            elif mutation == "duplicate": rows[0] = rows[1]
            elif mutation == "extra": rows.append(rows[0])
            elif mutation == "unknown": rows[0]["id"] = "other"
            elif mutation == "bad-choice": rows[0]["choice"] = "AB"
            elif mutation == "no-reason": rows[0]["reason"] = " "
            elif mutation == "bad-type": rows[0]["choice"] = True
            invalid.append(obj)
        for obj in invalid:
            with self.subTest(obj=obj):
                self.assertFalse(EVAL.judge(self.cases, obj)["valid"])

    def test_all_items_have_distinct_original_pairs(self):
        self.assertEqual(len({c["id"] for c in self.cases}), 28)
        self.assertEqual(len({c["scenario"] for c in self.cases}), 28)
        for item in range(1, 15):
            self.assertEqual(sum(c["item"] == item for c in self.cases), 2)
        self.assertEqual({c["expected"] for c in self.cases}, set("ABC"))

    def test_prompts_are_answer_key_blind_and_read_only(self):
        prompt, fingerprint = EVAL.build_prompt(ROOT, self.cases)
        visible = json.loads(prompt.split("SCENARIOS\n", 1)[1])
        self.assertTrue(all(set(c) == {"id", "scenario", "choices"} for c in visible))
        self.assertNotIn('"expected"', prompt)
        self.assertEqual(len(fingerprint), 64)
        self.assertIn("不要调用工具", prompt)
        # Missing suite contents cannot masquerade as a native baseline.
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "suite-contract-missing"):
                EVAL.build_prompt(Path(folder), self.cases)

    def test_missing_contract_and_undeclared_baseline_omission_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            suite = Path(folder)
            (suite / "VERSION").write_text("3.2.0\n")
            for name in EVAL.CONTRACTS[:-1]:
                target = suite / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("test contract")
            self.assertEqual(EVAL.preflight_suite(suite, require_new=False), "3.2.0")
            with self.assertRaisesRegex(ValueError, "suite-contract-missing"):
                EVAL.preflight_suite(suite)
            (suite / "VERSION").write_text("3.3.0\n")
            with self.assertRaisesRegex(ValueError, "baseline-omission-not-declared"):
                EVAL.preflight_suite(suite, require_new=False)

    def test_stale_answer_directory_rejected_before_any_cli_invocation(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            old = output / "batch1-baseline-answer.json"
            old.write_text(json.dumps(self.answer))
            argv = ["eval", "--baseline", str(ROOT), "--candidate", str(ROOT), "--output", str(output)]
            with patch.object(sys, "argv", argv), patch.object(EVAL.subprocess, "check_output") as cli_version, \
                    patch.object(EVAL.subprocess, "run") as cli, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as exc:
                    EVAL.main()
                self.assertEqual(exc.exception.code, 2)
                cli_version.assert_not_called()
                cli.assert_not_called()
            self.assertEqual(json.loads(old.read_text()), self.answer)

    def test_success_exit_without_new_answer_fails_and_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "new-evidence"
            argv = ["eval", "--baseline", str(ROOT), "--candidate", str(ROOT), "--output", str(output)]
            fake = subprocess.CompletedProcess([], 0, "", "")
            with patch.object(sys, "argv", argv), patch.object(EVAL.subprocess, "check_output", return_value="test CLI"), \
                    patch.object(EVAL.subprocess, "run", return_value=fake) as cli, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(EVAL.main(), 2)
                self.assertEqual(cli.call_count, 1)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["runs"][0]["error"], "answer-missing")
            self.assertNotIn("verdict", report)


class ContractDistributionTests(unittest.TestCase):
    def test_new_platform_reference_is_required_and_reachable(self):
        platform = "platforms/wechat/commerce-and-cloud-contracts.md"
        self.assertIn(platform, (ROOT / "scripts/validate_suite.py").read_text())
        for relative in ("skills/wechat-mini-program-platform-skill/SKILL.md",
                         "skills/mini-program-verification-skill/references/verification-workflow.md"):
            self.assertIn("commerce-and-cloud-contracts.md", (ROOT / relative).read_text())

    def test_platform_document_not_claiming_fixed_sdk_or_rule_facts(self):
        text = (ROOT / "platforms/wechat/commerce-and-cloud-contracts.md").read_text()
        for clause in ("实际访问主体", "省略环境变量不等于删除", "身份仅来自平台可信上下文",
                       "观测过期只刷新", "多行日志不能算多次", "测试事件与真实事件分开",
                       "脱敏的稳定业务关联标识", "公开报告只保留安全引用"):
            self.assertIn(clause, text)
        self.assertNotIn("userInfo", text)
        self.assertNotIn("tcbContext", text)

    def test_high_risk_contracts_keep_storage_and_protocol_boundaries(self):
        text = (ROOT / "skills/mini-program-architecture-skill/references/cloud-state-and-write-contracts.md").read_text()
        for clause in ("原子保存待确认意图", "物理索引", "不为测试通过删除唯一约束",
                       "诊断、日志、告警关闭不能跳过", "晚到结果", "独立重序列化适配器",
                       "不排序第三方", "随机补键", "未执行组合保持未核"):
            self.assertIn(clause, text)

    def test_client_and_delivery_do_not_remove_authorization(self):
        text = (ROOT / "skills/mini-program-implementation-skill/references/implementation-workflow.md").read_text()
        for clause in ("只释放对应本次请求", "保留原请求标识", "旧拒绝不能清掉新请求",
                       "普通入口", "无付款不等于无副作用", "生产构建和预览参数不能误开"):
            self.assertIn(clause, text)

    def test_evidence_empty_windows_and_privacy_versions_not_promoted(self):
        evidence = (ROOT / "skills/mini-program-verification-skill/references/evidence-admissibility.md").read_text()
        privacy = (ROOT / "platforms/wechat/privacy-permission-matrix.md").read_text()
        for clause in ("不能提供未出现语义的默认值", "相同文件内容不证明同来源", "不清除历史未结"):
            self.assertIn(clause, evidence)
        for clause in ("全部入口", "服务端 API", "旧通过不覆盖新处理", "分类证据不明确时保持未核"):
            self.assertIn(clause, privacy)

    def test_enter_exit_cycle_and_cost_have_explicit_limits(self):
        routing = (ROOT / "references/routing-and-state-machine.md").read_text()
        release = (ROOT / "skills/mini-program-release-skill/references/cloud-release-operations.md").read_text()
        for clause in ("产物生成阶段", "入口/退出", "循环依赖", "保留真实交易", "用户决定"):
            self.assertIn(clause, routing)
        for clause in ("情景区间", "成本单位", "独立资金决定", "禁止整包套回", "未核"):
            self.assertIn(clause, release)
        verifier = (ROOT / "skills/mini-program-verification-skill/references/verification-workflow.md").read_text()
        cost_row = next(line for line in verifier.splitlines() if "资源测算合同" in line)
        self.assertIn("../../mini-program-release-skill/references/cloud-release-operations.md", cost_row)

    def test_no_unconditional_tool_install_or_desktop_copy(self):
        text = (ROOT / "skills/mini-program-project-intake-skill/references/intake-workflow.md").read_text()
        for clause in ("不接管 GUI", "混有未验收改动", "有效冻结产物复用",
                       "不能统一放桌面", "不恢复已收起副本", "未取实际结果"):
            self.assertIn(clause, text)
        for clause in ("质量是核心底线", "用户可验收增量", "接回条件", "重复检查无新信息就停止",
                       "新增可验收结果", "没有界面的任务"):
            self.assertIn(clause, text)
        root = (ROOT / "SKILL.md").read_text()
        self.assertIn("内部测试数量不代表用户进度", root)

    def test_missing_public_reference_blocks_receiving_package(self):
        # Real export/receiver path, not a synthetic count assertion.
        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder) / "package"
            export = subprocess.run([sys.executable, str(ROOT / "scripts/export_public_package.py"),
                                     str(ROOT), "--output", str(package)], capture_output=True, text=True)
            self.assertEqual(export.returncode, 0, export.stderr + export.stdout)
            target = package / "platforms/wechat/commerce-and-cloud-contracts.md"
            self.assertTrue(target.is_file())
            target.unlink()
            result = subprocess.run([sys.executable, str(package / "scripts/verify_public_package.py"),
                                     str(package)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("file-missing", json.loads(result.stdout)["errors"])


if __name__ == "__main__":
    unittest.main()
