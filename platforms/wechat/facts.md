# 微信平台易变事实（facts）

本文件记录随平台运营而变化的微信平台事实，逐条带核验标注；运行时保鲜门禁与漂移检查据此判断新鲜度。方法类内容（证据层、核对清单、隐私矩阵）见同目录其余文件，不在此重复。

## 标注规范

每条事实紧跟一条 HTML 注释标注：

`<!-- fact: <id> verified=<UTC date|unknown> source=<官方URL> digest=<归一化指纹|unknown> -->`

- `verified` 为内容核验日期（UTC）；`unknown` 表示尚未核验，运行时门禁按过期处理。
- 无标注或标注不全的事实视为 `unverified`，同样按过期处理。
- `digest` 由保鲜工具（platform_drift，2.0 Phase 5）对官方正文做归一化指纹后写入；人工核验可暂记 `unknown`。
- 只收录公开可达的官方文档事实；需登录小程序后台才能确认的事实标记 `manual`，不进自动化。

## 事实清单

- 事实：小程序使用用户隐私接口时，须在平台配置《用户隐私保护指引》，相关接口可用性以平台申报与审核状态为准。
  <!-- fact: privacy-guideline-required verified=2026-08-30 source=https://developers.weixin.qq.com/miniprogram/dev/framework/user-privacy/ digest=d6ca28b83e144f9d47509e70764fe47823430db7089891ee3d94123858238821 -->
- 事实：平台运营规范覆盖注册、行为规范、内容标准与审核要求；提审前须按当前版本核对。
  <!-- fact: operations-spec-scope verified=2026-08-30 source=https://developers.weixin.qq.com/miniprogram/product/ digest=6970280c4bb4202b1efc4239b40f0af8ae9fc18a5298decf7812913220d74ef0 -->
- 事实：审核被驳回后可修正并重新提审；驳回原因以平台运维中心当前返回为准，不以历史截图替代。
  <!-- fact: review-rejection-flow verified=2026-08-30 source=https://developers.weixin.qq.com/miniprogram/product/ digest=6970280c4bb4202b1efc4239b40f0af8ae9fc18a5298decf7812913220d74ef0 -->
- 事实：开发者工具的当前稳定版本与环境要求以官方下载页为准；项目配置与构建行为兼容性变化需按当前版本核对。
  <!-- fact: toolchain-devtools verified=2026-08-30 source=https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html digest=4c562b850b1592a64f22d489170267f1f2c7da39abf797ebd0412b9a3020f1c0 -->

以上事实已于 2026-08-30 完成首次基线核验：digest 为当日官方页面归一化文本指纹，verified 为核验日期（UTC）。后续变化由周频 drift-watch 比对发现；过期或 `ttl=0` 类步骤执行前仍须查官方现行资料。
