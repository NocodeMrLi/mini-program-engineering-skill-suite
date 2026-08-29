from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / "scripts/capability_doctor.py"
ADAPTER = ROOT / "skills/mini-program-verification-skill/references/verification-capability-matrix.md"
QUALITY = ROOT / "skills/mini-program-verification-skill/assets/quality-evidence-matrix.md"
PRIVACY = ROOT / "platforms/wechat/privacy-permission-matrix.md"
ACCESSIBILITY = ROOT / "skills/mini-program-ui-device-skill/assets/accessibility-matrix.md"


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


class CapabilityDoctorTests(unittest.TestCase):
    def run_doctor(self, root: Path) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(DOCTOR), str(root)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_detects_native_without_mutating_or_leaking_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / "app.json").write_text(
                json.dumps({"pages": ["pages/home/index"], "subpackages": [{"root": "feature"}]}),
                encoding="utf-8",
            )
            (project / "project.config.json").write_text(
                json.dumps({"miniprogramRoot": "src/", "appid": "private-app-id"}), encoding="utf-8"
            )
            (project / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {"test": "jest --runInBand", "build": "private-token-in-command"},
                        "devDependencies": {"miniprogram-simulate": "1.0.0", "jest": "29.0.0"},
                    }
                ),
                encoding="utf-8",
            )
            (project / ".env").write_text("SECRET_MARKER=do-not-read\n", encoding="utf-8")
            before = tree_digest(project)
            report = self.run_doctor(project)
            self.assertEqual(tree_digest(project), before)
            self.assertEqual(report["framework"], "native-wechat")
            self.assertEqual(report["target_platforms"], ["wechat"])
            self.assertTrue(report["facts"]["has_subpackages"])
            self.assertIn("miniprogram-simulate", report["capabilities"])
            rendered = json.dumps(report, ensure_ascii=False)
            self.assertNotIn(str(project), rendered)
            self.assertNotIn("private-app-id", rendered)
            self.assertNotIn("private-token-in-command", rendered)
            self.assertNotIn("SECRET_MARKER", rendered)

    def test_detects_uniapp_multi_target_platforms(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / "manifest.json").write_text(
                json.dumps({"name": "anonymous", "mp-weixin": {"appid": ""}, "mp-alipay": {}}),
                encoding="utf-8",
            )
            (project / "pages.json").write_text(
                json.dumps({"pages": ["pages/index/index"]}), encoding="utf-8"
            )
            (project / "package.json").write_text(
                json.dumps({"dependencies": {"@dcloudio/uni-app": "3.0.0"}}), encoding="utf-8"
            )
            report = self.run_doctor(project)
            self.assertEqual(report["framework"], "uni-app")
            self.assertEqual(report["target_platforms"], ["alipay", "wechat"])

    def test_detects_taro_script_targets_with_unknown_suffix_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            config_dir = project / "config"
            config_dir.mkdir()
            (config_dir / "index.js").write_text("export default {};\n", encoding="utf-8")
            (project / "package.json").write_text(
                json.dumps(
                    {
                        "scripts": {
                            "dev:weapp": "npm run build:weapp -- --watch",
                            "build:tt": "tarox build --type tt",
                            "build:xhs": "tarox build --type xhs",
                        }
                    }
                ),
                encoding="utf-8",
            )
            report = self.run_doctor(project)
            self.assertEqual(report["framework"], "taro")
            self.assertEqual(report["target_platforms"], ["douyin", "wechat"])
            self.assertIn("unrecognized-target:xhs", report["warnings"])

    def test_detects_taro_uni_app_and_ambiguous_projects_without_guessing(self) -> None:
        fixtures = (
            ({"dependencies": {"@tarojs/taro": "4.0.0"}, "scripts": {"build:weapp": "taro build --type weapp"}}, "taro"),
            ({"dependencies": {"@dcloudio/uni-app": "3.0.0"}, "scripts": {"build:mp-weixin": "uni build"}}, "uni-app"),
            (
                {
                    "dependencies": {"@tarojs/taro": "4.0.0", "@dcloudio/uni-app": "3.0.0"},
                    "scripts": {"build:weapp": "taro build", "build:mp-weixin": "uni build"},
                },
                "ambiguous",
            ),
        )
        for package, expected in fixtures:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                (project / "package.json").write_text(json.dumps(package), encoding="utf-8")
                if expected in {"uni-app", "ambiguous"}:
                    (project / "manifest.json").write_text(json.dumps({"mp-weixin": {}}), encoding="utf-8")
                    (project / "pages.json").write_text(json.dumps({"pages": []}), encoding="utf-8")
                report = self.run_doctor(project)
                self.assertEqual(report["framework"], expected)
                self.assertEqual(sorted(report["script_names"]), sorted(package["scripts"]))

    def test_unknown_project_is_reported_as_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = self.run_doctor(Path(temp))
            self.assertEqual(report["framework"], "unknown")
            self.assertIn("manual-confirmation-required", report["constraints"])


class QualityMatrixTests(unittest.TestCase):
    def test_step6_resources_exist_and_are_linked(self) -> None:
        for path in (DOCTOR, ADAPTER, QUALITY, PRIVACY, ACCESSIBILITY):
            self.assertTrue(path.is_file(), path)
        root = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        verification = (ROOT / "skills/mini-program-verification-skill/SKILL.md").read_text(encoding="utf-8")
        platform = (ROOT / "skills/wechat-mini-program-platform-skill/SKILL.md").read_text(encoding="utf-8")
        ui = (ROOT / "skills/mini-program-ui-device-skill/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("capability_doctor.py", root)
        self.assertIn("verification-capability-matrix.md", verification)
        self.assertIn("quality-evidence-matrix.md", verification)
        self.assertIn("privacy-permission-matrix.md", platform)
        self.assertIn("accessibility-matrix.md", ui)

    def test_adapter_contract_is_optional_and_evidence_safe(self) -> None:
        text = ADAPTER.read_text(encoding="utf-8")
        for term in ("原生", "Taro", "uni-app", "miniprogram-simulate", "条件等待", "元素等待"):
            self.assertIn(term, text)
        for term in ("不自动安装", "不能替代真机", "不得执行项目命令"):
            self.assertIn(term, text)

    def test_privacy_accessibility_and_quality_contracts_cover_required_layers(self) -> None:
        privacy = PRIVACY.read_text(encoding="utf-8")
        for term in ("源码 API", "配置声明", "平台申报", "用户拒绝", "撤回", "unknown"):
            self.assertIn(term, privacy)
        self.assertIn("不能证明平台申报", privacy)

        accessibility = ACCESSIBILITY.read_text(encoding="utf-8")
        for term in ("ARIA", "读屏", "动态字体", "对比度", "触控热区", "焦点顺序"):
            self.assertIn(term, accessibility)
        self.assertIn("静态检查不能证明真机", accessibility)

        quality = QUALITY.read_text(encoding="utf-8")
        for term in ("包体", "分包", "启动", "首屏", "请求错误", "未处理拒绝", "发布后观察窗"):
            self.assertIn(term, quality)
        for term in ("阈值来源", "基线版本", "环境", "回滚条件", "不能替代正式环境"):
            self.assertIn(term, quality)


if __name__ == "__main__":
    unittest.main()
