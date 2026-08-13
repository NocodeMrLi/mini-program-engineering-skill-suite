---
name: mini-program-project-intake-skill
description: >-
  Perform a read-only, evidence-first intake of an existing mini-program repository before planning or modifying code. Use when users ask to take over, understand, audit, resume, scope, or continue a WeChat or other mini-program project; when project facts may conflict with historical documents; or when an agent needs the framework, rules, Git state, build path, risks, unknowns, protected behavior, and change boundary. Produces a project fact map and handoff without changing code, installing dependencies, building artifacts, or claiming runtime, device, cloud, upload, acceptance, or release status.
---

# /mini-program-project-intake-skill — 小程序项目接管

对已有小程序执行只读接管，建立当前事实、风险、未知项和改动边界。接管完成前不修改代码，也不把历史计划当成当前事实。

## 只读边界

- 可以读取文件、目录、版本控制状态、现有日志和已有构建信息。
- 不修改代码、配置或文档，不安装依赖，不生成构建产物，不部署或改变外部状态。
- 若用户同时要求实现功能，先完成本接管输出，再把事实图交给后续阶段。
- 不能从文件存在推导出功能可运行，也不能从历史记录推导出当前真机、云端或发布状态。

## 接管流程

1. 解析项目根目录，并读取从项目根到当前目录范围内的规则文件。
2. 使用 `rg --files` 或等价只读方式建立目录画像，识别框架、入口、页面、组件、服务、云端目录、配置、测试与文档。
3. 读取包管理、构建、平台和版本控制配置，记录可用命令，但不要在接管阶段运行会写入产物的命令。
4. 检查 Git 状态、当前分支、未提交文件和忽略规则；把现有改动视为用户资产，不覆盖、不清理。
5. 按 [项目接管方法](references/intake-workflow.md) 区分当前事实、历史记录、推断和未知项。
6. 根据 [项目事实图模板](assets/project-fact-map.md) 输出结论，明确改动边界、需要保护的行为和下一阶段入口条件。

## 事实源优先级

按“用户当前明确要求 → 项目级规则 → 当前源码与配置 → 当前平台或运行结果 → 最新内部文档 → 历史方案与截图 → 一般经验”判断冲突。低优先级信息不能覆盖高优先级事实。

## 最低输出

- 用户目标和本轮只读范围。
- 已读取的事实源及其时效性。
- 技术栈、入口、关键模块、数据与外部依赖。
- 构建、测试、预览和发布链路的可见配置。
- 当前 Git 状态与必须保护的用户改动。
- 已确认风险、冲突、假设和未知项。
- 允许影响的文件、模块和行为组成的改动边界。
- 下一阶段可以开始的条件，以及仍需用户确认的事项。

## 停止条件

项目根目录无法确定、规则文件互相冲突、读取权限不足，或缺失信息会 materially（实质性地）改变后续方案时，停止在只读接管阶段并说明具体阻塞。不要用猜测填补核心产品语义。

## 套件协作

独立安装时，本 Skill 可单独完成项目接管。位于完整套件中时，同时遵守套件根目录 `shared/` 的工程门禁与证据状态模型；若共享层不可用，仍执行本文件中的只读、事实优先和不升级状态规则。
