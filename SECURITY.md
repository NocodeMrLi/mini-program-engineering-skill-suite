# Security Policy

Mini Program Engineering Skill Suite treats package integrity, redaction, and evidence boundaries as part of the product.

## Two-layer secret scanning (maintainer setup)

Layer 1 is this repository's own `scripts/scan_sensitive_content.py`: it covers
WeChat AppIDs / cloud env IDs / personal paths AND generic credential shapes
(GitHub, AWS, Google, npm, PyPI, Slack, Tencent), runs in CI on every push,
and is exercised by a fake-credential negative probe so a rule regression
fails the build. Findings never echo matched text — only rule ids and
fingerprints.

Layer 2 is GitHub's own Secret Scanning with Push Protection. Maintainers must
keep these enabled for the repository (Settings → Code security and analysis):

- Secret scanning: **enabled**
- Push protection: **enabled**

A green CI plus enabled repo-level scanning is the acceptance bar; disabling
either layer is a security regression and must be reverted.

## Reporting a vulnerability

Please report issues through GitHub by opening a private security advisory when available, or by creating a minimal public issue that does not include secrets or private project details.

Do not paste real AppIDs, access tokens, cloud environment identifiers, private keys, personal paths, screenshots with private data, or production logs into public issues.

## What to report

Useful reports include:

- sensitive content that should have been blocked by `scripts/scan_sensitive_content.py`;
- public-package files that bypass the explicit allowlist;
- package manifest or SHA-256 verification weaknesses;
- documentation that could cause users to overstate review, release, device, or production evidence;
- examples that reveal private project identity or platform configuration.

## Supported version

Security fixes target the current version recorded in `VERSION`. Older tags remain available for traceability, but fixes are made on `main` first.

## Safe reproduction guidance

Use anonymous fixtures or synthetic examples. If a report requires a realistic example, replace identifiers with neutral placeholders and describe the pattern rather than the original secret.
