#!/usr/bin/env python3
"""Check that all public README translations keep the same core structure."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Sequence


README_HEADINGS: dict[str, list[str]] = {
    "README.md": [
        "# 小程序开发工程技能套件",
        "## 32 秒看懂这套技能",
        "## 项目状态",
        "## 它解决了什么问题",
        "## 真实项目来源：语宠精灵",
        "## 它帮助 Agent 做到这些事",
        "## 平台规则保鲜（2.0 新增）",
        "## 能力清单",
        "## 设计原则",
        "## 适用场景",
        "## 使用方法",
        "## 它不会做什么",
        "## 验证",
        "## 包完整性",
        "## 当前版本",
        "## 许可证",
    ],
    "README.en.md": [
        "# Mini Program Engineering Skill Suite",
        "## Understand the Skill in 32 Seconds",
        "## Status",
        "## What It Solves",
        "## Real Project Origin: WordPet",
        "## Component Map",
        "## Design Principles",
        "## Platform Rule Freshness (new in 2.0)",
        "## Intended Use",
        "## How To Use",
        "## What It Does Not Do",
        "## Verification",
        "## Package Integrity",
        "## Version",
        "## License",
    ],
    "README.zh-Hant.md": [
        "# 小程式開發工程技能套件",
        "## 32 秒看懂這套技能",
        "## 專案狀態",
        "## 它解決了什麼問題",
        "## 真實專案來源：語寵精靈",
        "## 它幫助 Agent 做到這些事",
        "## 能力清單",
        "## 設計原則",
        "## 使用方法",
        "## 它不會做什麼",
        "## 驗證",
        "## 包完整性",
        "## 目前版本",
        "## 授權",
    ],
    "README.ja.md": [
        "# Mini Program Engineering Skill Suite",
        "## 32 秒で概要を見る",
        "## ステータス",
        "## 解決する課題",
        "## 実プロジェクト由来：WordPet",
        "## Agent ができるようになること",
        "## コンポーネント一覧",
        "## 設計原則",
        "## 使い方",
        "## しないこと",
        "## 検証",
        "## パッケージ完全性",
        "## バージョン",
        "## ライセンス",
    ],
    "README.th.md": [
        "# Mini Program Engineering Skill Suite",
        "## เข้าใจ Skill นี้ใน 32 วินาที",
        "## สถานะโปรเจกต์",
        "## แก้ปัญหาอะไร",
        "## ที่มาจากโปรเจกต์จริง: WordPet",
        "## ช่วยให้ Agent ทำอะไรได้",
        "## ความสามารถหลัก",
        "## หลักการออกแบบ",
        "## วิธีใช้",
        "## สิ่งที่ไม่ทำ",
        "## การตรวจสอบ",
        "## ความสมบูรณ์ของ package",
        "## เวอร์ชัน",
        "## สัญญาอนุญาต",
    ],
    "README.id.md": [
        "# Mini Program Engineering Skill Suite",
        "## Pahami Skill Ini dalam 32 Detik",
        "## Status Proyek",
        "## Masalah yang Diselesaikan",
        "## Asal dari Proyek Nyata: WordPet",
        "## Yang Dibantu untuk Agent",
        "## Peta Kemampuan",
        "## Prinsip Desain",
        "## Cara Menggunakan",
        "## Yang Tidak Dilakukan",
        "## Verifikasi",
        "## Integritas Paket",
        "## Versi",
        "## Lisensi",
    ],
}


HEADING_RE = re.compile(r"^(#{1,2})\s+.+$", re.MULTILINE)


def extract_headings(path: Path) -> list[str]:
    """Return top-level and second-level Markdown headings from a README."""
    text = path.read_text(encoding="utf-8")
    return [match.group(0).strip() for match in HEADING_RE.finditer(text)]


def check_i18n_readme_structure(root: Path) -> dict[str, object]:
    """Return a structured report for README heading consistency."""
    errors: list[str] = []
    checked: dict[str, list[str]] = {}
    for readme_name, expected in README_HEADINGS.items():
        path = root / readme_name
        if not path.is_file():
            errors.append(f"{readme_name}: missing README")
            continue
        actual = extract_headings(path)
        checked[readme_name] = actual
        if actual != expected:
            errors.append(
                f"{readme_name}: heading structure drifted; expected {len(expected)} headings, got {len(actual)}"
            )
    return {
        "valid": not errors,
        "errors": errors,
        "checked_readmes": len(checked),
        "expected_readmes": len(README_HEADINGS),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the README i18n structure check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("."), help="Suite root directory")
    args = parser.parse_args(argv)
    report = check_i18n_readme_structure(args.root.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
