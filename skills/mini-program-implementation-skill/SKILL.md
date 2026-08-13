---
name: mini-program-implementation-skill
description: >-
  Implement bounded features and fixes in existing or new mini-program codebases while preserving repository rules, user-owned changes, approved behavior, assets, framework conventions, and evidence boundaries. Use when users ask to write or modify mini-program code, implement a confirmed specification or architecture, add a scoped feature, remove behavior semantically, update internal documentation required by a change, or carry out a well-defined small fix that does not require root-cause investigation. Establishes a baseline and change boundary, applies test-driven small steps, distinguishes source from generators and build artifacts, verifies the affected contract, and never reports source completion as device validation, formal acceptance, upload, or release.
---

# /mini-program-implementation-skill — 小程序工程实现

在已确认的改动边界内，把稳定产品语义或工程方案落到代码和必要内部文档。保护现有项目、用户已有改动与已验收行为；实现完成后只报告匹配证据，不等于正式验收。

## 进入条件与边界

- 接收已确认规格/架构、明确的小型实现目标，或已有项目的事实图和改动边界。
- 已有项目先读取规则、相关源码/配置/文档、版本控制状态、测试与构建方式；记录用户已有改动，不覆盖、不回退、不顺手整理无关文件。
- 产品语义、数据规则、权限或外部服务影响尚不明确时，停在决策点；单纯可观察故障但根因未知时转入调试阶段。
- 不新增未获来源支持的入口、状态、付费、广告、权限理由或业务逻辑；不把内部实现细节擅自扩写到公开说明。

## 受控实现流程

1. 写出目标、允许修改文件/模块、必须保护内容、明确不做项、验证命令与回滚条件，建立修改前基线。
2. 识别真实事实源，区分手写源码、生成脚本、配置、资源和构建产物；应修改生成脚本时不直接把生成结果当唯一修复点。
3. 为新增行为或缺陷先建立能失败的测试或最小复现，执行 `RED` 并确认失败原因正确。
4. 写最小改动到 `GREEN`，运行目标测试；再做不改变行为的 `REFACTOR`，每一步保持范围可审查。
5. 检查空、错误、边界、重复操作、异步与受影响共享契约；发现相邻问题只记录，不静默扩大范围。
6. 复核差异、用户已有改动、敏感内容和必要内部文档，运行与风险相称的静态、单元或集成检查。
7. 使用 [工程实现工作流](references/implementation-workflow.md) 自检，并按 [实现交接模板](assets/implementation-handoff.md) 交给验证阶段。

涉及资产时建立资产谱系，至少记录原始/衍生关系、处理工具与方式、目标槽位、尺寸、透明通道、SHA-256、批准范围和替换关系。命令中断或超时后把在途写入记为 `unknown`，先刷新工作区、进程、产物和日志，不盲目重放。

## 最低输出

- 实现目标、输入事实、假设、改动边界与保护项。
- 逐文件改动清单，以及为何属于当前目标。
- `RED → GREEN → REFACTOR` 或无法采用测试驱动时的明确理由与替代证据。
- 已执行验证、结果、未验证层级、残余风险和回滚方式。
- 状态最多报告到证据支持的 `implemented`、`built` 或 `locally-verified`；不得推导真机、云端、验收、上传或发布。

## 停止条件

遇到无法安全区分的用户改动、互相冲突的事实源、需要扩大产品范围的选择、未批准的高风险数据/权限/外部服务变更、不可接受的迁移或回滚缺口时停止。不得以覆盖文件、重置工作区或跳过失败测试强行推进。

## 独立与套件协作

独立安装时，本 Skill 可完成边界明确的代码实现。位于套件中时，接收规格、架构或调试阶段的稳定交接，只输出实现差异与验证入口，不直接调用其他组件脚本。
