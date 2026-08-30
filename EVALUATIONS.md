# 评测证据说明

本页说明这套技能在冻结发布前经过的评测分层、各层能证明什么、公开摘要政策，以及如何复现。评测摘要本身由 `scripts/summarize_evaluations.py` 从内部评测产物生成，只包含结论、关键指标与审计元数据，不包含提示词、模型回复或夹具内容。

## 评测分层

| 层 | 方式 | 能证明 | 不能证明 |
| --- | --- | --- | --- |
| tier1 结构与预算 | 本地静态检查：结构校验、frontmatter、链接、描述语言、token 预算、资源引用、开发内容泄漏 | 公共包结构完整且不超预算 | 任何 Agent 实际行为 |
| tier2 路由评测 | 以九个组件的 frontmatter 描述为唯一输入，让独立 Agent 会话对用例选择技能，与预期路由比对 | 描述文本在该批用例上的路由命中率不低于 0.90 | 真实任务成功率；未覆盖用例的路由质量 |
| tier3 行为/方法论评测 | 匿名夹具上加载对应技能后由独立 Agent 会话完成结构化响应，比对必需与禁止行为，并核对夹具未被修改 | 该批夹具上必需行为成立、禁止行为未出现、写入未越界 | 更广任务表现；真实项目效果 |
| 判定（judge） | 独立新会话按固定 rubric 对 with-skill 与 baseline 同时判定 | 相同标准下的相对有效性 | 用户验收；任何真实项目结论 |
| 独立签署（signer） | 汇总全部门禁产物与独立判定，输出最终版本结论 | 本版本通过既定发布门禁 | 发布者身份；安装后的使用效果 |

## 发布政策

- 每个 minor 或 major 版本在发布门禁通过后，把 `summarize_evaluations.py` 生成的摘要表格填入下方的版本记录。
- patch 版本不重复附摘要，沿用所属 minor 版本的最近一份摘要，并在 CHANGELOG 说明修复范围。
- 评测产物（含逐案例明细）保留在内部评测目录；公开摘要只含结论与审计元数据（时间、引擎、模型、提示词/架构指纹）。
- 路由用例分为 development 与 held-out 两批；held-out 批在冻结前不可用于调参，避免把评测做成训练。

## 复现命令

评测依赖本地 Agent 运行器（如 Codex CLI）；tier1 为纯本地检查。生成公开摘要：

```bash
python3 scripts/summarize_evaluations.py \
  --tier1 <tier1-report.json> \
  --routing-development <report.json> --routing-held-out <report.json> \
  --behavior-development <report.json> --behavior-held-out <report.json> \
  --methodology-development <report.json> --methodology-held-out <report.json> \
  --validation <validate-report.json> --sensitive <scan-report.json> \
  --package-verification <verify-report.json> --independent-judgment <judge-report.json> \
  --final-signature <signer-report.json> \
  --version "$(cat VERSION)" --output EVALUATIONS.md
```

摘要生成后会整体替换本页的版本记录表格；逐案例材料始终留在内部目录。

## 版本记录

| 版本 | 日期 | 摘要 | 说明 |
| --- | --- | --- | --- |
| 2.1.0 | 2026-08-30 | 全部门禁 PASS（增量评测，见下表） | 引擎 `claude:default`（DeepSeek 后端）；tier1 与 methodology 重跑（2.1 变更影响面），routing 与 behavior 复用 2.0.0 PASS 产物（九个子 Skill 描述与行为文本与 v2.0.0 评测输入逐字节一致）；独立终审与签署 PASS |
| 2.0.0 | 2026-08-29 | 全部门禁 PASS（见下表） | 引擎 `claude:default`（DeepSeek 后端）；tier2 路由 64/64；四个 tier3 判定 skill 1.00 且无回归，methodology-development 呈现最强对照（skill 1.00 / baseline 0.00）；独立终审与签署 PASS |
| 1.4.0 | 2026-08-29 | 全部门禁 PASS（见下表） | 引擎 `claude:default`；tier2 路由 64/64；四个 tier3 判定 skill 1.00 且无回归；独立终审与签署 PASS |

### 2.1.0 评测摘要（增量）

| 门禁 | 结论 | 关键指标 | 审计元数据 |
| --- | --- | --- | --- |
| tier1 结构、预算与资源引用 | PASS（重跑） | checks 22; skills 10 | engine=local |
| tier2 路由评测（development） | PASS（复用 2.0.0） | accuracy 1.00 (32/32) | 子 Skill 描述与 2.0.0 评测输入逐字节一致 |
| tier2 路由评测（held-out） | PASS（复用 2.0.0） | accuracy 1.00 (32/32) | 同上 |
| tier3 行为评测（development/held-out） | PASS（复用 2.0.0） | skill 1.00; non-regression true | 行为类 Skill 文本未变 |
| tier3 方法论评测（development） | PASS（重跑） | skill 1.00; baseline 0.67; non-regression true | engine=agent; model=claude:default |
| tier3 方法论评测（held-out） | PASS（重跑） | skill 1.00; baseline 0.67; non-regression true | engine=agent; model=claude:default |
| 结构校验 | PASS | 97 个公共文件 | local |
| 敏感信息扫描 | PASS | findings 0 | local |
| 公共包清单复验 | PASS | files 97；双 manifest 一致且各自复验通过 | local |
| 独立判定 | PASS | 增量范围与复用理由被独立复核接受 | engine=agent; model=claude:default |
| 独立终审签署 | PASS | errors 0; not-proven 0 | local |

### 2.0.0 评测摘要

| 门禁 | 结论 | 关键指标 | 审计元数据 |
| --- | --- | --- | --- |
| tier1 结构、预算与资源引用 | PASS | checks 22; skills 10 | engine=local |
| tier2 路由评测（development） | PASS | accuracy 1.00 (32/32); 最低 0.90 | engine=agent; model=claude:default |
| tier2 路由评测（held-out） | PASS | accuracy 1.00 (32/32); 最低 0.90 | engine=agent; model=claude:default |
| tier3 行为评测（development） | PASS | skill 1.00; baseline 1.00; non-regression true | engine=agent; model=claude:default |
| tier3 行为评测（held-out） | PASS | skill 1.00; baseline 1.00; non-regression true | engine=agent; model=claude:default |
| tier3 方法论评测（development） | PASS | skill 1.00; baseline 0.00; non-regression true | engine=agent; model=claude:default |
| tier3 方法论评测（held-out） | PASS | skill 1.00; baseline 1.00; non-regression true | engine=agent; model=claude:default |
| 结构校验 | PASS | 93 个公共文件 | local |
| 敏感信息扫描 | PASS | findings 0; scanned 94/94 | local |
| 公共包清单复验 | PASS | files 93；双 manifest 一致且各自复验通过 | local |
| 独立判定 | PASS | 评测证据完整、无阻塞项 | engine=agent; model=claude:default |
| 独立终审签署 | PASS | errors 0; not-proven 0 | local |

提示词与 schema 指纹、逐案例明细保留在内部评测目录；本表由 `scripts/summarize_evaluations.py` 生成。
| 1.2.0 – 1.3.1 | 2026-08-29 | 未发布公开摘要 | 同构门禁已在内部完成；公开摘要机制自 1.4.0 起生效 |

### 1.4.0 评测摘要

| 门禁 | 结论 | 关键指标 | 审计元数据 |
| --- | --- | --- | --- |
| tier1 结构、预算与资源引用 | PASS | checks 22; skills 10 | engine=local |
| tier2 路由评测（development） | PASS | accuracy 1.00 (32/32); 最低 0.90 | engine=agent; model=claude:default |
| tier2 路由评测（held-out） | PASS | accuracy 1.00 (32/32); 最低 0.90 | engine=agent; model=claude:default |
| tier3 行为评测（development） | PASS | skill 1.00; baseline 1.00; non-regression true | engine=agent; model=claude:default |
| tier3 行为评测（held-out） | PASS | skill 1.00; baseline 1.00; non-regression true | engine=agent; model=claude:default |
| tier3 方法论评测（development） | PASS | skill 1.00; baseline 0.67; non-regression true | engine=agent; model=claude:default |
| tier3 方法论评测（held-out） | PASS | skill 1.00; baseline 1.00; non-regression true | engine=agent; model=claude:default |
| 结构校验 | PASS | 87 个公共文件 | local |
| 敏感信息扫描 | PASS | findings 0; scanned 88/88 | local |
| 公共包清单复验 | PASS | files 87；双 manifest 一致且各自复验通过 | local |
| 独立判定 | PASS | 评测证据完整、无阻塞项 | engine=agent; model=claude:default |
| 独立终审签署 | PASS | errors 0; not-proven 0 | local |

提示词与 schema 指纹、逐案例明细保留在内部评测目录；本表由 `scripts/summarize_evaluations.py` 生成。

## 证据边界

- 本页与摘要不构成对任何真实小程序项目的验收、平台审核通过或正式发布证据。
- 评测夹具均为匿名合成材料；真实来源项目不参与技能验证，避免循环验证。
- 评测结论只覆盖当批用例与夹具；不得推广为「套件在所有任务上有效」。
