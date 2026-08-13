#!/usr/bin/env python3
"""Contracts for the Step 5 historical engineering methodology upgrade."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = ROOT / "tests" / "evals"
RECOVERY = ROOT / "skills/mini-program-debugging-skill/references/interruption-recovery-protocol.md"
LINEAGE = ROOT / "skills/mini-program-ui-device-skill/assets/asset-lineage-record.md"
ADMISSIBILITY = ROOT / "skills/mini-program-verification-skill/references/evidence-admissibility.md"
METHODOLOGY_FILES = (
    EVAL_ROOT / "methodology-development.json",
    EVAL_ROOT / "methodology-held-out.json",
)
SECOND_HELD_OUT = EVAL_ROOT / "methodology-v2-held-out.json"
THIRD_HELD_OUT = EVAL_ROOT / "methodology-v3-held-out.json"
FOURTH_HELD_OUT = EVAL_ROOT / "methodology-v4-held-out.json"
METHODOLOGY_SIGNER = EVAL_ROOT / "independent_methodology_signer.py"
CAPABILITIES = {
    "interruption-recovery",
    "asset-lineage",
    "evidence-admissibility",
}


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def cases(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


class PublicMethodologyContractTests(unittest.TestCase):
    def test_three_methodology_resources_are_public_and_reachable(self) -> None:
        for path in (RECOVERY, LINEAGE, ADMISSIBILITY):
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())

        validator = read("scripts/validate_suite.py")
        root_skill = read("SKILL.md")
        for path in (RECOVERY, LINEAGE, ADMISSIBILITY):
            relative = path.relative_to(ROOT).as_posix()
            self.assertIn(relative, validator)
            self.assertIn(relative, root_skill)

    def test_interruption_recovery_forbids_blind_replay(self) -> None:
        protocol = RECOVERY.read_text(encoding="utf-8")
        for required in (
            "unknown",
            "工具异常",
            "超时",
            "用户中止",
            "盲目重放",
            "工作区",
            "进程",
            "产物",
            "日志",
            "外部状态",
            "幂等",
            "重放授权",
        ):
            self.assertIn(required, protocol)
        self.assertIn("已确认生效", protocol)
        self.assertIn("已确认未生效", protocol)
        self.assertIn("仍不确定", protocol)
        self.assertIn("只读刷新不等于启动", protocol)
        self.assertIn("已有日志和产物", protocol)

        for relative in (
            "shared/engineering-guardrails.md",
            "skills/mini-program-debugging-skill/SKILL.md",
            "skills/mini-program-release-skill/SKILL.md",
        ):
            with self.subTest(path=relative):
                body = read(relative)
                self.assertIn("unknown", body)
                self.assertRegex(body, r"中断|超时|重放")
        debugging_skill = read("skills/mini-program-debugging-skill/SKILL.md")
        self.assertIn("只读检查命令", debugging_skill)
        self.assertIn("不属于启动业务或构建进程", debugging_skill)
        self.assertIn("计算并输出已有产物指纹", debugging_skill)
        self.assertIn("四项全部建立前明确禁止重放", debugging_skill)

    def test_asset_lineage_records_identity_transforms_and_approval_scope(self) -> None:
        template = LINEAGE.read_text(encoding="utf-8")
        for required in (
            "asset-id",
            "原始资产",
            "衍生资产",
            "来源",
            "处理工具",
            "处理方式",
            "目标槽位",
            "尺寸",
            "透明通道",
            "SHA-256",
            "批准状态",
            "替换关系",
        ):
            self.assertIn(required, template)
        self.assertIn("看起来相同", template)
        self.assertIn("不等于", template)
        self.assertIn("默认保留旧资产", template)
        self.assertIn("回滚入口", template)

        for relative in (
            "skills/mini-program-ui-device-skill/SKILL.md",
            "skills/mini-program-implementation-skill/SKILL.md",
        ):
            with self.subTest(path=relative):
                self.assertIn("资产谱系", read(relative))
        ui_skill = read("skills/mini-program-ui-device-skill/SKILL.md")
        self.assertIn("批准只覆盖点名文件、变体和目标槽位", ui_skill)
        self.assertIn("不得删除旧资产", ui_skill)
        self.assertIn("不能只把保留与回滚列为 unknown", ui_skill)
        self.assertIn("只读输出本身形成可复查回滚记录", ui_skill)

    def test_evidence_admissibility_records_scope_and_limitations(self) -> None:
        policy = ADMISSIBILITY.read_text(encoding="utf-8")
        for required in (
            "admissible",
            "limited",
            "not-admissible",
            "产生工具",
            "格式",
            "工具版本",
            "时间",
            "环境",
            "指纹",
            "采集方式",
            "适用结论",
            "不能证明",
            "完整性",
            "独立性",
        ):
            self.assertIn(required, policy)
        self.assertIn("不是交付生命周期状态", policy)

        for relative in (
            "skills/mini-program-verification-skill/SKILL.md",
            "skills/mini-program-release-skill/SKILL.md",
        ):
            with self.subTest(path=relative):
                body = read(relative)
                self.assertIn("可采信", body)
                self.assertIn("不能证明", body)


class MethodologyEvaluationContractTests(unittest.TestCase):
    def test_development_and_held_out_cases_cover_each_capability(self) -> None:
        development, held_out = (cases(path) for path in METHODOLOGY_FILES)
        self.assertFalse(
            {str(case["id"]) for case in development}
            & {str(case["id"]) for case in held_out}
        )
        self.assertEqual({str(case["capability"]) for case in development}, CAPABILITIES)
        self.assertEqual({str(case["capability"]) for case in held_out}, CAPABILITIES)
        self.assertEqual({str(case["kind"]) for case in development}, {"representative"})
        self.assertEqual({str(case["kind"]) for case in held_out}, {"boundary"})
        self.assertEqual(
            {str(case["language"]) for case in development + held_out},
            {"zh", "en"},
        )
        for case in development + held_out:
            self.assertIn(case["fixture"], {"interrupted", "assets", "evidence"})
            self.assertTrue(case["required"])
            self.assertTrue(case["forbidden"])

    def test_runner_and_signer_support_methodology_without_public_export(self) -> None:
        runner = read("tests/evals/run_evaluations.py")
        signer = METHODOLOGY_SIGNER.read_text(encoding="utf-8")
        self.assertIn("--dataset", runner)
        self.assertIn("methodology", runner)
        self.assertIn("methodology-v2", runner)
        self.assertIn("methodology-v3", runner)
        self.assertIn("methodology-v4", runner)
        for capability in CAPABILITIES:
            self.assertIn(capability, runner)
        for verdict in ("PASS", "FAIL", "NOT_PROVEN"):
            self.assertIn(verdict, signer)
        self.assertIn("HELD_OUT_MINIMUM = 1.00", signer)
        self.assertIn("NON_REGRESSION_MINIMUM = 0.00", signer)
        self.assertIn("--regression-held-out", signer)

        validator = read("scripts/validate_suite.py")
        exporter = read("scripts/export_public_package.py")
        for marker in ("methodology-development.json", "independent_methodology_signer.py"):
            self.assertNotIn(marker, validator)
            self.assertNotIn(marker, exporter)

    def test_second_held_out_is_new_and_keeps_the_same_fixed_capabilities(self) -> None:
        second = cases(SECOND_HELD_OUT)
        previous_ids = {
            str(case["id"])
            for path in METHODOLOGY_FILES
            for case in cases(path)
        }
        self.assertFalse(previous_ids & {str(case["id"]) for case in second})
        self.assertEqual({str(case["capability"]) for case in second}, CAPABILITIES)
        self.assertEqual({str(case["kind"]) for case in second}, {"boundary"})
        for case in second:
            self.assertTrue(case["required"])
            self.assertTrue(case["forbidden"])

    def test_third_held_out_is_new_and_keeps_the_same_fixed_capabilities(self) -> None:
        third = cases(THIRD_HELD_OUT)
        previous_ids = {
            str(case["id"])
            for path in METHODOLOGY_FILES + (SECOND_HELD_OUT,)
            for case in cases(path)
        }
        self.assertFalse(previous_ids & {str(case["id"]) for case in third})
        self.assertEqual({str(case["capability"]) for case in third}, CAPABILITIES)
        self.assertEqual({str(case["kind"]) for case in third}, {"boundary"})
        for case in third:
            self.assertTrue(case["required"])
            self.assertTrue(case["forbidden"])

    def test_fourth_held_out_is_new_and_keeps_the_same_fixed_capabilities(self) -> None:
        fourth = cases(FOURTH_HELD_OUT)
        previous_ids = {
            str(case["id"])
            for path in METHODOLOGY_FILES + (SECOND_HELD_OUT, THIRD_HELD_OUT)
            for case in cases(path)
        }
        self.assertFalse(previous_ids & {str(case["id"]) for case in fourth})
        self.assertEqual({str(case["capability"]) for case in fourth}, CAPABILITIES)
        self.assertEqual({str(case["kind"]) for case in fourth}, {"boundary"})
        for case in fourth:
            self.assertTrue(case["required"])
            self.assertTrue(case["forbidden"])


if __name__ == "__main__":
    unittest.main()
