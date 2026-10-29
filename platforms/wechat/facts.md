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

- 事实：小程序、插件涉及处理用户个人信息时，开发者须补充相应用户隐私保护指引。现网指引可在「账号设置—服务内容声明」完善，审核通过后生效；提审版本指引在「版本管理—提交代码审核」填写，审核通过且发布后覆盖现网版本。本页不完整列出隐私接口清单及授权撤回细则，涉及具体接口时仍需查对应官方文档与平台当前状态。
  <!-- fact: privacy-guideline-required verified=2026-10-29 source=https://developers.weixin.qq.com/miniprogram/dev/framework/user-privacy/ digest=b5748564b1a0ecbc64183ce437d79cbd3a527e4a75954cf425da515162493c38 -->
- 事实：运营规范主页正文分七大节（原则及相关说明、具体运营规范、小游戏特别规范、投诉与处罚、遵守当地法律监管、免责声明、动态文档）。「二、具体运营规范」的直接分节现编号为 2.1–2.19，包含注册提交、基本信息、功能设置、主体、行为、信息内容、可用性和完整性、技术实现、UI、支付退款、隐私和数据等。注册提交与主体规范要求按平台要求提供材料和修改、保证资质真实合法有效；行为规范要求提审版本与实际上线版本一致，不得绕开、规避或对抗审核监管。页面导航与独立文档入口不计入正文分节；旧页面的条款编号不应直接作为当前定位依据。
  <!-- fact: operations-spec-scope verified=2026-10-29 source=https://developers.weixin.qq.com/miniprogram/product/ digest=a19148674c15d3e2c745715fb5d7a540f6d2e800431075f51d3cacdc28789c19 -->
- 事实：运营规范主页在「四、投诉与处罚规范」给出高层路径：平台可能提供申诉渠道，开发者整改后可通过该渠道重新提交发布审核；多次整改仍不符合要求等情形下，平台可能暂时或永久关闭申诉渠道。公开正文未说明某次提审驳回原因的账号级查询入口和具体后台操作步骤；具体原因、审核记录和重新提交操作仍应以登录后小程序后台的当前展示为准，属需登录确认的 manual 事实。
  <!-- fact: review-rejection-flow verified=2026-10-29 source=https://developers.weixin.qq.com/miniprogram/product/ digest=a19148674c15d3e2c745715fb5d7a540f6d2e800431075f51d3cacdc28789c19 -->
- 事实：官方下载页的动态组件提供「备份下载地址」入口，备份页正文列出 Stable、RC、Nightly 及其下载平台与环境说明，确定性监测采用该官方静态正文。当前稳定版本与项目兼容性仍须按具体版本核对；备份页同时保留「Windows 7 及以上」旧提示与「Stable 从 1.06 起不支持 Windows 7」说明，不应据旧提示宣称当前稳定版支持 Windows 7，也不能由页面内容推导出本项目的构建或真机兼容通过。
  <!-- fact: toolchain-devtools verified=2026-10-29 source=https://developers.weixin.qq.com/miniprogram/dev/devtools/download_backup.html digest=3b72f9329184158f4d0ad1c24708f1fd3bc4ebaddfea0c245d04af55a099094b -->

2026-10-29 重新核对官方正文并录入基线：官网已采用 gzip 响应与新布局，读取器先受限解压，根节点布局状态不再触发整页噪声过滤；存在 `article#doc-content` 时只计算该正文的指纹，空动态组件不生成空壳指纹。工具链来源切到官方下载组件提供的静态备份入口。`verified` 为正文核验日期（UTC），不代表平台上传、审核、发布或项目兼容性通过；过期或 `ttl=0` 类步骤执行前仍须查官方现行资料。
