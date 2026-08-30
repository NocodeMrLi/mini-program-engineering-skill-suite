#!/usr/bin/env python3
"""Static guards against workflow script injection and release-tag drift.

Codex audit finding (v3.1.4): `${{ github.event.inputs.* / inputs.* }}`
interpolated into `run:` script bodies executes before any shell-level
validation, so a tag like `v"; cmd; #` is command injection. These tests keep
every workflow free of that pattern — inputs reach scripts only via env.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

# `${{ ... }}` appearing inside a run: block (script body) — the injection shape.
RUN_BLOCK_RE = re.compile(r"run:\s*\|?\s*\n((?:[ \t]+.*\n?)+)", re.MULTILINE)
INTERP_RE = re.compile(r"\$\{\{.*?\}\}")
# The only sanctioned shapes: input references inside env:, if:, with:, name:,
# concurrency: value positions (parsed by Actions, never by a shell).
SAFE_CONTEXT_KEYS = ("env:", "if:", "with:", "concurrency:")


class WorkflowInjectionTests(unittest.TestCase):
    def test_workflows_exist(self) -> None:
        self.assertGreaterEqual(len(WORKFLOWS), 3)

    def test_no_input_interpolation_inside_run_bodies(self) -> None:
        """No `${{ ... }}` may appear inside any run: script body."""
        for path in WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            for match in RUN_BLOCK_RE.finditer(text):
                body = match.group(1)
                hits = INTERP_RE.findall(body)
                self.assertEqual(
                    hits,
                    [],
                    f"{path.name}: script body interpolates expressions ({hits}); "
                    "pass inputs via env: instead",
                )

    def test_release_tag_is_strictly_validated(self) -> None:
        """The release tag must use whole-variable bash matching, not line grep."""
        text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("RAW_TAG_INPUT", text)
        self.assertIn('[[ ! "$release_tag" =~ ^v[0-9]+', text)
        # the line-grep form is what let multi-line tags through; keep it out
        # of the VALIDATION step itself (mentions in comments are fine).
        step_start = text.index("Resolve release tag")
        step_block = text[step_start:text.index("Run release gates")]
        self.assertNotIn("grep -Eq", step_block)
        # explicit CR/LF refusal before the regex gate
        self.assertIn("$'\\n'*", step_block)
        self.assertIn("$'\\r'*", step_block)

    def test_strict_tag_regex_rejects_injection_shapes(self) -> None:
        """The exact validation used in release.yml rejects every injection probe."""
        import subprocess

        # Run the REAL shell validation (not a Python re-implementation):
        # grep-based versions passed multi-line inputs that bash [[ =~ ]] rejects.
        script = r'''
set -euo pipefail
release_tag="$1"
if [[ "$release_tag" == *$'\n'* || "$release_tag" == *$'\r'* ]]; then exit 1; fi
if [[ ! "$release_tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then exit 1; fi
exit 0
'''
        def shell_accepts(tag: str) -> bool:
            result = subprocess.run(
                ["bash", "-c", script, "--", tag],
                capture_output=True, text=True,
            )
            return result.returncode == 0

        rejected = [
            'v1.2.3\nINJECTED=1',  # the multi-line probe that beat grep
            "v1.2.3\rINJECTED",
            'v"; printf "INJECTED"; #',
            "v$(echo INJECTED > /tmp/x)",
            "v1.2.3; rm -rf /",
            "v1.2.3 && curl evil",
            "  v1.2.3",
            "v1.2.3-beta",
            "1.2.3",
            "",
        ]
        for probe in rejected:
            self.assertFalse(shell_accepts(probe), f"shell accepted probe: {probe!r}")
        self.assertTrue(shell_accepts("v3.1.6"))


if __name__ == "__main__":
    unittest.main()
