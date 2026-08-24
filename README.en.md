<p align="center">
  <img src="assets/readme-cover.png" alt="Mini Program Engineering Skill Suite cover" width="100%">
</p>

# Mini Program Engineering Skill Suite

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/platform-WeChat%20Mini%20Program-07C160.svg" alt="Platform: WeChat Mini Program">
  <img src="https://img.shields.io/badge/type-Agent%20Skill%20Suite-7B61FF.svg" alt="Type: Agent Skill Suite">
  <img src="https://img.shields.io/badge/category-Evidence--First%20Engineering-FF6B35.svg" alt="Category: Evidence-First Engineering">
  <img src="https://img.shields.io/badge/stack-Taro%20%7C%20uni--app%20%7C%20native-4CAF50.svg" alt="Stack: Taro / uni-app / native">
  <img src="https://img.shields.io/badge/runtime-Python%203.9%2B-3776AB.svg" alt="Runtime: Python 3.9+">
  <img src="https://img.shields.io/badge/lang-English-2563EB.svg" alt="Language: English">
  <img src="https://img.shields.io/badge/status-Active%20Development-22C55E.svg" alt="Status: Active Development">
  <img src="https://img.shields.io/badge/version-1.1.1-0EA5E9.svg" alt="Version: 1.1.1">
</p>

<p align="center">
  <a href="./README.md">中文</a> ·
  <a href="./README.zh-Hant.md">繁體中文</a> ·
  <a href="./README.en.md">English</a> ·
  <a href="./README.ja.md">日本語</a> ·
  <a href="./README.th.md">ไทย</a> ·
  <a href="./README.id.md">Bahasa Indonesia</a>
</p>

**Mini Program Engineering Skill Suite** is an Agent Skill suite for zero-to-one mini-program development, existing project takeover, and release-readiness governance. It turns the hard parts of mini-program work into an executable agent workflow: clarifying what should be built, deciding how it should be built, proving what has been done, and keeping external actions explicitly authorized.

中文名：**小程序开发工程技能套件**。

---

## Understand the Skill in 30 Seconds

If you want a quick overview of what this Skill solves, where it came from, and how it is meant to be used, start with this [32-second explainer video](https://raw.githubusercontent.com/NocodeMrLi/mini-program-engineering-skill-suite/main/assets/readme-promo.mp4).

https://github.com/user-attachments/assets/73f542b6-f90d-4f1b-bb75-bb19db341dc5

<sub>The video only explains the suite positioning, origin, and usage boundaries.</sub>

---

## Status

This repository is the public project home for the suite, released under the **MIT License**. Anyone may view, use, modify, and redistribute it. See [LICENSE](LICENSE) for the full terms.

---

## What It Solves

Mini-program development is harder than it looks for people who have never shipped one before. The challenge is not just writing code; it is knowing what to confirm first, which decisions affect later work, when to stop and verify, and which release steps should never be skipped by assumption.

The suite helps an agent guide that process from zero to one, or take over an existing project without damaging accepted work:

- clarify product intent, users, scope, and acceptance criteria before building;
- turn vague ideas into testable specifications and engineering plans;
- map stable decisions into architecture, data, API, permission, and failure-handling choices;
- implement scoped changes while preserving existing work;
- check UI, device behavior, permissions, and release risks step by step;
- diagnose issues from evidence instead of guessing;
- report only what has actually been verified.

---

## Real Project Origin: WordPet

This Skill suite was not written from an abstract tutorial. It was distilled from long-running collaboration on the real WeChat mini program **WordPet（语宠精灵）**. What this repository preserves is the reusable engineering method: product decomposition, scoped implementation, verification, acceptance evidence, release readiness, and status discipline for mini-program work.

<p align="center">
  <img src="assets/wordpet-origin-case.png" alt="WordPet real project origin case: learning card, read practice, growth map, and mini program QR code" width="100%">
</p>

<sub>WordPet（语宠精灵）is shown only as the real-origin case behind the method. This repository publishes reusable mini-program engineering practices only. It does not include the app source code, AppID, cloud resources, private configuration, business data, review status, or internal development records. The QR code is provided only for experiencing the real case, and scan results depend on the current WeChat platform state.</sub>

---

## Component Map

| Area | Purpose |
| --- | --- |
| Project intake | Read-only project discovery, fact map, risk map, and change boundary |
| Product specification | MVP scope, user flow, state matrix, acceptance criteria |
| Architecture | Module, data, API, permission, and failure strategy decisions |
| Platform adaptation | WeChat mini-program tooling, privacy, permissions, and platform evidence |
| Implementation | Small scoped changes with tests and user-change protection |
| UI and device adaptation | Reference fidelity, preview-first changes, responsive/device checks |
| Debugging | Reproduction, competing hypotheses, root-cause isolation, regression coverage |
| Verification | Evidence tiers across static checks, unit tests, integration, simulator, device, cloud, and release layers |
| Release readiness | Version, build, security, privacy, rollback, upload/review/release evidence governance |

---

## Design Principles

- Facts before action: no edits before the current project state is understood.
- Evidence-calibrated status: report only the state that has actually been proven.
- Stage gates stay separate: preview, implementation, build, upload, review, acceptance, release, and rollback are not interchangeable.
- Authorization is explicit: external writes such as upload, review submission, release, cloud changes, and repository publishing require separate approval.
- Private information stays out: public packages must pass redaction and sensitive-content checks.
- Real devices still matter: local, static, and simulated checks cannot replace device, cloud, experience-version, or production evidence.

---

## Intended Use

The suite is intended for agents working with mini-program engineering tasks, especially when a project has accumulated product decisions, UI conventions, platform constraints, and release risk over time.

Typical use cases include:

- taking over an unfamiliar mini-program repository;
- planning a new mini-program from zero to one;
- implementing a feature without disturbing existing accepted work;
- checking whether a project is ready for upload, review, or release;
- turning repeated engineering judgment into reusable agent behavior.

---

## How To Use

### 1. Install Into An Agent App

Clone this repository into an application that supports `SKILL.md` or project rules. Exact discovery behavior depends on the app version, but these are the recommended locations:

If you do not want to run commands manually, paste this request into the agent app you are using. If the agent has network, Git, and local filesystem write access, it can usually choose the right install location and install the skill for you:

```text
https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git Install this skill for me.
```

If the agent cannot access your local filesystem, or if you want to control the exact install location, use the command-line examples below.

| App / runner | Recommended location | Invocation |
| --- | --- | --- |
| Codex CLI / universal Agent Skills | `~/.agents/skills/mini-program-engineering-suite` | `/mini-program-engineering-suite` |
| Claude Code | `~/.claude/skills/mini-program-engineering-suite` | `/mini-program-engineering-suite` |
| GitHub Copilot Coding Agent | `.github/skills/mini-program-engineering-suite` | Trigger through the repository task and Skill instructions |
| Cursor | `.cursor/rules/mini-program-engineering-suite` | Use as project rules / Skill instructions |
| Windsurf / Cline / Roo Code / Gemini CLI / Kiro / Trae / Goose / OpenCode | The app's skills or rules directory | Trigger through that app's Skill / Rules mechanism |

Universal install example:

```bash
git clone https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git \
  ~/.agents/skills/mini-program-engineering-suite
```

Claude Code example:

```bash
git clone https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git \
  ~/.claude/skills/mini-program-engineering-suite
```

GitHub Copilot project-level example:

```bash
mkdir -p .github/skills
git clone https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git \
  .github/skills/mini-program-engineering-suite
```

### 2. Invoke It In A New Session

After installation, open a new agent session and describe the task. You can explicitly call the root Skill:

```text
/mini-program-engineering-suite I want to build a WeChat mini program from zero to one. Please help me clarify scope and development steps first.
```

You can also describe a stage-specific task and let the agent route to the right component:

```text
Take over this mini-program project read-only first. Inspect the current state, but do not change code yet.
```

```text
This mini program is preparing for review. Run a release-readiness check, but do not upload or submit review.
```

### 3. Work In Stages

The recommended flow is product specification, architecture, implementation, UI/device adaptation, verification, and release readiness. At each stage, ask the agent to report:

- the current conclusion;
- the files, tests, screenshots, logs, or platform evidence behind it;
- what has not been verified yet;
- what needs your confirmation next.

For existing projects, start with read-only project intake before changing anything. External actions such as upload, review submission, release, cloud changes, and repository permission changes require separate authorization.

---

## What It Does Not Do

This suite does not automatically install project dependencies, create cloud resources, upload packages, submit review, publish releases, or modify production state. It can prepare evidence and instructions for those actions, but each external action remains separately authorized.

---

## Verification

The current suite version uses structural validation, sensitive-content scanning, deterministic public-package export, manifest verification, routing evaluation, behavior evaluation, and independent final judgment before being treated as frozen.

For a received package, integrity is checked through its `package-manifest.json`. For a source working copy, validation and sensitive scanning are run before distribution.

---

## Package Integrity

Use a 可信来源 (trusted source) for any distributed package, and do not mix files from different versions. `VERSION` is the version source of truth. A package that includes `package-manifest.json` can be checked by recomputing each file size and SHA-256 digest:

```bash
python3 <package-dir>/scripts/verify_public_package.py <package-dir>
```

The command confirms package integrity only; it does not prove publisher identity, device behavior, platform approval, or production release state. Keep the previous verified package and its manifest digest so rollback (回滚) remains possible if a later version regresses.

---

## Version

Current working version: **1.1.1**.

---

## License

This project is released under the **MIT License**. See [LICENSE](LICENSE) for details. You are free to use, modify, distribute, and commercially use it, provided you retain the copyright notice and permission notice.
