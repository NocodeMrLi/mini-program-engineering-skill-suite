---
name: wechat-mini-program-platform-skill
description: >-
  Analyze WeChat Mini Program platform constraints and evidence layers for an idea or existing repository, including source configuration, build output, WeChat DevTools loading, device behavior, permissions, privacy declarations, cloud or backend linkage, upload, trial, review, and production status. Use when users ask about WeChat-specific configuration, project roots, compile paths, capability permissions, privacy compliance, official platform rules, upload or release readiness, or why source and platform behavior differ. Performs read-only evidence classification by default, verifies time-sensitive or high-risk claims against current official WeChat sources, redacts identifiers and secrets, and never upgrades one evidence layer into another.
---

# /wechat-mini-program-platform-skill — 微信小程序平台适配

识别微信小程序特有的工具、配置、权限、隐私和发布约束，并把不同证据层分开。默认只读核对；存在源码不等于开发者工具已加载，开发者工具可见不等于真机、审核版或正式版成立。

## 输入与安全边界

- 可接收产品/架构产物、项目目录、配置摘录、平台报错或发布状态问题。
- 已有项目先读取项目规则和事实图，再只读检查入口、构建目录及公开配置；不修改、不安装、不构建、不上传、不部署。
- 不输出或保存真实 AppID、Secret、云环境标识、账号、项目后台地址或凭证；报告中只写是否存在、来源层级和脱敏指纹。
- 未经用户明确授权，不打开开发者工具执行写操作，不创建云资源，不提交审核或发布。

## 平台适配流程

1. 确认问题属于通用产品/架构约束还是微信平台专属约束；只处理后者及二者的交界。
2. 按 [平台证据层](../../platforms/wechat/platform-evidence-layers.md) 分别记录源码、构建产物、开发者工具、真机、云端、体验版、审核版和正式版证据。
3. 只读核对项目根、源码目录、构建目录、平台配置、权限声明、隐私调用和运行所需外部能力；将私有配置视为敏感项。
4. 把“当前文件事实”“本轮工具/设备结果”“平台返回”和“历史记录”分开，不从低层证据推导高层状态。
5. 对微信平台时效性规则、高风险权限、隐私申报、审核要求或工具行为，检索微信官方当前资料；技术事实只采用官方一手来源，并记录核验日期与链接。
6. 使用 [权限与隐私静态映射](../../platforms/wechat/privacy-permission-matrix.md) 分开核对源码 API、客户端授权、配置声明、平台申报、用户拒绝与撤回路径；缺少高层证据时保持 `unknown`。
7. 平台触点步骤（上传、提审、审核、发布、隐私申报、配额）执行前，按 [平台规则地图](../../platforms/wechat/rule-map.json) 与 [平台事实](../../platforms/wechat/facts.md) 核对时效性：事实新鲜且非 `ttl=0` 类，可引用并注明核验日期；过期或 `ttl=0` 类先查官方现行资料。核验结果与漂移发现只写入本轮任务报告（含核验日期、来源链接、差异描述），**不写回 facts.md 或 rule-map.json，也不更新其中的 verified/digest 标注**——内容更新只走仓库的受控修订流程；可向用户提供项目仓库的 Platform rule drift 模板链接，由用户自愿上报。
8. 无法访问官方资料或官方说明不明确时，标记为 `unknown`，给出待核验问题，不凭记忆给确定结论。
9. 按 [微信平台核对清单](../../platforms/wechat/wechat-platform-checklist.md) 输出约束、证据、缺口、风险和下一步；只建议动作，不把建议写成已执行。

## 最低输出

- 微信平台问题范围和只读边界。
- 各证据层当前状态、事实源、时间与仍缺少的证明。
- 项目根/源码/构建目录关系，以及开发者工具实际加载对象（若有证据）。
- 权限、隐私、网络域名、云端或外部服务约束及脱敏风险。
- 时效性规则的微信官方依据；无法核验的未知项。
- 上传或发布前缺口，但不宣布未获平台证据支持的状态。

## 停止条件

需要真实凭证、账号登录、平台写操作或用户授权才能继续时停止；不同证据层相互冲突且无法只读消解时保留冲突；官方当前资料不可获得时不替平台作结论。

## 独立与套件协作

独立安装时，本 Skill 可单独完成微信平台只读核对。位于完整套件中时，遵守共享脱敏与证据状态模型；接收产品或架构约束、返回平台边界，不调用其他组件脚本。
