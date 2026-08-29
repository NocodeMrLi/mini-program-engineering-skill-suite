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
  <!-- fact: privacy-guideline-required verified=unknown source=https://developers.weixin.qq.com/miniprogram/dev/framework/user-privacy/ digest=unknown -->
- 事实：平台运营规范覆盖注册、行为规范、内容标准与审核要求；提审前须按当前版本核对。
  <!-- fact: operations-spec-scope verified=unknown source=https://developers.weixin.qq.com/miniprogram/product/ digest=unknown -->
- 事实：审核被驳回后可修正并重新提审；驳回原因以平台运维中心当前返回为准，不以历史截图替代。
  <!-- fact: review-rejection-flow verified=unknown source=https://developers.weixin.qq.com/miniprogram/product/ digest=unknown -->

以上种子事实迁移自既有清单，`verified` 均为 `unknown`：待保鲜工具首次核验后写入日期与指纹。在此之前的运行时门禁都会要求先查官方现行资料。
