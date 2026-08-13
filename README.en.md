**[English](#)** | [中文](./README.md)

---

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
  <img src="https://img.shields.io/badge/runtime-Python%203.8%2B-3776AB.svg" alt="Runtime: Python 3.8+">
  <img src="https://img.shields.io/badge/lang-English-2563EB.svg" alt="Language: English">
  <img src="https://img.shields.io/badge/status-Active%20Development-22C55E.svg" alt="Status: Active Development">
  <img src="https://img.shields.io/badge/version-1.1.0-0EA5E9.svg" alt="Version: 1.1.0">
</p>

**Mini Program Engineering Skill Suite** is an Agent Skill suite for evidence-first mini-program development. It helps an agent take a WeChat or other mini-program project from unclear intent to reliable engineering action: project intake, product specification, architecture, implementation, UI and device adaptation, debugging, verification, and release readiness.

中文名：**小程序开发工程技能套件**。

---

## Status

This repository is the public project home for the suite, released under the **MIT License**. Anyone may view, use, modify, and redistribute it. See [LICENSE](LICENSE) for the full terms.

---

## What It Solves

Mini-program development often fails in the gaps between stages: a preview is mistaken for acceptance, a local build is mistaken for a submitted package, or a pushed branch is mistaken for a released version. This suite makes those boundaries explicit.

It is designed to help an agent:

- understand an existing mini-program before editing it;
- turn vague product ideas into testable specifications;
- map stable product decisions into architecture, data, API, permission, and failure-handling choices;
- implement scoped changes while preserving existing work;
- treat UI preview, user confirmation, integration, device checks, and final acceptance as separate events;
- diagnose issues from evidence instead of guessing;
- report verification and release readiness without overstating what has been proven.

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

Current working version: **1.1.0**.

---

## License

This project is released under the **MIT License**. See [LICENSE](LICENSE) for details. You are free to use, modify, distribute, and commercially use it, provided you retain the copyright notice and permission notice.
