---
name: mini-program-verification-skill
description: >-
  Verify mini-program implementations and fixes with risk-calibrated evidence across static checks, unit tests, integration tests, state matrices, simulators, real devices, cloud environments, and release artifacts. Use when users ask to test, validate, accept, regression-check, quality-check, confirm readiness, or determine whether a mini-program feature is actually complete. Binds results to a source and build fingerprint, records commands and observable evidence, separates passed, failed, blocked, and not-run layers, prioritizes the next highest-information check, and never converts local success into device, cloud, release, or formal acceptance claims.
---

# /mini-program-verification-skill — 小程序工程验证

固定版本和风险，逐层验证；只报告有证据支持的层级。

## 输入与版本指纹

- 接收目标、验收标准、交接、事实图、复现入口和可用环境。
- 记录已核实的分支/提交/文件哈希、构建/配置、工具/设备/云端环境与时间；匿名快照无 Git 时填 `unknown`，不借外层提交。
- 划分本轮目标与既有改动；不得清理、覆盖或计入无关变化。
- 验收行为不明时退回规格；故障根因不明时退回调试。

## 风险分层验证

1. 按目标、变更、共享契约、数据/权限/外部服务和历史缺陷建风险矩阵。
2. 审计按[短路径](references/source-audit-workflow.md)用工具枚举文件/目标；数量须由清单算出，否则不报。沿用户路径追踪输入→写入→读取→呈现；活动资源列创建、暂停、恢复、销毁，检查 `onLoad→onShow→onHide→onShow→onUnload`；纯函数正确不等于页面持续可用。
3. 再核对全称注释/承诺：摘实际表达式并算反例。“不重复”查游标走完集合并再次前进；“追加不影响”用同一输入比较集合长度变化前后的索引；非法数值查 `NaN`、无穷和小数，重进查状态恢复。不能只建议未来补测试；未证实不得判无发现或确认承诺成立。报告以发现为主体，各域记有发现/未发现/证据不足。
4. 标高严重度、关键错误或发布阻断前，核实完整性并完成机制反证闭环：调用实参、条件求值、实际分支/兜底、可观察后果，主动查找能推翻该机制的路径。部分快照未含引用只证明缺口；仅完整清单或实际构建/解析失败可证明真实缺失。未证实则区分事实与假设，降级或标记 `unknown`。
5. 先做低成本反证，再按风险升级：静态检查、单元测试、集成测试、状态矩阵、真机验证、云端验证、发布验证。
6. 每项记录实际命令或步骤、退出码、样本/设备、观察结果和证据位置；只写“测过了”不构成证据。
7. 覆盖正常、空、错误、边界、重复、并发/乱序、恢复与回归；不凑无关测试。
8. 留存失败证据，区分产品、实现、环境和证据问题；不改期望掩盖失败。
9. 按 [证据可采信规则](references/evidence-admissibility.md) 逐份核对来源、时间、版本、完整性、独立性、适用结论和不能证明的内容；质量标签不得用结论状态替代。
10. 未知项目先运行只读 capability doctor（独立安装时同等探测），按 [验证能力与适配矩阵](references/verification-capability-matrix.md) 复用能力；不自动安装或执行候选命令。
11. 多页面/流程/状态按 [分维度质量覆盖合同](references/dimensional-quality-contract.md) 枚举唯一目标，以只读 `check` 拦基线漂移；用 [质量证据矩阵](assets/quality-evidence-matrix.md) 记基础/专项、包体/分包、首屏、错误和发布观察窗，按 [验证工作流](references/verification-workflow.md) 与 [验证证据报告](assets/verification-evidence-report.md) 输出风险。

## 状态与证据边界

- 静态检查或单元测试最多支持 `locally-verified`，不推出真机、云端或发布结论。
- 模拟器截图不是设备证据；真机证据需绑定机型、系统、微信版本、步骤和截图/日志。
- 云端证据需绑定环境、部署版本、真实请求与日志；本地桩不能替代。
- 构建成功不等于已上传；已上传不等于审核通过或正式发布。
- 自主验证不等于正式验收；没有用户明确确认时，报告“验证通过，待验收”，不写 `accepted`。

## 最低输出

- 目标、范围、版本指纹、风险矩阵和验收行为。
- 各验证层的已执行命令/步骤、结果、证据位置与失败详情。
- 审计类任务的确定性文件/目标清单、用户点名领域覆盖表，以及所有高严重度或发布阻断发现的机制反证闭环。
- 审计发现全称承诺时，逐条给出“承诺、实际表达式、边界输入或最小反例、结论”；不能计算的标为证据不足，不用测试建议代替核验。
- 审计活动资源时，逐条给出创建、暂停、恢复、销毁的页面生命周期证据和断点。
- 条件触发时的目标单元来源、基础/专项覆盖数、失败项、`N/A` 依据、金样指纹和 `check` 结果。
- 未执行、被阻塞和不适用项目，以及为什么未执行。
- 当前可支持的最高状态、残余风险、不可推出结论和下一项高信息量验证。
- 截图/截断日志须记工具版本、时间、环境、步骤、证据/构建指纹及完整性；缺失填 `unknown`。
- 每份证据写 `admissible / limited / not-admissible` 及理由；结构化输出没有专用字段时写入事实或限制。`proven / not-proven` 不能代替证据质量标签。

## 停止条件

需要真实账号、设备、凭证、云端写入、付费资源或平台操作但未获授权时停止在当前证据层；三次不同验证方法仍被同一外部条件阻塞时报告阻塞。不得为了得到“通过”结论扩大外部权限。

## 独立与套件协作

独立安装可验证已有交付；套件内接收目标、版本和验证入口，向发布治理传递证据报告；不执行上传、审核或发布。
