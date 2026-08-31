#!/usr/bin/env python3
"""Machine-readable evaluation gate: no release without fresh or verifiably
reused tier2/tier3/judge/signer evidence (audit P1-01).

This gate is a REQUIRED input of scripts/release_gate.sh, so a release cannot
be packaged without it. Two admission modes, both fail-closed:

- fresh: this release reran the evaluations named in the policy. Every named
  stage must have a PASS artifact whose recorded version equals the candidate
  and whose suite/evaluation-harness fingerprints match the current tree.
- reuse (patch only): this release reuses a previous release's artifacts. The
  reused release must exist, every reused artifact must PASS there, the
  candidate's own fingerprints must equal the reused release's, and no
  behavior/evaluation-harness file may differ between the two commits.

Fingerprints deliberately hash FILE CONTENT, not commit ids: a new commit that
only bumps VERSION/SKILL.md frontmatter metadata must remain reuse-eligible,
while any behavioral text change breaks the hash and forbids reuse. Zero-LLM
by construction (file reads and JSON only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from evidence_signature import SignatureError, verify_signed_document

# Stages whose PASS is required for minor/major releases (the README's
# "门禁全 PASS 才发布" contract). tier1/validation/sensitive/package are
# enforced by the other release gates on every run and are not duplicated here.
REQUIRED_STAGES: tuple[str, ...] = (
    "routing-development",
    "routing-held-out",
    "behavior-development",
    "behavior-held-out",
    "methodology-development",
    "methodology-held-out",
    "independent-judgment",
    "final-signature",
)

# Behavior text: a change here always invalidates evidence reuse.
BEHAVIOR_PREFIXES: tuple[str, ...] = ("skills/", "shared/", "SKILL.md", "foundation/")
# Evaluation harness: a change here also invalidates reuse even when the skill
# text is identical (the measuring instrument itself moved).
HARNESS_PREFIXES: tuple[str, ...] = ("tests/evals/",)

# Root SKILL.md frontmatter lines that are release METADATA (version,
# last_reviewed), not behavior text: identical policy to
# release_recommendation.ROOT_SKILL_METADATA_LINE. A diff that only moves
# these lines keeps the reuse chain intact.
ROOT_SKILL_METADATA_DIFF = ("version", "last_reviewed")
TRUSTED_SIGNER_KEY_ID = "release-evaluation-2026-08-31"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_frontmatter_metadata_diff(root: Path, old_rev: str, new_rev: str, path: str) -> bool:
    """True when a root-SKILL.md content difference is only version metadata."""
    if path != "SKILL.md":
        return False
    old = git_blob(root, old_rev, path)
    new = git_blob(root, new_rev, path)
    if old is None or new is None:
        return False

    def frontmatter_parts(text: bytes) -> tuple[dict[str, list[str]], bytes] | None:
        """Flatten frontmatter to key -> list of leaf 'key: value' strings.

        Nested blocks (metadata:) collapse to their LEAF lines only, so a
        version bump inside metadata changes version/last_reviewed and nothing
        else — a giant folded string would diff on any nesting change.
        """
        lines = text.decode("utf-8", errors="replace").splitlines()
        if not lines or lines[0].strip() != "---":
            return None
        pairs: dict[str, list[str]] = {}
        current_parent = ""
        closing_index: int | None = None
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                closing_index = index
                break
            if not line.strip():
                continue
            indented = line[:1] in {" ", "\t"}
            key, sep, value = line.strip().partition(":")
            if not sep:
                continue
            if not indented:
                current_parent = key if not value else ""
                if value:
                    pairs.setdefault(key, []).append(line.strip())
            else:
                if current_parent:
                    pairs.setdefault(f"{current_parent}.{key}", []).append(line.strip())
                else:
                    pairs.setdefault(key, []).append(line.strip())
        if closing_index is None:
            return None
        body = "\n".join(lines[closing_index + 1 :]).encode("utf-8")
        return pairs, body

    old_parts = frontmatter_parts(old)
    new_parts = frontmatter_parts(new)
    if old_parts is None or new_parts is None:
        return False
    old_fm, old_body = old_parts
    new_fm, new_body = new_parts
    # A metadata exemption is valid only when every byte outside frontmatter
    # is unchanged. The former implementation ignored the body and allowed a
    # version bump to hide a simultaneous behavior change.
    if old_body != new_body:
        return False
    changed_keys: set[str] = set()
    for key in set(old_fm) | set(new_fm):
        if old_fm.get(key) != new_fm.get(key):
            changed_keys.add(key)
    allowed = {f"metadata.{field}" for field in ROOT_SKILL_METADATA_DIFF} | set(ROOT_SKILL_METADATA_DIFF)
    return bool(changed_keys) and changed_keys <= allowed

SEMVER_ORDER = {"patch": 0, "minor": 1, "major": 2}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_semver(tag: str) -> tuple[int, int, int] | None:
    body = tag[1:] if tag.startswith("v") else tag
    parts = body.split(".")
    if len(parts) != 3:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def semver_bump(baseline: str, candidate: str) -> str | None:
    """Return patch/minor/major for baseline->candidate, None if not a bump."""
    base = parse_semver(baseline)
    cand = parse_semver(candidate)
    if base is None or cand is None:
        return None
    if cand <= base:
        return None
    if cand[0] != base[0]:
        return "major"
    if cand[1] != base[1]:
        return "minor"
    return "patch"


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise ValueError(f"git-{args[0]}-failed:{result.stderr.strip()[:200]}")
    return result.stdout


def git_blob(root: Path, rev: str, path: str) -> bytes | None:
    """Read one file's bytes at a revision; None when absent there."""
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{rev}:{path}"],
        capture_output=True, check=False,
    )
    return result.stdout if result.returncode == 0 else None


def git_ls_files(root: Path, rev: str) -> list[str]:
    return [line for line in git(root, "ls-tree", "-r", "--name-only", rev).splitlines() if line.strip()]


def commit_of(root: Path, ref: str) -> str:
    return git(root, "rev-parse", f"{ref}^{{}}").strip()


def is_release_tag(tag: str) -> bool:
    return parse_semver(tag) is not None


def release_tags(root: Path) -> list[str]:
    tags = [line.strip() for line in git(root, "tag", "--list", "v*").splitlines() if line.strip()]
    parsed = [(parse_semver(t), t) for t in tags]
    parsed = [(v, t) for v, t in parsed if v is not None]
    return [t for _, t in sorted(parsed)]


def classify_path(path: str) -> str | None:
    """Map one repo path to behavior/harness, or None for unrelated files."""
    for prefix in BEHAVIOR_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return "behavior"
    for prefix in HARNESS_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return "harness"
    return None


def fingerprint_paths(root: Path, rev: str, kinds: tuple[str, ...]) -> dict[str, str]:
    """Content fingerprint of every tracked file whose class is in kinds.

    The map is path -> sha256(blob bytes at rev); empty files still hash to a
    real digest, and a path that exists at one rev but not the other shows up
    as a hash mismatch (or a missing key), so deletions are covered too.
    """
    fingerprint: dict[str, str] = {}
    for path in git_ls_files(root, rev):
        label = classify_path(path)
        if label not in kinds:
            continue
        blob = git_blob(root, rev, path)
        if blob is not None:
            fingerprint[path] = sha256_bytes(blob)
    return fingerprint


def aggregate_fingerprint(fingerprint: dict[str, str]) -> str:
    return sha256_bytes(json.dumps(fingerprint, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def load_evaluation_artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing-artifact:{path.name}")
    if path.stat().st_size > 20_000_000:
        raise ValueError(f"oversized-artifact:{path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid-artifact:{path.name}:not-object")
    return value


def artifact_passes(report: dict[str, Any]) -> bool:
    return report.get("verdict") == "PASS"


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None


def validate_stage_attestations(stages: Any, source_version: str) -> list[str]:
    """Validate the signed, minimal attestations for all eight private stages."""
    if not isinstance(stages, dict):
        return ["evidence:stages-not-object"]
    problems: list[str] = []
    missing = sorted(set(REQUIRED_STAGES) - set(stages))
    extra = sorted(set(stages) - set(REQUIRED_STAGES))
    for stage in missing:
        problems.append(f"evidence:stage-missing:{stage}")
    for stage in extra:
        problems.append(f"evidence:stage-unknown:{stage}")
    for stage in REQUIRED_STAGES:
        record = stages.get(stage)
        if not isinstance(record, dict):
            continue
        if record.get("stage") != stage:
            problems.append(f"evidence:{stage}:stage-mismatch")
        if record.get("verdict") != "PASS":
            problems.append(f"evidence:{stage}:not-pass")
        if record.get("source_version") != source_version:
            problems.append(f"evidence:{stage}:source-version-mismatch")
        if not _sha256(record.get("artifact_sha256")):
            problems.append(f"evidence:{stage}:artifact-sha256-invalid")
        if not _sha256(record.get("audit_sha256")):
            problems.append(f"evidence:{stage}:audit-sha256-invalid")
        if not _nonempty_string(record.get("engine")):
            problems.append(f"evidence:{stage}:engine-missing")
        if not _nonempty_string(record.get("model")):
            problems.append(f"evidence:{stage}:model-missing")
        if not _nonempty_string(record.get("generated_at_utc")):
            problems.append(f"evidence:{stage}:generated-at-missing")
    return problems


def verify_fresh(
    root: Path,
    candidate_tag: str,
    evaluation: dict[str, Any],
    artifacts_dir: Path,
) -> tuple[list[str], dict[str, Any]]:
    """Every required stage must be hash-bound to this exact candidate."""
    problems: list[str] = []
    stage_results: dict[str, str] = {}
    candidate_commit = commit_of(root, candidate_tag)
    behavior = aggregate_fingerprint(fingerprint_paths(root, candidate_commit, ("behavior",)))
    harness = aggregate_fingerprint(fingerprint_paths(root, candidate_commit, ("harness",)))
    if evaluation.get("candidate_commit") != candidate_commit:
        problems.append("fresh:candidate-commit-mismatch")
    if evaluation.get("candidate_skill_behavior_sha256") != behavior:
        problems.append("fresh:behavior-fingerprint-mismatch")
    if evaluation.get("candidate_evaluation_harness_sha256") != harness:
        problems.append("fresh:harness-fingerprint-mismatch")
    stages = evaluation.get("stages")
    if not isinstance(stages, dict):
        stages = {}
    for stage in REQUIRED_STAGES:
        attestation = stages.get(stage)
        if not isinstance(attestation, dict):
            problems.append(f"fresh:{stage}:attestation-missing")
            stage_results[stage] = "missing-attestation"
            continue
        artifact_name = attestation.get("artifact_path")
        if not isinstance(artifact_name, str) or Path(artifact_name).name != artifact_name:
            problems.append(f"fresh:{stage}:artifact-path-invalid")
            stage_results[stage] = "invalid-path"
            continue
        artifact_path = artifacts_dir / artifact_name
        try:
            report = load_evaluation_artifact(artifact_path)
        except ValueError as exc:
            problems.append(f"fresh:{exc}")
            stage_results[stage] = "missing"
            continue
        digest = sha256_bytes(artifact_path.read_bytes())
        required_fields = {
            "schema_version": 1,
            "stage": stage,
            "candidate_tag": candidate_tag,
            "candidate_commit": candidate_commit,
            "verdict": "PASS",
            "skill_behavior_sha256": behavior,
            "evaluation_harness_sha256": harness,
        }
        for field, expected in required_fields.items():
            if report.get(field) != expected:
                problems.append(f"fresh:{stage}:{field}-mismatch")
        if digest != attestation.get("artifact_sha256"):
            problems.append(f"fresh:{stage}:artifact-sha256-mismatch")
        for field in ("engine", "model", "generated_at_utc"):
            if not _nonempty_string(report.get(field)):
                problems.append(f"fresh:{stage}:{field}-missing")
        stage_results[stage] = "PASS" if not any(f"fresh:{stage}:" in p for p in problems) else "FAIL"
    return problems, {
        "fresh_stage_results": stage_results,
        "artifacts_dir": str(artifacts_dir),
        "candidate_commit": candidate_commit[:12],
        "skill_behavior_sha256": behavior,
        "evaluation_harness_sha256": harness,
    }


def verify_reuse(
    root: Path,
    candidate_tag: str,
    evaluation: dict[str, Any],
    baseline_tag: str,
) -> tuple[list[str], dict[str, Any]]:
    """Validate a patch-level reuse declaration end to end."""
    detail: dict[str, Any] = {}
    reuse = evaluation.get("reuse")
    if not isinstance(reuse, dict):
        return (["reuse:declaration-missing"], detail)
    reused_from = reuse.get("source_tag")
    if not isinstance(reused_from, str) or not is_release_tag(reused_from):
        return ([f"reuse:invalid-reused-from:{reused_from!r}"], detail)
    if reused_from == candidate_tag:
        return (["reuse:reused-from-equals-candidate"], detail)
    tags = release_tags(root)
    if reused_from not in tags:
        return ([f"reuse:reused-from-tag-not-found:{reused_from}"], detail)
    if baseline_tag not in tags or tags.index(reused_from) >= tags.index(candidate_tag):
        return ([f"reuse:reused-from-not-before-candidate:{reused_from}"], detail)
    bump = semver_bump(baseline_tag, candidate_tag)
    if bump is None:
        return ([f"reuse:candidate-not-a-bump-of:{baseline_tag}"], detail)
    if bump != "patch":
        return ([f"reuse:forbidden-for-{bump}-release"], detail)

    reason = reuse.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return (["reuse:missing-reuse-reason"], detail)

    candidate_commit = commit_of(root, candidate_tag)
    reused_commit = commit_of(root, reused_from)
    if reuse.get("source_commit") != reused_commit:
        problems = ["reuse:source-commit-mismatch"]
    else:
        problems = []
    detail["reused_from"] = reused_from
    detail["reused_from_commit"] = reused_commit[:12]
    detail["candidate_commit"] = candidate_commit[:12]

    # Sensitive inputs: ANY behavior or harness file whose content differs
    # between the reused release and the candidate forbids reuse.
    behavior_cand = fingerprint_paths(root, candidate_commit, ("behavior",))
    behavior_old = fingerprint_paths(root, reused_commit, ("behavior",))
    harness_cand = fingerprint_paths(root, candidate_commit, ("harness",))
    harness_old = fingerprint_paths(root, reused_commit, ("harness",))
    behavior_cand_sha = aggregate_fingerprint(behavior_cand)
    behavior_old_sha = aggregate_fingerprint(behavior_old)
    harness_cand_sha = aggregate_fingerprint(harness_cand)
    harness_old_sha = aggregate_fingerprint(harness_old)
    if reuse.get("source_skill_behavior_sha256") != behavior_old_sha:
        problems.append("reuse:source-behavior-fingerprint-mismatch")
    if reuse.get("source_evaluation_harness_sha256") != harness_old_sha:
        problems.append("reuse:source-harness-fingerprint-mismatch")
    if evaluation.get("candidate_skill_behavior_sha256") != behavior_cand_sha:
        problems.append("reuse:candidate-behavior-fingerprint-mismatch")
    if evaluation.get("candidate_evaluation_harness_sha256") != harness_cand_sha:
        problems.append("reuse:candidate-harness-fingerprint-mismatch")
    problems.extend(validate_stage_attestations(reuse.get("stages"), reused_from.lstrip("v")))
    changed_behavior = sorted(
        path
        for path in set(behavior_cand) | set(behavior_old)
        if behavior_cand.get(path) != behavior_old.get(path)
        and not _is_frontmatter_metadata_diff(root, reused_commit, candidate_commit, path)
    )
    changed_harness = sorted(
        path
        for path in set(harness_cand) | set(harness_old)
        if harness_cand.get(path) != harness_old.get(path)
    )
    for path in changed_behavior:
        problems.append(f"reuse:behavior-changed:{path}")
    for path in changed_harness:
        problems.append(f"reuse:harness-changed:{path}")
    detail["skill_behavior_sha256"] = behavior_cand_sha
    detail["evaluation_harness_sha256"] = harness_cand_sha
    detail["changed_behavior_files"] = changed_behavior
    detail["changed_harness_files"] = changed_harness
    if not changed_behavior and not changed_harness:
        detail["verdict"] = "PASS"
    else:
        detail["verdict"] = "FAIL"
    return (problems, detail)


def verify(
    root: Path,
    candidate_tag: str,
    baseline_tag: str,
    required_level: str,
    evaluation_path: Path,
    trusted_public_key: Path | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "gate": "evaluation",
        "candidate_tag": candidate_tag,
        "baseline_tag": baseline_tag,
        "required_level": required_level,
        "generated_at_utc": utc_now(),
    }
    try:
        evaluation = load_evaluation_artifact(evaluation_path)
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        report["verdict"] = "FAIL"
        report["problems"] = [f"evaluation-gate-input:{exc}"]
        return report
    problems: list[str] = []
    if evaluation.get("schema_version") != 2:
        problems.append("evaluation-gate-input:schema-version-invalid")
    if evaluation.get("candidate_tag") != candidate_tag:
        problems.append("evaluation-gate-input:candidate-tag-mismatch")
    if not _nonempty_string(evaluation.get("engine")):
        problems.append("evaluation-gate-input:engine-missing")
    if not _nonempty_string(evaluation.get("model")):
        problems.append("evaluation-gate-input:model-missing")
    if not _nonempty_string(evaluation.get("generated_at_utc")):
        problems.append("evaluation-gate-input:generated-at-missing")
    key_path = trusted_public_key or root / ".github" / "release-evidence" / "trusted-signers.pem"
    try:
        signer_key_id = verify_signed_document(
            evaluation,
            key_path,
            expected_key_id=TRUSTED_SIGNER_KEY_ID,
        )
    except SignatureError as exc:
        problems.append(f"evaluation-gate-input:{exc}")
        signer_key_id = None
    if problems:
        report.update({
            "verdict": "FAIL",
            "problems": problems,
            "mode": evaluation.get("mode"),
            "signer_key_id": signer_key_id,
        })
        return report
    report["mode"] = evaluation.get("mode")
    report["engine"] = evaluation.get("engine")
    report["model"] = evaluation.get("model")

    mode = evaluation.get("mode")
    if required_level in ("minor", "major") and mode != "fresh":
        problems = [f"evaluation-gate-input:{required_level}-requires-fresh"]
        detail = {}
    elif mode == "fresh":
        # Fresh evidence only: patch-style reuse is forbidden for minor/major
        # (audit P1-01: minor/major must provide current-version PASS artifacts).
        problems, detail = verify_fresh(root, candidate_tag, evaluation, evaluation_path.parent)
        report["mode"] = "fresh"
        report["executed_stages"] = list(REQUIRED_STAGES)
        report["reused_stages"] = []
        report["reuse_forbidden_reason"] = (
            f"minor/major releases require fresh tier2/tier3/judge/signer evidence; "
            f"required_level={required_level}"
        )
    elif mode == "reuse":
        problems, detail = verify_reuse(root, candidate_tag, evaluation, baseline_tag)
        report["reused_stages"] = list(REQUIRED_STAGES) if not problems else []
        report["executed_stages"] = []
    else:
        problems, detail = (["evaluation-gate-input:mode-invalid"], {})
        report["executed_stages"] = []
        report["reused_stages"] = []
    report.update(detail)
    report["problems"] = problems
    report["signer_key_id"] = signer_key_id
    report["verdict"] = "PASS" if not problems else "FAIL"
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path("."), help="Repository root")
    parser.add_argument("--candidate-tag", required=True, help="Tag being released, e.g. v3.2.0")
    parser.add_argument("--baseline-tag", required=True, help="Preceding release tag, e.g. v3.1.9")
    parser.add_argument("--required-level", choices=("patch", "minor", "major"), required=True)
    parser.add_argument("--evaluation-gate", type=Path, required=True, help="Path to evaluation-gate.json")
    parser.add_argument("--trusted-public-key", type=Path, help="Trusted RSA public key PEM")
    parser.add_argument("--output", type=Path, help="Write the verification report here")
    args = parser.parse_args(argv)
    try:
        report = verify(
            args.root.resolve(),
            args.candidate_tag,
            args.baseline_tag,
            args.required_level,
            args.evaluation_gate,
            args.trusted_public_key,
        )
    except ValueError as exc:
        report = {
            "gate": "evaluation",
            "candidate_tag": args.candidate_tag,
            "verdict": "FAIL",
            "problems": [f"evaluation-gate-error:{exc}"],
            "generated_at_utc": utc_now(),
        }
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
