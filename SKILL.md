---
name: mini-program-engineering-suite
description: >-
  Orchestrate evidence-first engineering for WeChat and other mini programs from a vague idea or existing repository through project discovery, product specification, architecture, implementation, debugging, device adaptation, verification, and release readiness. Use when users ask to build a mini program from zero to one, take over an existing mini-program project, deliver a cross-stage feature, diagnose project status, coordinate development and testing, or judge whether a mini program is ready to upload or release. Enforces fact discovery, change boundaries, stage gates, evidence-calibrated status, sensitive-information redaction, and continuity after side questions.
license: MIT
compatibility: Requires Python 3.9+ for bundled scripts; framework adapters are optional and discovered read-only.
metadata:
  version: "2.1.0"
  author: "Mini Program Engineering Suite contributors"
  maintainers: "Mini Program Engineering Suite contributors"
  language: "zh-CN"
  created: "2026-08-12"
  last_reviewed: "2026-08-29"
  review_interval_days: "90"
---

# /mini-program-engineering-suite — 小程序工程开发套件

把小程序任务视为一条有阶段、有门禁、有证据的工程链路。先确认当前事实，再决定路由和动作；只把已经有证据支持的状态报告给用户。

## 启动顺序

1. 读取当前项目及上级目录中的 `AGENTS.md`、`CLAUDE.md` 或同类规则文件。
2. 读取 [共享工程门禁](shared/engineering-guardrails.md)、[证据状态模型](shared/evidence-status-model.md)、[判断与确认规则](shared/decision-and-confirmation-rules.md) 和 [脱敏规则](shared/redaction-policy.md)。涉及中断恢复、资产或验证证据时，再分别读取 [中断恢复协议](skills/mini-program-debugging-skill/references/interruption-recovery-protocol.md)、[资产谱系记录](skills/mini-program-ui-device-skill/assets/asset-lineage-record.md) 和 [证据可采信规则](skills/mini-program-verification-skill/references/evidence-admissibility.md)；接管未知技术栈时可运行只读 `scripts/capability_doctor.py` 并按 [验证能力矩阵](skills/mini-program-verification-skill/references/verification-capability-matrix.md) 选择既有工具；涉及文档或对外输出时，再读取 [公开与内部文档边界](shared/documentation-boundaries.md)。
3. 判断这是新项目、已有项目，还是没有项目目录的咨询任务。
4. 已有项目若尚未建立本轮事实图，先使用 [项目接管 Skill](skills/mini-program-project-intake-skill/SKILL.md)。在完成只读接管前，不修改代码。
5. 建立或恢复任务计划，记录原目标、当前阶段、完成证据和未完成项。

## 判断当前阶段

使用 [路由与状态机](references/routing-and-state-machine.md) 判断当前阶段。允许跳过与任务无关的阶段，但必须说明依据；不能因为已经写了代码就跳过验证。

| 用户意图 | 当前路由 | 可用状态 |
| --- | --- | --- |
| 接管项目、了解现状、识别技术栈或改动边界 | [`mini-program-project-intake-skill`](skills/mini-program-project-intake-skill/SKILL.md) | 已实现 |
| 梳理产品、MVP、流程与状态 | [`mini-program-product-spec-skill`](skills/mini-program-product-spec-skill/SKILL.md) | 已实现 |
| 设计模块、数据、接口与权限 | [`mini-program-architecture-skill`](skills/mini-program-architecture-skill/SKILL.md) | 已实现 |
| 微信平台规则、工具、隐私与配置 | [`wechat-mini-program-platform-skill`](skills/wechat-mini-program-platform-skill/SKILL.md) | 已实现 |
| 编写或修改代码 | [`mini-program-implementation-skill`](skills/mini-program-implementation-skill/SKILL.md) | 已实现 |
| UI、参考还原、机型适配与手势 | [`mini-program-ui-device-skill`](skills/mini-program-ui-device-skill/SKILL.md) | 已实现 |
| 白屏、错误、卡顿或状态异常 | [`mini-program-debugging-skill`](skills/mini-program-debugging-skill/SKILL.md) | 已实现 |
| 独立测试、回归或交付证据判断 | [`mini-program-verification-skill`](skills/mini-program-verification-skill/SKILL.md) | 已实现 |
| 版本、导出、上传/审核/发布就绪治理 | [`mini-program-release-skill`](skills/mini-program-release-skill/SKILL.md) | 已实现 |

当目标组件尚未实现时，明确报告套件当前能力边界；可以继续做安全的只读发现与任务拆解，但不要伪装成已调用不存在的组件。已实现组件既可由主 Skill 编排，也可独立使用；组件只交换阶段产物，不直接调用彼此脚本。

## 编排工程任务

### 新项目从 0 到 1

按 `discovery → specification → architecture → implementation → verification → release-ready` 推进。先澄清核心用户、问题和最小闭环，再选择技术方案。没有用户授权时，不提交审核、不发布、不创建付费资源。

### 已有项目开发或修复

先执行项目接管，获得事实图、风险、未知项和改动边界。只在范围明确后实施；对错误先复现并定位根因，对共享契约补相应验证。

### 发布前判断

分别核对源码、当前分支、构建产物、开发者工具加载版本、平台上传记录与正式环境证据。任一层缺少证据时，只报告到已经证明的状态。

## 执行门禁

- 未读取事实源，不修改已有项目。
- 未确认产品语义，不新增按钮、入口、状态、付费、广告或数据规则。
- 高影响视觉方案先给预览或候选方案，用户确认后再集成。
- 数据、权限、外部服务和不可逆操作先说明影响、失败策略与回滚条件。
- 工具异常、超时或中止后的在途动作先保持 `unknown`，刷新本地与外部事实，不盲目重放写操作。
- 资产变体与证据材料分别记录谱系、指纹、适用范围和不能证明的内容。
- 已实现必须进入与风险匹配的验证；本地通过不能推导出真机、云端或发布通过。
- 对外输出和安装包运行 `python3 scripts/scan_sensitive_content.py <path> --format json`。

## 中途问题与连续执行

用户提出中途问题时，先回答问题，再判断它是否改变原目标。若没有改变，恢复原计划与未完成步骤；若改变，更新计划并说明受影响阶段。不得把中途问题当成默默终止原任务的理由。

## 输出契约

阶段性或最终汇报至少包含：

1. 当前结论与工程阶段。
2. 已完成的动作及对应证据。
3. 未执行、未验证或待用户确认的内容。
4. 当前改动边界与残余风险。
5. 下一步动作。

使用 [证据状态模型](shared/evidence-status-model.md) 中的状态词。用户明确验收前，不使用 `accepted`（已正式验收）；没有平台正式证据时，不使用 `released`（已正式发布）。

## 能力地图

- [项目接管 Skill](skills/mini-program-project-intake-skill/SKILL.md)：只读建立项目事实图、技术栈、风险、未知项和改动边界。
- [产品规格 Skill](skills/mini-program-product-spec-skill/SKILL.md)：将模糊想法收敛为范围、流程、状态矩阵与可测试验收标准，不发明产品逻辑。
- [工程架构 Skill](skills/mini-program-architecture-skill/SKILL.md)：把稳定产品语义映射为模块、状态源、数据、接口、权限、失败策略与 ADR。
- [微信平台适配 Skill](skills/wechat-mini-program-platform-skill/SKILL.md)：只读核对工具、构建、权限、隐私和发布证据层；时效性规则查微信官方当前资料。
- 平台事实层（按目标平台路由，doctor 的 `target_platforms` 决定入口）：
  - 微信：[platforms/wechat/](platforms/wechat/platform-evidence-layers.md)（证据层、核对清单、隐私矩阵、[规则地图](platforms/wechat/rule-map.json) 与 [核验标注](platforms/wechat/facts.md)；支持确定性漂移检测）；
  - 支付宝：[规则地图](platforms/alipay/rule-map.json) 与 [核验标注](platforms/alipay/facts.md)（官方文档为客户端渲染 SPA，确定性指纹不可观测，保鲜依赖运行时查官方与用户上报，规则地图标 `manual-only`）；
  - 未收录平台（如抖音）：无平台事实层，平台触点步骤一律查官方当前资料并保持 `unknown`，不猜测。
- 工程流程层遇到平台触点时引用对应平台事实层，不内置平台规则。
- [工程实现 Skill](skills/mini-program-implementation-skill/SKILL.md)：在明确边界内保护用户改动，以测试驱动小步实施并交付验证入口。
- [界面与真机适配 Skill](skills/mini-program-ui-device-skill/SKILL.md)：按参考目标处理预览、确认、集成、屏幕/内容边界、手势和真机证据。
- [问题调试 Skill](skills/mini-program-debugging-skill/SKILL.md)：从最小复现、竞争假设与判别实验定位根因，并覆盖同类状态回归。
- [工程验证 Skill](skills/mini-program-verification-skill/SKILL.md)：按风险分层执行静态、单元、集成、状态、真机、云端和发布验证，报告已执行、未执行与残余风险。
- [发布治理 Skill](skills/mini-program-release-skill/SKILL.md)：核对版本、构建、安全、权限隐私、回滚和各发布层证据；默认只读，外部动作逐项授权。

每个组件均包含独立的 `agents/openai.yaml`、工作流参考和可复用交付模板，可脱离主套件安装和触发；主 Skill 负责跨阶段编排、计划连续性和证据状态一致性。

## 共享模板与门禁

- [项目接管模板](shared/templates/project-intake.md)：统一接管输出。
- [实施计划模板](shared/templates/implementation-plan.md)：记录范围、步骤与门禁。
- [验证报告模板](shared/templates/verification-report.md)：区分检查范围与证据层级。
- [发布清单模板](shared/templates/release-checklist.md)：核对发布链路，但不授权外部操作。
- [共享工程门禁](shared/engineering-guardrails.md)、[证据状态模型](shared/evidence-status-model.md)、[判断与确认规则](shared/decision-and-confirmation-rules.md)、[脱敏规则](shared/redaction-policy.md) 和 [公开与内部文档边界](shared/documentation-boundaries.md)：统一约束所有组件。

## 维护脚本与公开包

- `VERSION`：套件语义版本事实源。
- `scripts/validate_suite.py`：检查主 Skill、九个分 Skill、共享层、公开文档、版本事实源、链接、frontmatter、界面元数据和占位内容。
- `scripts/check_i18n_readme_structure.py`：检查六种语言 README 的核心章节顺序，防止安装、验证、包完整性、版本和许可说明漂移。
- `scripts/scan_sensitive_content.py`：扫描公开包候选中的真实 AppID、云环境 ID、凭证形态、用户路径、邮箱、手机号、JWT、COS bucket、私钥块与二进制命中。
- `scripts/export_public_package.py`：按明确公共路径清单执行全候选敏感扫描和确定性导出，未知文件默认拒绝，并生成相对路径哈希清单。
- `scripts/verify_public_package.py`：只读取收到的公共包，独立复算文件大小与 SHA-256，并拒绝缺失、篡改、新增、非法路径或损坏清单。
- `scripts/summarize_evaluations.py`：把发布门禁的评测产物汇总为只含结论、关键指标与审计元数据的公开摘要，不含提示词、回复或夹具内容。
- [评测证据说明](EVALUATIONS.md)：说明三层评测、判定与独立签署各自能证明什么，以及各版本公开摘要政策。
- `scripts/capability_doctor.py`：只读识别原生/Taro/uni-app、既有脚本、测试依赖、分包和工具事实；不执行命令、不安装依赖、不输出配置值。
- `install.sh`：从源码或已导出的公开包中安装套件，默认不覆盖已有目录，项目级安装必须显式传入目标项目路径。
- `.github/workflows/ci.yml` 与 `.github/workflows/release.yml`：分别守住常规变更门禁和版本化发布包门禁；Release 附带压缩包、`package-manifest.json` 与 `SHA256SUMS`。

## 可靠性方法论资源

- [中断恢复协议](skills/mini-program-debugging-skill/references/interruption-recovery-protocol.md)：中断后把在途动作保持为 `unknown`，刷新事实并阻止盲目重放。
- [资产谱系记录](skills/mini-program-ui-device-skill/assets/asset-lineage-record.md)：追踪原始/衍生资产、处理、目标槽位、文件指纹、批准和替换关系。
- [证据可采信规则](skills/mini-program-verification-skill/references/evidence-admissibility.md)：判断证据来源、版本、完整性、适用结论和不能证明的内容。
- `scripts/capability_doctor.py`：只读识别原生/Taro/uni-app、既有脚本、测试依赖、分包和工具事实；不执行命令、不安装依赖、不输出配置值。
- [质量证据矩阵](skills/mini-program-verification-skill/assets/quality-evidence-matrix.md)：记录包体/分包、启动/首屏、运行错误和发布后观察窗。
