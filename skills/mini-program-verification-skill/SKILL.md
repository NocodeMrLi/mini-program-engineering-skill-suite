---
name: mini-program-verification-skill
description: >-
  Verify mini-program implementations and fixes with risk-calibrated evidence across static checks, unit tests, integration tests, state matrices, simulators, real devices, cloud environments, and release artifacts. Use when users ask to test, validate, accept, regression-check, quality-check, confirm readiness, or determine whether a mini-program feature is actually complete. Binds results to a source and build fingerprint, records commands and observable evidence, separates passed, failed, blocked, and not-run layers, prioritizes the next highest-information check, and never converts local success into device, cloud, release, or formal acceptance claims.
---

# /mini-program-verification-skill — 小程序工程验证

把“看起来完成”转成可复查的证据。先固定目标版本和风险，再逐层验证；已执行到哪一层，就只报告到哪一层。

## 输入与版本指纹

- 接收功能目标、验收标准、实现/修复交接、项目事实图、复现入口和允许使用的环境。
- 验证前记录当前分支、提交或文件哈希、源码状态、构建产物标记、配置开关、工具/设备/云端环境与时间。
- 若工作区已有用户改动，先划分本轮目标与既有差异；不得清理、覆盖或把无关变化计入验证结论。
- 没有稳定验收行为时退回产品规格；根因未知的故障退回调试，不用随机测试代替定位。

## 风险分层验证

1. 从用户目标、变更面、共享契约、数据/权限/外部服务和历史缺陷建立风险清单与验证矩阵。
2. 先运行低成本且能否定结论的检查，再按风险升级：静态检查、单元测试、集成测试、状态矩阵、真机验证、云端验证、发布验证。
3. 每项记录实际命令或步骤、退出码、样本/设备、观察结果和证据位置；只写“测过了”不构成证据。
4. 覆盖正常、空、错误、边界、重复操作、并发/乱序、恢复与回归；不为凑数量执行与风险无关的测试。
5. 失败时保存最小失败证据，区分产品不符合、实现缺陷、测试环境阻塞和证据缺失；不通过修改测试期望掩盖失败。
6. 使用 [证据可采信规则](references/evidence-admissibility.md) 记录产生工具、格式、版本、时间、环境/版本指纹、完整性、适用结论和不能证明的内容，并对每份证据给出 `admissible / limited / not-admissible` 质量标签；质量标签描述证据可采信程度，不与 `proven / not-proven` 等状态词混用或互相替代。
7. 对未知项目先运行套件提供的只读 capability doctor（若独立安装则执行同等只读探测），再按 [验证能力与适配矩阵](references/verification-capability-matrix.md) 复用现有能力；不自动安装或执行候选命令。
8. 使用 [质量证据矩阵](assets/quality-evidence-matrix.md) 记录包体/分包、启动/首屏、运行错误与发布后观察窗，并按 [验证工作流](references/verification-workflow.md) 和 [验证证据报告](assets/verification-evidence-report.md) 输出已执行、未执行和残余风险。

## 状态与证据边界

- 静态检查或单元测试成功最多支持 `locally-verified`，不推出真机验证、云端验证或发布验证。
- 模拟器截图不是设备证据；真机证据需绑定机型、系统、微信版本、步骤和截图/日志。
- 云端证据需绑定环境、部署版本、真实请求与日志；本地桩不能替代。
- 构建成功不等于已上传；已上传不等于审核通过或正式发布。
- 自主验证不等于正式验收；没有用户明确确认时，报告“验证通过，待验收”，不写 `accepted`。

## 最低输出

- 目标、范围、版本指纹、风险矩阵和验收行为。
- 各验证层的已执行命令/步骤、结果、证据位置与失败详情。
- 未执行、被阻塞和不适用项目，以及为什么未执行。
- 当前可支持的最高状态、残余风险、不可推出结论和下一项高信息量验证。
- 即使只评估截图转录或截断日志，也逐项输出采集工具、工具版本、时间、设备/环境、步骤、证据/构建指纹和完整性；缺失时必须明确写 `unknown` 或缺失，不能省略字段。

## 停止条件

需要真实账号、设备、凭证、云端写入、付费资源或平台操作但未获授权时停止在当前证据层；三次不同验证方法仍被同一外部条件阻塞时报告阻塞。不得为了得到“通过”结论扩大外部权限。

## 独立与套件协作

独立安装时可验证已有小程序交付。位于套件中时，接收实现/调试/UI 阶段的目标、版本和验证入口，向发布治理传递证据报告；不直接执行上传、审核或发布。
