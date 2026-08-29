# Contributing

Thank you for helping improve Mini Program Engineering Skill Suite.

This repository contains a public Agent Skill suite for evidence-first mini-program engineering. Contributions should improve reusable engineering guidance, validation, redaction, documentation, or maintenance quality without depending on a private source project.

## Development principles

- Keep the suite generic: do not add private project code, AppIDs, cloud resources, business data, review status, or local user paths.
- Preserve fail-closed behavior: unknown public-package files must be reviewed and added to the explicit allowlist before export.
- Keep version facts together: when the version changes, update `VERSION`, root `SKILL.md` metadata, README version text/badges, `CHANGELOG.md`, tests, and public-package manifests together.
- Use evidence-calibrated language: do not claim device verification, platform approval, or production release without matching evidence.

## Local verification

Run these checks before submitting changes:

```bash
python3 -m unittest discover -s tests -q
python3 scripts/validate_suite.py .
python3 scripts/scan_sensitive_content.py . --format json
```

For release-facing changes, also run a deterministic export and package verification:

```bash
export_dir="$(mktemp -d)"
python3 scripts/export_public_package.py . --output "$export_dir/package"
python3 "$export_dir/package/scripts/verify_public_package.py" "$export_dir/package"
```

## Pull request checklist

- [ ] The change is useful for general mini-program engineering, not only one private project.
- [ ] Public documentation is clear and does not expose private context.
- [ ] New public files are added to `scripts/validate_suite.py` intentionally.
- [ ] Relevant tests or validation rules were added or updated.
- [ ] All local verification commands passed.
