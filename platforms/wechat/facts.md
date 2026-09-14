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
  <!-- fact: privacy-guideline-required verified=2026-08-30 source=https://developers.weixin.qq.com/miniprogram/dev/framework/user-privacy/ digest=549f0eb28b7409603b427e8f1da8af3bf4f4aa163cdfeee7d3cabe5fc0da0cf4 -->
- 事实：运营规范主页正文现分七大节（原则说明、具体运营规范、小游戏特别规范、投诉与处罚、当地法律监管、免责声明、动态文档），提审与发布要求集中在「二、具体运营规范」下的注册提交、可用性和完整性、技术实现、UI、支付退款等 19 个小节；导航中的小商店、交易类、短剧等规范是独立子页面，不在主页正文。与提审直接相关的条款：5.19 提审版本须与实际发布上线版本一致，禁止以任何技术方式绕开或对抗审核监管；4.2 资质文件须真实合法有效，伪造可被拒审或追责。
  <!-- fact: operations-spec-scope verified=2026-09-14 source=https://developers.weixin.qq.com/miniprogram/product/ digest=73cb8f6151acf5e19625001c4dbf72412b654cdbebddaaac916f78fbe390c749 -->
- 事实：运营规范主页当前未载明驳回后的重提审流程与驳回原因查询入口（提取标记 NOT_STATED）；既往实践入口为小程序后台运维中心的审核记录页，以后台当前展示为准，属需登录确认的 manual 事实。
  <!-- fact: review-rejection-flow verified=2026-09-14 source=https://developers.weixin.qq.com/miniprogram/product/ digest=73cb8f6151acf5e19625001c4dbf72412b654cdbebddaaac916f78fbe390c749 -->
- 事实：开发者工具的当前稳定版本与环境要求以官方下载页为准；项目配置与构建行为兼容性变化需按当前版本核对。
  <!-- fact: toolchain-devtools verified=2026-08-30 source=https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html digest=694dd716b1ff1a8c4fe7ce70ec8d457edb6a09a15de27576e0bad13286c129e5 -->

以上事实已于 2026-08-30 完成基线重录：3.1.5 提取器修复后首次以完整正文计算指纹（旧提取器因噪声栈泄漏只看到 6-21 字符的页面标题，原 digest 实为空壳指纹，监测不到正文变化）；同页双跑逐字一致。verified 为核验日期（UTC）。后续变化由周频 drift-watch 比对发现；过期或 `ttl=0` 类步骤执行前仍须查官方现行资料。
