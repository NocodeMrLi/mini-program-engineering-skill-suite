# 抖音平台易变事实（facts）

本文件记录随平台运营而变化的抖音小程序平台事实，逐条带核验标注；运行时保鲜门禁据此判断新鲜度。

## 标注规范

每条事实紧跟一条 HTML 注释标注：

`<!-- fact: <id> verified=<UTC date|unknown> source=<官方URL> digest=<归一化指纹|unknown> -->`

- 无标注或标注不全视为 `unverified`，运行时门禁按过期处理。
- 抖音开放平台文档为客户端渲染（任意 URL 返回同构壳页，正文为导航文本），确定性指纹无法观测文章内容（见 rule-map 的 `detection: manual-only`，2026-08-30 多 URL 探测证实）；本平台 `digest` 恒为 `unknown`，保鲜依赖运行时查官方与用户上报。

## 事实清单

- 事实：抖音小程序版本发布需在开放平台控制台完成上传、提审与发布；审核要求与驳回处理以平台当前规则为准。
  <!-- fact: release-review-flow verified=unknown source=https://developer.open-douyin.com/docs/resource/zh-CN/mini-app/operation/review digest=unknown -->
- 事实：使用涉及用户信息的接口需按平台要求完成隐私相关配置并遵循用户授权与撤回路径；具体清单以平台当前文档为准。
  <!-- fact: privacy-protection verified=unknown source=https://developer.open-douyin.com/docs/resource/zh-CN/mini-app/develop/guide/privacy digest=unknown -->

以上为结构占位种子，`verified` 均为 `unknown`：首次人工核验后写入日期；核验入口见 rule-map 各条 `official.url`。
