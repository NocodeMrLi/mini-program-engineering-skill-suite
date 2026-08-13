---
name: mini-program-architecture-skill
description: >-
  Translate a confirmed mini-program product specification or bounded feature into an implementable architecture covering modules, pages, components, services, canonical state sources, data models, interfaces, permissions, failures, caching, concurrency, idempotency, migration, rollback, external dependencies, and architecture decision records. Use when users ask how to structure a mini program, design data or APIs, divide frontend and cloud responsibilities, evolve an existing system safely, or prepare implementation after product semantics are stable. Preserves product meaning, current repository constraints, user-owned changes, and verifiable acceptance behavior rather than redesigning the product for technical convenience.
---

# /mini-program-architecture-skill — 小程序工程架构

把已经确认的产品语义映射为可实现、可验证、可迁移和可回滚的工程方案。架构服务于产品约束，不改变产品语义来迁就技术方案。

## 进入条件与边界

- 需要一份稳定的产品规格、明确功能边界，或现有项目的只读事实图。
- 已有项目先读取规则、当前源码与配置、Git 状态和必须保护的用户改动；优先延续已经有效的工程模式。
- 若目标用户、主流程或关键数据规则仍有实质冲突，退回产品决策点，不用架构选择掩盖歧义。
- 不直接实现代码，不决定未确认的按钮、奖励、付费、权限理由或业务状态。

## 架构流程

1. 列出输入事实、产品不变量、质量目标、约束、未知项和不在本轮范围内的内容。
2. 将页面职责映射为页面、组件、领域服务、平台适配层和外部依赖，明确每层所有权。
3. 为关键事实指定唯一规范状态源，说明派生状态、生命周期、刷新时机与跨页同步。
4. 定义数据模型、标识、版本、校验、读写边界和敏感字段；说明本地、云端或第三方的权威关系。
5. 定义 API 或云函数契约、认证与权限、错误分类、超时、重试、降级和可观察证据。
6. 针对重复请求、离线恢复、多端写入和异步回调，明确缓存、并发、幂等与一致性策略。
7. 若涉及存量数据或接口，写出兼容、迁移、灰度、回滚条件和失败后的恢复路径。
8. 比较至少一个可行替代方案，记录选择理由、代价和需要重新评估的触发条件。
9. 使用 [架构工作流](references/architecture-workflow.md) 自检，并按 [架构决策记录模板](assets/architecture-decision-record.md) 输出 ADR 与实施交接。

## 最低输出

- 架构范围、事实、产品不变量、质量目标与未知项。
- 页面/组件/服务/平台层边界及依赖方向。
- 状态源、数据模型、接口、权限与失败策略。
- 缓存、并发、幂等、一致性、迁移和回滚方案。
- 外部依赖风险、可观察性和对应产品验收行为。
- ADR：选择、替代方案、代价、验证方式与重新评估条件。

## 停止条件

关键产品语义未确认、当前项目存在无法保护的未知改动、核心外部能力不可核验，或数据迁移没有可接受回滚路径时，停止并报告具体缺口。不要用“实现时再说”隐藏高影响决策。

## 独立与套件协作

独立安装时，本 Skill 可基于给定规格完成架构设计。位于完整套件中时，遵守共享工程门禁和证据状态；只接收阶段产物、输出 ADR 和实施边界，不调用其他组件脚本。
