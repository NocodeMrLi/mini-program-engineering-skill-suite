---
name: mini-program-verification-skill
description: >-
  Verify mini-program implementations and fixes with risk-calibrated evidence across static checks, unit tests, integration tests, state matrices, simulators, real devices, cloud environments, and release artifacts. Use when users ask to test, validate, accept, regression-check, quality-check, confirm readiness, or determine whether a mini-program feature is actually complete. Binds results to a source and build fingerprint, records commands and observable evidence, separates passed, failed, blocked, and not-run layers, prioritizes the next highest-information check, and never converts local success into device, cloud, release, or formal acceptance claims.
---

# /mini-program-verification-skill — 小程序工程验证

固定版本和风险，逐层验证；只报告有证据支持的层级。

## 输入与版本指纹

- 接收目标、验收标准、交接、事实图、复现入口和可用环境。
- 记录分支、提交/文件哈希、构建、配置、工具/设备/云端环境与时间。
- 划分本轮目标与既有改动；不得清理、覆盖或计入无关变化。
- 验收行为不明时退回规格；故障根因不明时退回调试。

## 风险分层验证

1. 从用户目标、变更面、共享契约、数据/权限/外部服务和历史缺陷建立风险清单与验证矩阵。
2. 审计用工具枚举文件/目标，按领域追踪输入→写入→读取→呈现。写结论前，逐条核对可由输入、次数或规模推翻的全称注释/承诺：摘出实际表达式，计算最小反例或成立边界。对“不重复”须检查游标走完集合并再次前进；对“追加不影响”须用同一输入比较集合长度变化前后的索引；同时检查非法数值与重进。不能只建议未来补测试而不报告当前计算结果；未证实不得判无发现或确认承诺成立。报告以发现为主体，每域记有发现/未发现/证据不足。
3. 标记高严重度、关键错误或发布阻断前，先核实输入完整性，再完成机制反证闭环：调用实参、条件求值、实际分支/兜底、可观察后果，并主动查找能推翻该机制的路径。部分快照未包含引用路径只证明证据缺口；仅完整清单或目标版本实际构建/解析失败能证明真实缺失。任一环未证实时，分开事实与假设，降级或标记 `unknown`。
4. 先做低成本反证，再按风险升级：静态、单元、集成、状态矩阵、真机、云端、发布验证。
5. 每项记录实际命令或步骤、退出码、样本/设备、观察结果和证据位置；只写“测过了”不构成证据。
6. 覆盖正常、空、错误、边界、重复、并发/乱序、恢复与回归；不凑无关测试。
7. 保存最小失败证据，区分产品、实现、环境、证据问题；不改测试期望掩盖失败。
8. 按 [证据可采信规则](references/evidence-admissibility.md) 逐份核对来源、时间、版本指纹、完整性、独立性、适用结论和不能证明的内容；质量标签不得用结论状态替代。
9. 对未知项目先运行套件提供的只读 capability doctor（若独立安装则执行同等只读探测），再按 [验证能力与适配矩阵](references/verification-capability-matrix.md) 复用现有能力；不自动安装或执行候选命令。
10. 多页面/流程/状态项目按 [分维度质量覆盖合同](references/dimensional-quality-contract.md) 枚举唯一目标，分开基础/专项，以只读 `check` 拦基线漂移；用 [质量证据矩阵](assets/quality-evidence-matrix.md) 记覆盖、包体/分包、启动/首屏、错误和发布观察窗，按 [验证工作流](references/verification-workflow.md) 及 [验证证据报告](assets/verification-evidence-report.md) 输出执行情况与风险。

## 状态与证据边界

- 静态检查或单元测试成功最多支持 `locally-verified`，不推出真机验证、云端验证或发布验证。
- 模拟器截图不是设备证据；真机证据需绑定机型、系统、微信版本、步骤和截图/日志。
- 云端证据需绑定环境、部署版本、真实请求与日志；本地桩不能替代。
- 构建成功不等于已上传；已上传不等于审核通过或正式发布。
- 自主验证不等于正式验收；没有用户明确确认时，报告“验证通过，待验收”，不写 `accepted`。

## 最低输出

- 目标、范围、版本指纹、风险矩阵和验收行为。
- 各验证层的已执行命令/步骤、结果、证据位置与失败详情。
- 审计类任务的确定性文件/目标清单、用户点名领域覆盖表，以及所有高严重度或发布阻断发现的机制反证闭环。
- 审计发现全称承诺时，逐条给出“承诺、实际表达式、边界输入或最小反例、结论”；不能计算的标为证据不足，不用测试建议代替核验。
- 条件触发时的目标单元来源、基础/专项覆盖数、失败项、`N/A` 依据、金样指纹和 `check` 结果。
- 未执行、被阻塞和不适用项目，以及为什么未执行。
- 当前可支持的最高状态、残余风险、不可推出结论和下一项高信息量验证。
- 截图转录或截断日志也须逐项记录采集工具/版本、时间、设备/环境、步骤、证据/构建指纹和完整性；缺失填 `unknown`。
- 每份证据写 `admissible / limited / not-admissible` 及理由；结构化输出没有专用字段时写入事实或限制。`proven / not-proven` 不能代替证据质量标签。

## 停止条件

需要真实账号、设备、凭证、云端写入、付费资源或平台操作但未获授权时停止在当前证据层；三次不同验证方法仍被同一外部条件阻塞时报告阻塞。不得为了得到“通过”结论扩大外部权限。

## 独立与套件协作

独立安装时可验证已有小程序交付。位于套件中时，接收实现/调试/UI 阶段的目标、版本和验证入口，向发布治理传递证据报告；不直接执行上传、审核或发布。
