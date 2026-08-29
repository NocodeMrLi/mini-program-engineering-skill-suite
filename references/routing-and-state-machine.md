# 路由与工程状态机

## 目录

1. 状态机
2. 路由原则
3. 典型链路
4. 阶段交接

## 状态机

| 阶段 | 最低进入条件 | 最低退出证据 |
| --- | --- | --- |
| `discovery`（项目发现） | 用户给出目标或项目目录 | 事实源、风险、未知项和改动边界已记录 |
| `specification`（产品规格） | 核心目标和用户可讨论 | 主流程、异常流程、状态和验收行为明确 |
| `architecture`（工程架构） | 产品语义稳定 | 模块、数据、接口、权限和失败策略明确 |
| `implementation`（工程实现） | 改动边界与必要方案已确认 | 源码及必要测试完成，未越界 |
| `debugging`（问题调试） | 有可观察症状或失败 | 根因证据与影响范围明确 |
| `verification`（工程验证） | 存在待证明的实现或修复 | 所需检查已运行，结果和未覆盖项已记录 |
| `release-ready`（发布就绪） | 验证达到发布风险要求 | 分支、构建、开关、敏感项与回滚条件通过 |
| `released`（已发布） | 用户授权外部发布动作 | 平台或正式环境提供可核对证据 |
| `retrospective`（复盘沉淀） | 阶段交付结束 | 通用经验、项目记录与遗留项已归档 |

阶段可以按任务裁剪。例如纯调试任务可以从轻量 `discovery` 进入 `debugging`，但不能跳过修复后的 `verification`。

## 路由原则

1. 单阶段任务只加载必要组件。
2. 跨阶段任务由主 Skill 保存计划、阶段结论与证据，不让组件直接互相调用脚本。
3. 组件不存在或尚未安装时，明确能力边界，不虚构调用结果。
4. 涉及微信平台时效性规则、高风险配置或发布要求时，只使用当前官方资料进行核查。
5. 共享门禁始终生效，不能被组件自己的便利流程覆盖。

## 产品与架构路由

- 目标用户、MVP、产品范围、主/异常流程、页面职责、状态矩阵或验收行为不明确时，使用 [产品规格 Skill](../skills/mini-program-product-spec-skill/SKILL.md)。
- 产品语义稳定，需要设计模块、状态源、数据模型、接口、权限、失败、迁移或回滚时，使用 [工程架构 Skill](../skills/mini-program-architecture-skill/SKILL.md)。
- 问题涉及微信开发者工具、构建目录、权限、隐私、平台配置、上传、审核或发布证据时，使用 [微信平台适配 Skill](../skills/wechat-mini-program-platform-skill/SKILL.md)。
- 同时命中多个阶段时，按 `specification → architecture → wechat-platform` 传递最小交接产物；局部改动不影响结构时可以有依据地跳过架构阶段。

## 实施、界面与调试路由

- 产品语义与改动边界已经稳定，需要编写、修改或语义删除代码时，使用 [工程实现 Skill](../skills/mini-program-implementation-skill/SKILL.md)。症状根因未知时先调试，不盲改。
- 任务涉及参考还原、视觉预览、布局/内容边界、安全区、键盘、触控、滚动、手势或真实设备适配时，使用 [界面与真机适配 Skill](../skills/mini-program-ui-device-skill/SKILL.md)。高影响视觉先预览并取得用户确认，再正式集成。
- 任务涉及白屏、卡顿、异常值、间歇错误、旧构建、设备差异、权限或外部服务失败且根因未明时，使用 [问题调试 Skill](../skills/mini-program-debugging-skill/SKILL.md)。
- 新功能通常按 `implementation → ui-device（涉及界面时）→ verification`；故障按 `debugging → implementation（获授权修复时）→ verification`。

## 验证与发布路由

- 需要测试、回归、验收证据、质量判断或确认实现是否完成时，使用 [工程验证 Skill](../skills/mini-program-verification-skill/SKILL.md)。根据风险选择证据层，未执行层保持 unknown。
- 需要版本、打包、导出、上传/审核/发布就绪判断、发布记录或回滚治理时，使用 [发布治理 Skill](../skills/mini-program-release-skill/SKILL.md)。默认只读，外部状态变化逐项授权。
- 发布前按 `verification → wechat-platform（涉及微信当前规则时）→ release-ready`；上传、审核和正式发布不是自动连续动作，各自需要授权和平台证据。

## 典型链路

- 新项目：`discovery → specification → architecture → implementation → verification → release-ready`。
- 已有项目新功能：`discovery → specification → architecture（若结构受影响）→ implementation → verification`。
- 真机问题：`discovery（轻量刷新）→ debugging → implementation → verification`。
- 发布前检查：`discovery（刷新分支和产物）→ verification → platform → release-ready`。

## 阶段交接

每次交接传递以下最小信息：用户目标、已确认事实、假设、改动边界、完成证据、未知项、风险与下一阶段入口条件。不要传递冗长内部推理，也不要把假设改写成事实。
