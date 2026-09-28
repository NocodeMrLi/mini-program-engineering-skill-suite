#!/usr/bin/env python3
"""Validate and sign one fresh release-evaluation declaration.

The private key is supplied by a controlled caller and is never printed or
persisted by this module. Fresh evidence binds a release-subject commit; the
current HEAD may differ only by the candidate's redacted evidence files and
EVALUATIONS.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import evaluation_gate
from evidence_signature import sign_document, verify_signed_document


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def attest(
    root: Path,
    candidate_tag: str,
    declaration_path: Path,
    private_key: Path,
    trusted_public_key: Path,
) -> dict[str, Any]:
    root = root.resolve()
    declaration_path = declaration_path.resolve()
    expected_parent = (root / ".github" / "release-evidence").resolve()
    if declaration_path.parent != expected_parent:
        raise ValueError("declaration-path-outside-release-evidence")
    declaration = evaluation_gate.load_evaluation_artifact(declaration_path)
    if "signature" in declaration:
        raise ValueError("declaration-already-signed")
    problems: list[str] = []
    if declaration.get("schema_version") != 2:
        problems.append("schema-version-invalid")
    if declaration.get("candidate_tag") != candidate_tag:
        problems.append("candidate-tag-mismatch")
    if declaration.get("mode") != "fresh":
        problems.append("mode-not-fresh")
    for field in ("engine", "model", "generated_at_utc"):
        if not _nonempty(declaration.get(field)):
            problems.append(f"{field}-missing")
    fresh_problems, _ = evaluation_gate.verify_fresh(
        root,
        candidate_tag,
        declaration,
        declaration_path.parent,
        candidate_ref="HEAD",
    )
    problems.extend(fresh_problems)
    if problems:
        raise ValueError("fresh-evidence-invalid:" + ";".join(problems))
    signed = sign_document(
        declaration,
        private_key,
        evaluation_gate.TRUSTED_SIGNER_KEY_ID,
    )
    verify_signed_document(
        signed,
        trusted_public_key,
        expected_key_id=evaluation_gate.TRUSTED_SIGNER_KEY_ID,
    )
    return signed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--candidate-tag", required=True)
    parser.add_argument("--declaration", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--trusted-public-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        signed = attest(
            args.root,
            args.candidate_tag,
            args.declaration,
            args.private_key,
            args.trusted_public_key,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(signed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"release evidence signing blocked: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "candidate_tag": args.candidate_tag,
                "output": str(args.output),
                "signer_key_id": evaluation_gate.TRUSTED_SIGNER_KEY_ID,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
