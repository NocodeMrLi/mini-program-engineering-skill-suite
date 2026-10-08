# 抖音平台易变事实（facts）

本文件记录随平台运营而变化的抖音小程序平台事实，逐条带核验标注；运行时保鲜门禁据此判断新鲜度。

## 标注规范

每条事实紧跟一条 HTML 注释标注：

`<!-- fact: <id> verified=<UTC date|unknown> source=<官方URL> digest=<归一化指纹|unknown> -->`

- 无标注或标注不全视为 `unverified`，运行时门禁按过期处理。
- 抖音开放平台文档为客户端渲染（任意 URL 返回同构壳页，正文为导航文本），确定性指纹无法观测文章内容（见 rule-map 的 `detection: manual-only`，2026-08-30 多 URL 探测证实）；本平台 `digest` 恒为 `unknown`，保鲜依赖运行时查官方与用户上报。

## 事实清单

- 事实：抖音小程序版本发布需在开放平台控制台完成上传、提审与发布；审核要求与驳回处理以平台当前规则为准。
  <!-- fact: release-review-flow verified=2026-10-08 source=https://developer.open-douyin.com/docs/resource/zh-CN/mini-app/operation/version-review/standard digest=unknown -->
- 事实：使用涉及用户信息的接口需按平台要求完成隐私相关配置并遵循用户授权与撤回路径；具体清单以平台当前文档为准。
  <!-- fact: privacy-protection verified=2026-10-08 source=https://developer.open-douyin.com/docs/resource/zh-CN/mini-app/open-capacity/basic-capacities/privacy-agreement digest=unknown -->

以上事实于 2026-10-08 再次人工核验：版本审核标准页的隐私保护标准仍列出 28 条要求，涉及用户同意、拒绝授权后的处理和第三方信息处理约束；专门的「配置隐私协议」页仍要求控制台配置、动态生效、使用隐私接口前获得用户授权，并保留官方/自定义/联合三种授权方式，未配置的接口会受限。补充读取[发布上线](https://developer.open-douyin.com/docs/resource/zh-CN/mini-app/introduction/develop-process/publish)（页面更新时间 2026-04-30）：IDE 上传后在控制台版本管理中体验、自查、提审，驳回原因可见，审核通过后可立即或灰度发布。核验入口见 rule-map 各条 `official.url`。
