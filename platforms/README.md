# 平台事实层说明（platforms/）

本目录是各小程序平台的**易变事实层**：每个平台一个子目录（`wechat/`、`alipay/`、`douyin/`），含 `facts.md`（逐条带核验标注的事实）与 `rule-map.json`（规则地图：步骤类 → 官方权威文档 → 核对点 → TTL → 域名白名单）。工程流程层遇到平台触点步骤时引用本层，不内置平台规则。

## 两种操作，一条边界

公开技能文本中「步骤 7 核验结果不写回 facts/rule-map」与本目录存在 `verified` 日期与 `digest` 更新**并不冲突**——它们是两种不同的操作，发生在不同的主体与流程上：

| | 运行时保鲜门禁 | 基线刷新 |
| --- | --- | --- |
| **谁做** | 任意用户的 Agent，执行任务时 | 维护者，走仓库修订流程 |
| **做什么** | 核对事实新鲜度；过期/高风险步骤先查官方现行规则再执行；核验结果与漂移发现**只写入本轮任务报告** | 用工具实算官方页面指纹，经人工 PR 更新 facts.md 的 `verified` 日期与 `digest` |
| **改不改本目录文件** | **永不**（包括不更新 verified/digest 标注） | 是，但只经「工具实算 → 提案 → 审计 → 作者合并」的受控流程，随版本号与 CHANGELOG 走 |
| **目的** | 保证任何一次任务执行都以官方现行规则为准，与本地教材新旧无关 | 让周频漂移检测有可比对的基线（digest 与官方一致时报 unchanged，变化才报警） |

一句话：**运行时只读，刷新走 PR。** 用户侧永远不需要（也不可能）改这些文件；基线变化只发生在维护者的版本化提交里。

## 检测模式（detection）

- `detection` 缺省（如 wechat）：官方文档服务端渲染，确定性指纹可观测内容——周频 drift-watch 自动比对，变化开 issue 进入审计。
- `detection: manual-only`（如 alipay/douyin）：官方文档为客户端渲染同构壳页，确定性指纹**无法观测文章内容**——自动检测对该平台禁用（drift-watch 跳过，避免每周误报），保鲜依赖运行时查官方与用户上报。`detection_note` 记录判定依据（实测证据），不是措辞装饰。

## 事实标注规范

每条事实紧跟 HTML 注释标注：`<!-- fact: <id> verified=<UTC date|unknown> source=<官方URL> digest=<指纹|unknown> -->`

- 无标注或标注不全视为 `unverified`，运行时门禁按过期处理。
- `digest` 由 `scripts/platform_drift.py` 的归一化文本指纹实算（永不哈希原始 HTML）；人工核验可暂记 `unknown`。
- 同一 source URL 关联的多条事实 digest 必须一致；不一致时检测判 `inconsistent-baseline-digests`（fail-closed）。
- 只收录公开可达的官方文档；需登录后台确认的事实标 `manual`，不进自动化。

## manual-only 平台的人工核验节奏

支付宝与抖音的 facts 已完成首次人工核验（alipay 2026-08-30、douyin 2026-08-30/31 二次修正，详见各 facts.md 与 CHANGELOG）。为避免「知道要人工查、但版本记录看不出查没查」，按发布级别分级约定：

- **major 发布**：manual-only 平台（alipay/douyin）每条 rule 必须重新人工核验后才可发布。
- **minor 发布**：距上次核验超过 90 天，或本版本涉及平台事实/发布治理变更时核验。
- **patch 发布**：仅当修改了相关事实、出现用户上报漂移、或平台发生高风险变化时核验。
- **到期未核验**：`release_recommendation.py` 输出 `MANUAL_VERIFICATION_REQUIRED`，发布建议不得静默通过。
- **记录方式**：核验后把该条事实的 `verified` 更新为当日 UTC 日期（digest 保持 `unknown`，因 SPA 无法实算），并在 CHANGELOG 的该版本条目加一句「alipay/douyin facts 人工核验于 YYYY-MM-DD (tag: vX.Y.Z)」——`release_recommendation.py` 只认**本发布周期**内记录的核验证据（读取本版 CHANGELOG 块），仅有历史日期不满足 major/涉事实发布的要求。
- **发现变化时**：走与微信相同的受控修订流程（提案→审计→合并），只是触发源是人工而非指纹比对。

## 漂移处理路径

发现漂移（周频 CI 或用户上报）→ `platform_drift.py` L2 抽取生成脱敏提案（含模型抽取的 `extracted_statements` 与起草的 `proposed_fact_updates`）→ `review_drift_proposal.py` 四道确定性门禁 + K 轮一致性审计 → 裁决为 `PROPOSAL_CONSISTENT_WITH_EXTRACTION`（提案未超出模型抽取范围）或 `DO_NOT_APPLY` → **作者必须亲自打开官方页面核对抽取结果后**才可手动合并 → 随版本发布。

裁决语义的诚实边界：`PROPOSAL_CONSISTENT_WITH_EXTRACTION` **只**证明拟写入内容没有超出模型抽取结果，不证明抽取结果等于官方事实。工具链中不存在自动合并路径。
