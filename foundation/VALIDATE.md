# foundation 校验与 vendored 规则

本目录（evidence-first-engineering 基础层）可被整体 vendored 到任意领域的 Agent 套件。

## 结构自检

- 本层含 1 份 SKILL.md（官方 frontmatter 契约：name + description）、4 份治理文档（guardrails/）、4 份交付模板（templates/）。
- 8 份内容文件（guardrails/×4 + templates/×4）末尾带 `foundation-source` 标记，版本跟随源套件主版本；SKILL.md 与本文件是本层自有文档（无 shared/ 原版，不参与等价断言），不带标记。
- 源套件用 `scripts/check_foundation_equivalence.py` 断言本层与 shared/ 原版逐字节等价（声明的通用化差异除外）；vendored 方没有该脚本时，可按标记行核对来源与版本。

## vendored 同步规则

1. 引用而非复制：单仓场景直接相对链接 `foundation/guardrails/...`，不把正文复制进领域 Skill。
2. 升级同步：源套件主版本升级后，vendored 方用等价性脚本或标记行核对本层是否变化；未变化则只升级源套件，变化则同步本层并重跑领域套件自己的门禁。
3. 领域叠加：领域易变事实（平台规则等）放领域自己的事实层，遵循「执行层即时查官方、内容层受控进化」。
4. 引擎依赖：本层不含执行引擎（agent CLI/HTTP 适配）；需要引擎能力的领域套件自带等价物，本层只约束行为契约。

## 边界

本层不验证任何具体项目的实现、审核或发布状态；它约束的是治理方法的一致性。
