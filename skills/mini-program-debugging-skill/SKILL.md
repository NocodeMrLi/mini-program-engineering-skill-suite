---
name: mini-program-debugging-skill
description: >-
  Diagnose and fix mini-program failures through reproducible, evidence-driven root-cause analysis across source, state, asynchronous timing, caches, mock data, build versions, platform behavior, devices, cloud calls, and external services. Use when users report white screens, crashes, stale or jumping values, missing data, intermittent behavior, permission failures, performance stalls, device-only defects, API or cloud-function errors, source-versus-build mismatches, or regressions whose cause is not yet established. Freezes the observation environment, ranks competing hypotheses, runs discriminating checks, creates a failing regression test before repair, covers analogous states, and never hides a known failure with longer waits, swallowed errors, forced success, or cosmetic patches.
---

# /mini-program-debugging-skill — 小程序问题调试

从可重复症状建立证据链，定位能解释关键现象的根因，再以失败复现、最小修复和回归测试闭环。诊断请求本身不授权修改；用户要求修复或任务明确包含修复时，才进入受控改动。

## 输入与观察基线

- 接收症状、截图/视频、日志、错误码、复现步骤、项目事实图或失败测试。
- 先固定源码/构建版本、分支/文件状态、运行环境、设备/工具、账号/数据状态、网络与时间，再写最小复现和预期/实际差异。
- 截图是现象证据，不是根因；历史日志不能证明当前构建仍有同一问题。
- 若只有产品语义争议而非故障，退回产品规格；若根因已证实且只需实施，可交给实现阶段。

## 证据驱动调试流程

1. 用最少步骤稳定复现；无法稳定复现时记录频率、前置状态、成功/失败样本和最后正常版本。
2. 建立时间线与证据链：输入、默认值、状态迁移、异步时序、缓存、模拟数据、接口、渲染、构建版本、设备/平台结果。
3. 提出至少两个可证伪的竞争假设，为每个假设记录支持/反对证据和最小判别实验；先执行信息增益最高的只读检查。
4. 外部服务失败按调用前、传输、服务返回、解析、持久化和界面反馈分段，核对错误码、参数、耗时、重试与幂等，敏感值只报告存在性。
5. 根因结论必须解释主要现象和边界样本；证据不足时保持“最可能假设”，不把相关性写成根因。
6. 修复前写能失败的回归测试或自动复现；做最小修复后验证原症状、同类状态、共享契约和反例，避免只修截图实例。
7. 工具异常、超时、用户中止或外部响应不明确时，按 [中断恢复协议](references/interruption-recovery-protocol.md) 将在途动作记为 `unknown`，刷新事实后再决定是否重试。
   用户禁止启动业务或构建进程时，读取既有日志、产物、工作区和进程元数据的只读检查命令不属于启动业务或构建进程；除非用户明确禁止一切工具读取，否则先执行这些检查，不以“需要授权检查”代替事实刷新。
   已有产物可读时，计算并输出已有产物指纹（优先 SHA-256）并绑定路径；工具失败时输出失败原因和未取得指纹，不能只写“已检查产物”。
8. 使用 [问题调试工作流](references/debugging-workflow.md) 自检，并按 [调试报告模板](assets/debugging-report.md) 输出证据、修复与剩余风险。

## 禁止性策略

- 不用延长等待、吞掉错误、硬编码成功、强制刷新或清空缓存掩盖明确失败。
- 不把日志减少、占位内容、视觉遮挡或重试次数增加当成根因修复。
- 不在没有版本/产物证据时把源码修改当成设备问题已修复。
- 不为了验证假设执行未经授权的平台写操作、云端部署或破坏性数据修改。

## 最低输出

- 观察环境、最小复现、预期与实际、频率和影响范围。
- 时间线、证据表、竞争假设、判别实验与根因置信度。
- 修复差异、失败回归测试、同类状态覆盖与反例结果（若获授权修复）。
- 已验证和未验证层级、无法排除的假设、残余风险与下一步。
- 中断恢复输出必须逐项给出进程状态、副作用、幂等性和新授权；四项全部建立前明确禁止重放，不能只列其中一项。

## 停止条件

需要用户账号、真实凭证、设备操作、云端写入或破坏性数据才能取得下一项证据时停止并说明所需动作；三次不同判别实验仍无法区分假设时报告阻塞，不重复相同尝试。不得凭猜测修改生产路径。

## 独立与套件协作

独立安装时，本 Skill 可完成诊断，且在用户授权范围内修复。位于套件中时，接收轻量事实刷新，向实现阶段传递已证实根因与修复边界，再向验证阶段传递复现与回归入口；不直接调用其他组件脚本。
