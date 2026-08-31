#!/usr/bin/env python3
"""Validate the public structure and links of the skill suite."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Sequence

from check_i18n_readme_structure import check_i18n_readme_structure


REQUIRED_FILES = (
    "README.md",
    "README.en.md",
    "README.zh-Hant.md",
    "README.ja.md",
    "README.th.md",
    "README.id.md",
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    ".github/workflows/drift-watch.yml",
    ".github/release-evidence/trusted-signers.pem",
    ".github/dependabot.yml",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/skill_proposal.yml",
    ".github/ISSUE_TEMPLATE/platform_drift.yml",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "EVALUATIONS.md",
    "LICENSE",
    "CHANGELOG.md",
    "COMPATIBILITY.md",
    "assets/readme-cover.webp",
    "assets/readme-promo.mp4",
    "assets/wordpet-origin-case.png",
    "SKILL.md",
    "agents/openai.yaml",
    "references/routing-and-state-machine.md",
    "shared/engineering-guardrails.md",
    "shared/evidence-status-model.md",
    "shared/decision-and-confirmation-rules.md",
    "shared/redaction-policy.md",
    "shared/documentation-boundaries.md",
    "shared/architecture-layers.md",
    "foundation/SKILL.md",
    "foundation/VALIDATE.md",
    "foundation/guardrails/evidence-status-model.md",
    "foundation/guardrails/engineering-guardrails.md",
    "foundation/guardrails/decision-and-confirmation-rules.md",
    "foundation/guardrails/redaction-policy.md",
    "foundation/templates/project-intake.md",
    "foundation/templates/implementation-plan.md",
    "foundation/templates/verification-report.md",
    "foundation/templates/release-checklist.md",
    "scripts/check_foundation_equivalence.py",
    "scripts/release_gate.sh",
    "shared/templates/project-intake.md",
    "shared/templates/implementation-plan.md",
    "shared/templates/verification-report.md",
    "shared/templates/release-checklist.md",
    "skills/mini-program-project-intake-skill/SKILL.md",
    "skills/mini-program-project-intake-skill/agents/openai.yaml",
    "skills/mini-program-project-intake-skill/references/intake-workflow.md",
    "skills/mini-program-project-intake-skill/assets/project-fact-map.md",
    "skills/mini-program-product-spec-skill/SKILL.md",
    "skills/mini-program-product-spec-skill/agents/openai.yaml",
    "skills/mini-program-product-spec-skill/references/specification-workflow.md",
    "skills/mini-program-product-spec-skill/assets/product-specification.md",
    "skills/mini-program-architecture-skill/SKILL.md",
    "skills/mini-program-architecture-skill/agents/openai.yaml",
    "skills/mini-program-architecture-skill/references/architecture-workflow.md",
    "skills/mini-program-architecture-skill/assets/architecture-decision-record.md",
    "skills/wechat-mini-program-platform-skill/SKILL.md",
    "skills/wechat-mini-program-platform-skill/agents/openai.yaml",
    "platforms/README.md",
    "platforms/wechat/platform-evidence-layers.md",
    "platforms/wechat/wechat-platform-checklist.md",
    "platforms/wechat/privacy-permission-matrix.md",
    "platforms/wechat/facts.md",
    "platforms/wechat/rule-map.json",
    "platforms/alipay/facts.md",
    "platforms/alipay/rule-map.json",
    "platforms/douyin/facts.md",
    "platforms/douyin/rule-map.json",
    "skills/mini-program-implementation-skill/SKILL.md",
    "skills/mini-program-implementation-skill/agents/openai.yaml",
    "skills/mini-program-implementation-skill/references/implementation-workflow.md",
    "skills/mini-program-implementation-skill/assets/implementation-handoff.md",
    "skills/mini-program-ui-device-skill/SKILL.md",
    "skills/mini-program-ui-device-skill/agents/openai.yaml",
    "skills/mini-program-ui-device-skill/references/ui-device-workflow.md",
    "skills/mini-program-ui-device-skill/assets/ui-device-evidence-record.md",
    "skills/mini-program-ui-device-skill/assets/asset-lineage-record.md",
    "skills/mini-program-ui-device-skill/assets/accessibility-matrix.md",
    "skills/mini-program-debugging-skill/SKILL.md",
    "skills/mini-program-debugging-skill/agents/openai.yaml",
    "skills/mini-program-debugging-skill/references/debugging-workflow.md",
    "skills/mini-program-debugging-skill/references/interruption-recovery-protocol.md",
    "skills/mini-program-debugging-skill/assets/debugging-report.md",
    "skills/mini-program-verification-skill/SKILL.md",
    "skills/mini-program-verification-skill/agents/openai.yaml",
    "skills/mini-program-verification-skill/references/verification-workflow.md",
    "skills/mini-program-verification-skill/references/evidence-admissibility.md",
    "skills/mini-program-verification-skill/references/verification-capability-matrix.md",
    "skills/mini-program-verification-skill/assets/verification-evidence-report.md",
    "skills/mini-program-verification-skill/assets/quality-evidence-matrix.md",
    "skills/mini-program-release-skill/SKILL.md",
    "skills/mini-program-release-skill/agents/openai.yaml",
    "skills/mini-program-release-skill/references/release-governance-workflow.md",
    "skills/mini-program-release-skill/assets/release-readiness-record.md",
    "VERSION",
    "install.sh",
    "scripts/check_i18n_readme_structure.py",
    "scripts/agent_cli.py",
    "scripts/platform_drift.py",
    "scripts/drift_watch.py",
    "scripts/drift_audit.py",
    "scripts/review_drift_proposal.py",
    "scripts/release_recommendation.py",
    "scripts/evaluation_gate.py",
    "scripts/evidence_signature.py",
    "scripts/summarize_evaluations.py",
    "scripts/export_public_package.py",
    "scripts/capability_doctor.py",
    "scripts/scan_sensitive_content.py",
    "scripts/verify_public_package.py",
    "scripts/validate_suite.py",
)
EXCLUDED_PARTS = {".git", ".planning", "__pycache__", "tests"}
# Repo-only assets: tracked in git, scanned like every other file (binary
# payloads get the latin-1 full scan since 1.4), but not part of the public
# package (design sources for shipped assets).
REPO_ONLY_ASSETS = ("assets/readme-cover-2000x849-v2.webp",)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
DURATION_CLAIM = re.compile(r"(?<!\d)(\d{1,3})\s*(?:[-‑–—]\s*)?(秒|seconds?|วินาที|detik)", re.IGNORECASE)
PROMO_VIDEO_CONTEXT = re.compile(
    r"readme-promo\.mp4|说明视频|說明影片|説明動画|explainer video|video penjelasan|วิดีโอ|"
    r"看懂这套技能|看懂這套技能|概要を見る|Understand the Skill in|เข้าใจ Skill นี้ใน|Pahami Skill Ini dalam",
    re.IGNORECASE,
)
PACKAGE_VERSION_REFERENCE = re.compile(r"mini-program-engineering-suite-v(\d+\.\d+\.\d+)")


def parse_frontmatter(path: Path) -> tuple[dict[str, str], list[str]]:
    """Parse and validate the flat official Codex frontmatter contract."""
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return {}, [f"{path}: missing YAML frontmatter delimiters"]
    block = text.split("---\n", 2)[1]
    result: dict[str, str] = {}
    current_key: str | None = None
    for line in block.splitlines():
        if line.startswith("  ") and current_key:
            result[current_key] = f"{result[current_key]} {line.strip()}".strip()
            continue
        if ":" not in line:
            errors.append(f"{path}: unsupported frontmatter line: {line}")
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        result[current_key] = value.strip().removesuffix(">-").strip()
    return result, errors


def validate_skill(path: Path, expected_name: str, *, root_skill: bool = False) -> list[str]:
    """Validate one SKILL.md against the official minimal contract."""
    errors: list[str] = []
    frontmatter, parse_errors = parse_frontmatter(path)
    errors.extend(parse_errors)
    expected_keys = {"name", "description", "license", "compatibility", "metadata"} if root_skill else {
        "name",
        "description",
    }
    if set(frontmatter) != expected_keys:
        errors.append(f"{path}: frontmatter keys do not match the supported contract")
    if frontmatter.get("name") != expected_name:
        errors.append(f"{path}: name must be {expected_name}")
    description = frontmatter.get("description", "")
    if not 80 <= len(description) <= 1024:
        errors.append(f"{path}: description length must be between 80 and 1024 characters")
    if root_skill:
        if frontmatter.get("license") != "MIT":
            errors.append(f"{path}: root license must be MIT")
        compatibility = frontmatter.get("compatibility", "")
        if not 10 <= len(compatibility) <= 500:
            errors.append(f"{path}: compatibility length must be between 10 and 500 characters")
        version = (path.parent / "VERSION").read_text(encoding="utf-8").strip()
        content_block = path.read_text(encoding="utf-8").split("---\n", 2)[1]
        if f'version: "{version}"' not in content_block:
            errors.append(f"{path}: metadata version must match VERSION")
    content = path.read_text(encoding="utf-8")
    if "TODO" in content:
        errors.append(f"{path}: unresolved TODO placeholder")
    if len(content.splitlines()) >= 500:
        errors.append(f"{path}: SKILL.md must stay below 500 lines")
    return errors


def heading_slug(heading: str) -> str:
    """Render a GitHub-style anchor slug for one Markdown heading."""
    text = re.sub(r"[*_`\[\]]", "", heading)
    text = text.strip().lower()
    text = re.sub(r"[^\w\u4e00-\u9fff\u3040-\u30ff\u0e00-\u0e7f-]+", "-", text)
    return text.strip("-")


def validate_links(root: Path) -> list[str]:
    """Check relative Markdown links and cross-file anchors in public package files.

    Cross-file anchors (`path/to/file.md#section`) are resolved against the
    target file's own headings. Previously only same-file anchors were
    checked, so renaming a section in one file silently broke anchors that
    pointed at it from every other file (audit finding).
    """
    errors: list[str] = []
    markdown_files = [
        path.resolve()
        for path in sorted(root.rglob("*.md"))
        if not any(part in EXCLUDED_PARTS for part in path.parts)
    ]
    # Pre-compute heading slugs per file (keys resolved the same way the link
    # targets are, so /tmp-vs-/private/tmp style symlink aliases cannot split
    # one file into two identities) for cross-file anchor checking.
    slugs_by_file: dict[Path, set[str]] = {}
    for path in markdown_files:
        content = path.read_text(encoding="utf-8")
        slugs_by_file[path] = {
            heading_slug(m.group(1)) for m in re.finditer(r"^#+\s+(.+)$", content, re.MULTILINE)
        }
    for path in markdown_files:
        for target in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            clean_target, _, anchor = target.partition("#")
            if clean_target:
                target_path = (path.parent / clean_target).resolve()
                if not target_path.exists():
                    errors.append(f"{path}: broken link {target}")
                    continue
                if anchor and target_path in slugs_by_file and anchor not in slugs_by_file[target_path]:
                    errors.append(f"{path}: broken cross-file anchor {target}")
                continue
            if anchor and anchor not in slugs_by_file[path]:
                errors.append(f"{path}: broken same-file anchor #{anchor}")
    return errors


def validate_openai_yaml(path: Path, skill_name: str) -> list[str]:
    """Check required UI metadata without adding a YAML dependency."""
    if not path.is_file():
        return [f"{path}: missing"]
    content = path.read_text(encoding="utf-8")
    errors = []
    for key in ("display_name:", "short_description:", "default_prompt:"):
        if key not in content:
            errors.append(f"{path}: missing {key.removesuffix(':')}")
    if f"${skill_name}" not in content:
        errors.append(f"{path}: default_prompt must mention ${skill_name}")
    return errors


def validate_version_consistency(root: Path) -> list[str]:
    """Check public version facts that must move together."""
    errors: list[str] = []
    version_path = root / "VERSION"
    if not version_path.is_file():
        return ["missing required file: VERSION"]
    version = version_path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        errors.append(f"{version_path}: VERSION must use MAJOR.MINOR.PATCH")

    changelog_path = root / "CHANGELOG.md"
    if changelog_path.is_file():
        changelog = changelog_path.read_text(encoding="utf-8")
        if f"## {version} - " not in changelog:
            errors.append(f"{changelog_path}: CHANGELOG must include current VERSION")

    readme_files = (
        "README.md",
        "README.en.md",
        "README.zh-Hant.md",
        "README.ja.md",
        "README.th.md",
        "README.id.md",
    )
    badge = f"version-{version}-0EA5E9.svg"
    alt = f"Version: {version}"
    for readme_name in readme_files:
        readme_path = root / readme_name
        if not readme_path.is_file():
            continue
        readme = readme_path.read_text(encoding="utf-8")
        if badge not in readme:
            errors.append(f"{readme_path}: version badge must match VERSION")
        if alt not in readme:
            errors.append(f"{readme_path}: version badge alt text must match VERSION")
        if version not in readme:
            errors.append(f"{readme_path}: README body must mention current VERSION")
        for package_version in PACKAGE_VERSION_REFERENCE.findall(readme):
            if package_version != version:
                errors.append(
                    f"{readme_path}: release package example version {package_version} "
                    f"must match VERSION {version}"
                )
    return errors


def validate_platform_rule_maps(root: Path) -> list[str]:
    """Validate platforms/*/rule-map.json against the freshness-protocol schema."""
    errors: list[str] = []
    for path in sorted(root.glob("platforms/*/rule-map.json")):
        platform = path.parent.name
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append(f"{path}: unreadable rule map")
            continue
        if not isinstance(data, dict) or data.get("format_version") != 1:
            errors.append(f"{path}: format_version must be 1")
            continue
        if data.get("platform") != platform:
            errors.append(f"{path}: platform must match directory name {platform}")
        domains = data.get("allowed_domains")
        domains_ok = (
            isinstance(domains, list)
            and bool(domains)
            and all(isinstance(x, str) and x and "://" not in x and "/" not in x for x in domains)
        )
        if not domains_ok:
            errors.append(f"{path}: allowed_domains must be non-empty domain strings")
        rules = data.get("rules")
        if not isinstance(rules, list) or not rules:
            errors.append(f"{path}: rules must be a non-empty list")
            continue
        seen_rule_ids: set[str] = set()
        for rule in rules:
            if not isinstance(rule, dict):
                errors.append(f"{path}: rule must be an object")
                continue
            rule_id = rule.get("id")
            if not isinstance(rule_id, str) or not rule_id:
                errors.append(f"{path}: rule missing string id")
                continue
            if rule_id in seen_rule_ids:
                errors.append(f"{path}: duplicate rule id {rule_id}")
            seen_rule_ids.add(rule_id)
            ttl = rule.get("ttl_days")
            if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl < 0:
                errors.append(f"{path}: {rule_id} ttl_days must be a non-negative integer")
            official = rule.get("official")
            url = official.get("url") if isinstance(official, dict) else None
            if not isinstance(url, str) or not url.startswith("https://"):
                errors.append(f"{path}: {rule_id} official.url must be https")
            elif domains_ok:
                parts = url.split("/")
                if len(parts) > 2 and parts[2] not in domains:
                    errors.append(f"{path}: {rule_id} url domain not in allowed_domains")
            title = official.get("title") if isinstance(official, dict) else None
            if not isinstance(title, str) or not title:
                errors.append(f"{path}: {rule_id} official.title must be a non-empty string")
            points = rule.get("verify_points")
            if not isinstance(points, list) or not points or not all(isinstance(p, str) and p for p in points):
                errors.append(f"{path}: {rule_id} verify_points must be non-empty strings")
            elif len(set(points)) != len(points):
                errors.append(f"{path}: {rule_id} verify_points contains duplicates")
        validate_facts_rule_map_binding(path, data, errors)
    return errors


FACT_ANNOTATION_LINE = re.compile(
    r"<!--\s*fact:\s*(?P<id>[^\s]+)\s+verified=(?P<verified>[^\s]+)\s+source=(?P<source>\S+)\s+digest=(?P<digest>\S+)\s*-->"
)


def validate_facts_rule_map_binding(path: Path, rule_map: dict[str, object], errors: list[str]) -> None:
    """Cross-bind facts.md annotations to rule-map rules by fact.id == rule.id.

    URL-derived linkage is what let a stale annotation (privacy note still
    pointing at the old review page) silently re-route rule associations
    (codex sixth audit): binding by ID first, then requiring the fact's
    source to equal the rule's official.url, catches that at validation time.
    """
    facts_path = path.parent / "facts.md"
    rules = rule_map.get("rules") if isinstance(rule_map.get("rules"), list) else []
    if not facts_path.is_file():
        for rule in rules:
            if isinstance(rule, dict) and isinstance(rule.get("id"), str):
                errors.append(f"{facts_path}: missing; rule {rule['id']} has no facts file")
        return
    seen: dict[str, str] = {}
    for m in FACT_ANNOTATION_LINE.finditer(facts_path.read_text(encoding="utf-8")):
        fid, source = m.group("id"), m.group("source")
        if fid in seen:
            errors.append(f"{facts_path}: duplicate fact id {fid}")
        seen[fid] = source
    rule_ids = set()
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("id"), str):
            continue
        rid = rule["id"]
        rule_ids.add(rid)
        official = rule.get("official")
        url = official.get("url") if isinstance(official, dict) else None
        if rid not in seen:
            errors.append(f"{facts_path}: rule {rid} has no matching fact annotation")
        elif url is not None and seen[rid] != url:
            errors.append(f"{facts_path}: fact {rid} source != rule-map official.url ({seen[rid]} != {url})")
    for fid in seen:
        if fid not in rule_ids:
            errors.append(f"{facts_path}: orphan fact {fid} has no rule with the same id")


def read_mp4_duration_seconds(path: Path) -> float | None:
    """Read the MP4 mvhd duration without external media tools."""
    data = path.read_bytes()
    marker = data.find(b"mvhd")
    if marker < 0:
        return None
    version = data[marker + 4]
    if version == 0:
        if marker + 24 > len(data):
            return None
        timescale = int.from_bytes(data[marker + 16 : marker + 20], "big")
        duration = int.from_bytes(data[marker + 20 : marker + 24], "big")
    elif version == 1:
        if marker + 36 > len(data):
            return None
        timescale = int.from_bytes(data[marker + 24 : marker + 28], "big")
        duration = int.from_bytes(data[marker + 28 : marker + 36], "big")
    else:
        return None
    if timescale <= 0:
        return None
    return duration / timescale


def find_promo_duration_claims(text: str) -> list[int]:
    """Return duration claims only from README lines that describe the promo video."""
    claims: list[int] = []
    for line in text.splitlines():
        if PROMO_VIDEO_CONTEXT.search(line):
            claims.extend(int(match.group(1)) for match in DURATION_CLAIM.finditer(line))
    return claims


def validate_public_media_copy(root: Path) -> list[str]:
    """Check public README claims against bundled media facts."""
    errors: list[str] = []
    promo = root / "assets" / "readme-promo.mp4"
    if not promo.is_file():
        return errors
    duration = read_mp4_duration_seconds(promo)
    if duration is None:
        errors.append(f"{promo}: unable to read MP4 duration metadata")
        return errors
    expected_seconds = round(duration)

    for readme_name in (
        "README.md",
        "README.en.md",
        "README.zh-Hant.md",
        "README.ja.md",
        "README.th.md",
        "README.id.md",
    ):
        readme_path = root / readme_name
        if not readme_path.is_file():
            continue
        text = readme_path.read_text(encoding="utf-8")
        claims = find_promo_duration_claims(text)
        if not claims:
            errors.append(f"{readme_path}: README promo video duration copy is missing")
            continue
        for claim in claims:
            if claim != expected_seconds:
                errors.append(
                    f"{readme_path}: README promo video duration says {claim}, "
                    f"but assets/readme-promo.mp4 is {expected_seconds} seconds"
                )
    return errors


def discover_child_names(root: Path) -> tuple[str, ...]:
    """Enumerate child skills from the filesystem as the single source of truth."""
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return ()
    return tuple(sorted(p.name for p in skills_dir.iterdir() if (p / "SKILL.md").is_file()))


def validate(root: Path) -> dict[str, object]:
    """Return a machine-readable validation report."""
    errors: list[str] = []
    for relative_path in REQUIRED_FILES:
        if not (root / relative_path).is_file():
            errors.append(f"missing required file: {relative_path}")
    # Repo-only assets exist in the source repository, not in exported packages;
    # requiring them inside validate() would fail every clean export.
    if (root / ".git").exists() or (root / "platforms").is_dir() and (root / "tests").is_dir():
        for relative_path in REPO_ONLY_ASSETS:
            if not (root / relative_path).is_file():
                errors.append(f"missing repo-only asset: {relative_path}")

    root_skill = root / "SKILL.md"
    child_names = discover_child_names(root)
    if root_skill.is_file():
        errors.extend(validate_skill(root_skill, "mini-program-engineering-suite", root_skill=True))
        root_text = root_skill.read_text(encoding="utf-8")
        for child_name in child_names:
            if f"skills/{child_name}/SKILL.md" not in root_text:
                errors.append(f"root skill missing route: {child_name}")
    i18n_report = check_i18n_readme_structure(root)
    errors.extend(str(error) for error in i18n_report["errors"])
    errors.extend(validate_platform_rule_maps(root))
    foundation_report = __import__("check_foundation_equivalence").check(root)
    errors.extend(str(problem) for problem in foundation_report["problems"])
    errors.extend(validate_version_consistency(root))
    errors.extend(validate_public_media_copy(root))
    errors.extend(validate_openai_yaml(root / "agents/openai.yaml", "mini-program-engineering-suite"))
    for child_name in child_names:
        child_root = root / "skills" / child_name
        child_skill = child_root / "SKILL.md"
        if child_skill.is_file():
            errors.extend(validate_skill(child_skill, child_name))
        errors.extend(validate_openai_yaml(child_root / "agents/openai.yaml", child_name))
    errors.extend(validate_links(root))

    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if path.suffix.lower() in {".md", ".yaml", ".yml", ".json"} and "TODO" in path.read_text(encoding="utf-8"):
            errors.append(f"{path}: unresolved TODO placeholder")

    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "checked_files": len(REQUIRED_FILES),
        "skill_count": len(child_names),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Validate one suite directory and emit JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Suite root")
    args = parser.parse_args(argv)
    root = args.path.resolve()
    if not root.is_dir():
        print(json.dumps({"valid": False, "errors": ["suite path is not a directory"]}))
        return 2
    report = validate(root)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
