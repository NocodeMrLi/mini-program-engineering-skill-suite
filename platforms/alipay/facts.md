# 支付宝平台易变事实（facts）

本文件记录随平台运营而变化的支付宝小程序平台事实，逐条带核验标注；运行时保鲜门禁与漂移检查据此判断新鲜度。

## 标注规范

每条事实紧跟一条 HTML 注释标注：

`<!-- fact: <id> verified=<UTC date|unknown> source=<官方URL> digest=<归一化指纹|unknown> -->`

- 无标注或标注不全视为 `unverified`，运行时门禁按过期处理。
- 支付宝文档中心为客户端渲染 SPA，确定性指纹无法观测内容变化（见 rule-map 的 `detection: manual-only`）；因此本平台 `digest` 恒为 `unknown`，保鲜完全依赖运行时查官方与用户上报。

## 事实清单

- 事实：支付宝小程序版本发布需在开放平台控制台完成上传、提审与发布操作；审核要求与驳回处理以平台当前规则为准。
  <!-- fact: release-review-flow verified=2026-10-08 source=https://opendocs.alipay.com/mini/introduce/release digest=unknown -->
- 事实：使用涉及用户信息的接口需按平台要求配置隐私协议并遵循用户授权与撤回路径；具体清单以平台当前文档为准。
  <!-- fact: privacy-protection verified=2026-10-08 source=https://opendocs.alipay.com/mini/03lwro digest=unknown -->

以上事实于 2026-10-08 再次人工核验（浏览器读取官方正文并逐条对照 verify_points）：发布流程页更新时间为 2026-06-02，仍要求开发工具上传后在控制台提审、处理驳回、上架，允许可选体验版、灰度及线上版本回滚；常规审核为 2 个工作日，特殊情形以页面说明为准。隐私政策页更新时间为 2026-08-14，要求提审前完成配置，并覆盖第三方插件/SDK 信息、补充文档和 OpenAPI 配置路径。[my.openSetting](https://opendocs.alipay.com/mini/api/qflu8f) 补充确认用户可在设置中修改已经请求过的权限，返回最新授权结果；该接口不代表所有信息处理目的的统一撤回方式。核验与更新走人工流程（SPA 限制自动化指纹），核验入口见 rule-map 各条 `official.url`。
