---
name: mini-program-product-spec-skill
description: >-
  Convert a vague mini-program idea, feature request, or partially documented product into an evidence-calibrated product specification with target users, core problem, version-one scope, main and exception flows, page responsibilities, state matrices, and testable acceptance criteria. Use when users ask to define an MVP, clarify requirements, organize product flows, specify page behavior, resolve ambiguous product states, or prepare a stable handoff before architecture or implementation. Separates facts, user decisions, assumptions, unknowns, and future ideas; never invents product logic merely to complete a screen or technical plan.
---

# /mini-program-product-spec-skill — 小程序产品规格

把模糊想法收敛为可交接、可验证的小程序产品规格。只定义“用户需要什么、在什么条件下发生什么”，不决定代码结构，也不直接实现页面。

## 输入与边界

- 可接收一句想法、需求记录、原型、现有页面说明或只读项目事实图。
- 先区分用户已确认事实、当前产品事实、有依据的假设、未知项和未来规划。
- 缺少的信息不会改变核心闭环时，采用最小且明确标注的假设继续；会实质性改变用户、价值、数据规则、付费、权限或主流程时，列为决策点。
- 不发明按钮、入口、奖励、社交、付费、广告、数据规则或异常处理来填满页面。
- 不决定代码结构、框架、数据库、API 形态或微信平台配置；这些分别交给架构和平台阶段。

## 规格流程

1. 写出目标用户、发生场景、核心问题、用户期望结果和成功条件。
2. 划定第一版最小闭环，分别记录 `本版包含`、`本版不包含` 和 `未来候选`。
3. 用“触发 → 用户动作 → 系统反馈 → 状态变化 → 完成结果”描述主流程。
4. 对无数据、加载中、失败、权限拒绝、重复操作、退出恢复和不可达条件补异常流程。
5. 建立页面清单，只写页面职责、入口、出口和依赖的已确认状态，不写视觉或代码方案。
6. 为关键页面和对象建立状态矩阵，明确状态来源、可见内容、允许动作和迁移条件。
7. 将每条验收标准写成可观察行为；优先使用 `Given / When / Then`，避免“体验良好”“正常显示”等不可测试措辞。
8. 使用 [产品规格工作流](references/specification-workflow.md) 自检，再按 [产品规格模板](assets/product-specification.md) 交付。

## 最低输出

- 目标用户、核心问题、价值主张与成功条件。
- 已确认事实、假设、未知项和待用户决策项。
- 第一版范围、明确不做项与未来候选。
- 主流程、异常流程、页面职责与状态矩阵。
- 可测试验收标准，以及产品层仍未覆盖的风险。
- 交给架构阶段的稳定语义和不可擅自改变项。

## 停止条件

当核心用户、核心价值或关键数据规则存在互斥解释，且任一选择都会实质性改变主流程时，停止在决策点，不用假设替用户拍板。若用户要求直接编码但产品语义尚不稳定，先交付最小规格和阻塞项。

## 独立与套件协作

独立安装时，本 Skill 可单独产出产品规格。位于完整套件中时，遵守套件共享的事实优先、确认门禁、证据状态和脱敏规则；只把规格产物交给后续阶段，不调用其他组件脚本。
