---
name: evidence-first-engineering
description: >-
  Apply evidence-first engineering discipline to any agent-built software project: fact discovery before action, evidence-calibrated status reporting, explicit change boundaries and stage gates, controlled confirmation for risky or external actions, sensitive-information redaction for anything shared publicly, and resumable continuity after interruptions. Use when users ask an agent to take over an existing codebase, deliver a feature across stages, verify whether work is actually complete, judge release readiness, or keep conclusions honest about what is proven versus assumed. This foundation skill is domain-neutral; vertical suites (for example mini-program engineering) build on it by adding domain facts and platform rules.
---

# /evidence-first-engineering — 证据优先工程基础

本技能是领域无关的工程治理基础：任何领域的 Agent 软件工程套件都可以 vendored 引用本层，再叠加自己的领域事实与平台规则。第一个垂直应用是小程序工程开发套件（mini-program-engineering-suite）。

## 核心组件

- [证据状态模型](guardrails/evidence-status-model.md)：状态只能由匹配证据支持，低级状态不得自动推导为高级状态；交付生命周期与用户验收正交。
- [共享工程门禁](guardrails/engineering-guardrails.md)：事实、范围、实现与调试、验证与发布、恢复与证据、来源独立性六类门禁。
- [判断与确认规则](guardrails/decision-and-confirmation-rules.md)：按动作影响与可逆性决定直接执行、先给依据还是先确认。
- [脱敏与公开包规则](guardrails/redaction-policy.md)：对外分发的脱敏标准、匿名形式与出包门禁。
- 四个交付模板（[项目摸排](templates/project-intake.md)、[实施计划](templates/implementation-plan.md)、[验证报告](templates/verification-report.md)、[发布清单](templates/release-checklist.md)）统一跨阶段输出结构。

## 使用方式（对垂直套件作者）

1. 把 `foundation/` 目录整体 vendored 到你的套件，或以相对链接引用（单仓场景）。
2. 你的领域 Skill 引用上述文档作为门禁与状态语言，不复制正文。
3. 领域易变事实（平台规则等）放你自己的事实层，并遵循「执行层即时查官方、内容层受控进化」的保鲜原则。
4. 引用本层时保留 `foundation-source` 标记，便于升级时同步。

## 输出契约（继承，不变）

阶段性或最终汇报至少包含：当前结论与阶段；已完成的动作及证据；未执行、未验证或待确认项；改动边界与残余风险；下一步动作。状态词使用证据状态模型；没有对应证据时诚实标注 `unknown`，不夸大。
