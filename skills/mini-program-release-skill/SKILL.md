---
name: mini-program-release-skill
description: >-
  Govern mini-program release readiness and evidence across source branches, semantic versions, build artifacts, test flags, debug paths, sensitive data, permissions, privacy declarations, platform uploads, review submissions, staged versions, production releases, and rollback plans. Use when users ask for a release checklist, packaging, export, version bump, upload readiness, submission readiness, launch status, rollback preparation, or a precise judgment of what has and has not shipped. Defaults to read-only preflight, requires separate explicit authorization for every external state change, and never treats a Git push, successful build, platform upload, review submission, approval, or production publication as interchangeable.
---

# /mini-program-release-skill — 小程序发布治理

默认执行只读发布预检，形成可审计的 release-ready 判断。核对证据不等于获得外部操作权限；每一种外部状态变化都必须单独明确授权。

## 输入与发布目标

- 接收目标版本、目标分支、功能范围、验证报告、平台/渠道、计划窗口、回滚策略和用户授权边界。
- 先记录当前分支、提交、工作区、版本事实源、源码、构建产物和开发者工具加载目标；证据不一致时停止在 `not-ready`。
- 涉及微信规则、权限、隐私或审核要求且可能变化时，只查询当前官方资料；无法核对时保留 `unknown`。

## 只读发布预检

1. 核对目标功能已在当前分支，版本符合语义化策略，源码与构建产物绑定同一指纹。
2. 核对静态、单元、集成、状态矩阵以及风险所需的真机/云端证据；失败或未执行项必须映射为阻塞或残余风险。
3. 核对源码和构建产物中的测试开关、模拟数据、调试入口、日志、后门路径和内部文案。
4. 执行敏感信息扫描与人工匿名化复核；核对权限、隐私声明、域名/服务和实际功能一致性，但不回显凭证值。
5. 准备版本说明、变更范围、已知问题、监控/观察点、回滚条件、回滚版本与复验步骤。
6. 分别记录代码推送、平台上传、体验版、审核提交、审核结果和正式发布的证据；任何一层缺证据都保持 `unknown`。
7. 使用 [发布治理工作流](references/release-governance-workflow.md) 判定阻塞，按 [发布就绪记录](assets/release-readiness-record.md) 输出。

外部动作发生中断、超时或回执不明确时，当前状态保持 `unknown`；先查询平台记录、目标版本和回执，再判断已生效、未生效或仍不确定。原上传/审核/发布授权不自动成为高风险动作的重放授权。

## 权限与状态边界

- Git 提交不等于代码推送；代码推送不等于平台上传；构建成功也不等于平台上传。
- 平台上传不等于审核提交；审核提交不等于审核通过；审核通过不等于正式发布。
- 用户说“检查”“准备”“看看能不能发”只授权只读预检，不授权外部动作。
- 即使用户给出总目标，也应在执行平台上传、审核提交或正式发布前确认具体目标、版本和回滚条件已明确。
- 输出行动清单或结构化 `proposed_actions` 时，每个行动条目只能包含一个外部动作。代码推送、平台上传、提交审核、正式发布、云端修改和付费资源创建不得合并授权；每项分别记录目标、版本、影响、回滚条件与 `requires_authorization: true`。
- 不得自动推送代码、平台上传、提交审核、正式发布、修改云端、创建付费资源或改变外部状态。

## 最低输出

- 发布目标、当前分支、提交、版本、源码/构建/工具指纹与工作区状态。
- 验证证据、安全、测试开关、敏感信息、权限、隐私和回滚检查结果。
- 关键证据的产生工具、格式、版本、时间、目标指纹、可采信范围和不能证明的内容。
- 每个发布层的当前状态、证据、缺失项与阻塞项。
- 当前结论：`not-ready` / `release-ready` / `uploaded` / `review-submitted` / `review-approved` / `released`；只使用证据支持的最高状态。
- 获准外部动作、未获准动作、残余风险和下一步。

## 停止条件

目标版本/分支不明、验证失败、源码与产物不一致、敏感信息命中、回滚缺失或平台证据冲突时停止。需要账号、验证码、凭证、真实平台写入或付费操作但未获明确授权时，不尝试绕过。

## 独立与套件协作

独立安装时可执行发布就绪审查和已授权的发布步骤治理。位于套件中时，接收验证报告和微信平台约束，输出发布状态证据；不会因处于端到端流程而获得额外外部权限。
