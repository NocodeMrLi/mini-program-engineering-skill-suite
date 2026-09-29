#!/usr/bin/env python3
"""Focused tests for deterministic source inventory and report provenance."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_source_inventory.py"
SPEC = importlib.util.spec_from_file_location("audit_source_inventory", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceInventoryTests(unittest.TestCase):
    def test_count_hash_and_anonymous_git_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            project = parent / "snapshot"
            project.mkdir()
            (project / "app.js").write_text("App({})\n", encoding="utf-8")
            (project / "pages").mkdir()
            (project / "pages" / "today.js").write_text("Page({})\n", encoding="utf-8")
            (project / "node_modules").mkdir()
            (project / "node_modules" / "ignored.js").write_text("x", encoding="utf-8")
            (project / ".git").write_text("gitdir: /not-a-real-worktree\n", encoding="utf-8")
            first = MODULE.inventory(project)
            self.assertEqual(first["files"], ["app.js", "pages/today.js"])
            self.assertEqual(first["file_count"], 2)
            self.assertEqual(first["git_commit"], "unknown")
            self.assertEqual(first["tree_sha256"], MODULE.inventory(project)["tree_sha256"])
            (project / "app.js").write_text("App({changed:true})\n", encoding="utf-8")
            self.assertNotEqual(first["tree_sha256"], MODULE.inventory(project)["tree_sha256"])

    def test_rejects_bad_count_commit_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.js").write_text("a", encoding="utf-8")
            facts = MODULE.inventory(root)
            self.assertEqual(MODULE.check_report("I read all 1 files", facts), [])
            self.assertIn("file-count-mismatch:2!=1", MODULE.check_report("I read all 2 files", facts))
            self.assertIn("unsupported-commit-claim", MODULE.check_report("commit `c988190`", facts))
            (root / "link.js").symlink_to(root / "a.js")
            with self.assertRaisesRegex(ValueError, "source-nonregular"):
                MODULE.inventory(root)

    def test_cli_checks_report_without_modifying_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source"
            root.mkdir()
            (root / "app.js").write_text("App({})", encoding="utf-8")
            report = Path(temp) / "report.md"
            report.write_text("Full read of snapshot (2 files)", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(root), "--report", str(report)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)["valid"])
            self.assertEqual(MODULE.inventory(root)["file_count"], 1)


if __name__ == "__main__":
    unittest.main()
