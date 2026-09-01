# Changelog

本文件记录公共套件能力变化。版本标题表示套件已通过对应冻结门禁，不代表已经安装到任何全局目录或发布到外部平台。

## 3.1.11 - 2026-09-01

### Fixed（正式运行回读整改）

- 修复 coverage.py 7.10.7 JSON 兼容：覆盖率门禁不再读取版本间不稳定的展示字段，改由 `covered_lines / num_statements` 精确计算全仓语句覆盖率，仍严格执行 ≥85% 门槛。
- 修复 Release 发布说明中两条 Python 单行命令的 f-string 转义语法错误，改用 `str.format` 读取 SemVer 与评测门禁摘要；发布资产、摘要内容和门禁语义不变。
- 新增两项工作流契约回归，分别禁止重新引入不稳定覆盖率字段和带反斜杠的 f-string 表达式。
- v3.1.10 的本地 release gate、Python 3.9/3.11/3.13、Shell/YAML、安装器和敏感扫描探针均通过，但正式 CI 覆盖率作业与 Release 创建步骤因上述工作流错误失败，且未创建 GitHub Release；已公开标签不重写，本次修复顺延到 v3.1.11。

### Release boundary

- 本版本只修改工作流、契约测试、版本与发布文档，不改变九个子 Skill 行为正文或评测基架；继续复用 v3.1.2 的完整八阶段 PASS 证据，并为 v3.1.11 单独生成签名证明。

## 3.1.10 - 2026-09-01

### Fixed（质检整改与正式放行链）

- 评测门禁升级为 RSA/SHA-256 签名证明：声明严格绑定候选 tag、历史来源 tag/commit、八阶段 PASS 证明、行为指纹与评测基架指纹；缺字段、错 stage、错版本、错 commit、错指纹、签名篡改和无历史证明全部 fail-closed。
- 修复根 `SKILL.md` 元数据豁免绕过：只有 frontmatter 的 `version` / `last_reviewed` 变化且正文逐字节不变时才允许复用。
- Release 从干净 checkout 读取 `.github/release-evidence/v<version>.json`，不再依赖被 `.gitignore` 排除的本机 `.planning` 文件；私有逐案例产物继续不进入公共包。
- SemVer 人工降级必须通过可信公钥验签，且签署人与候选提交作者不得相同；任意填写 `signed_by` 不再有效。
- CI 安装固定版本 PyYAML；敏感扫描探针覆盖 GitHub/AWS/npm/PyPI/Slack/腾讯/Google/微信全部规则；覆盖率使用父进程与 Python 子进程合并采集，真实执行全仓语句 ≥85%、核心门禁模块分支 ≥90% 门槛。
- Release 改为先创建草稿并附齐全部资产，再发布为不可变 Release；发布后 API 复核仓库和该 Release 的 immutable 状态。
- 安装器临时目录、跨平台漂移报告、Python 3.9/3.11/3.13 矩阵与通用凭证扫描修复一并纳入本版正式验证。

### Release boundary

- 本版本不改变九个子 Skill 行为正文与评测基架，评测语义复用最近一份完整八阶段 PASS 证据；复用来源、私有产物摘要哈希和候选双指纹由签名证明清单绑定。

## 3.1.9 - 2026-08-31

### Fixed（codex 九次复核：浅仓库语义全路径收口）

- `release_recommendation.recommend()` 的浅仓库检查提升为候选/无候选共用门禁；depth-1 checkout 不再把整个仓库误分类为本轮 behavior/data/assets/tooling/docs，也不再错误写出 `history_complete=true`。
- drift-watch 的 audit job checkout 改为完整历史，使审计 issue 中的“当前发布建议”基于上一 tag 到 HEAD 的真实变更；detect job 保持轻量 checkout。
- 无新提交的 `HOLD` 返回补齐 `history_complete=true`；`recommend()` 入口统一接受 `Path` 与字符串路径，消除直接调用时的路径运算异常。
- 新增 4 项回归：无候选浅 clone fail-closed、完整历史 HOLD 字段、字符串路径兼容、drift audit 完整历史配置。连同 v3.1.8 后首批 7 项回归，本版本测试总数由 173 增至 184。

### Release boundary

- 本版本不改平台事实与九个子 Skill 行为正文；不重复运行 tier2/tier3，正式发布证据以本 tag 的 `gate-summary.json`、SHA256 和 113 文件接收端复验为准。

## 3.1.8 - 2026-08-31

### Fixed（codex 七次复核批：1 P0 + 2 P1 + 2 P2 + 1 优化项，P0 为正式发布路径门禁绕过）

- **P0 正式 Release 中人工核验门禁被整体绕过**：Release checkout 候选 tag 后，`git describe` 把候选自身当作上一版 → 候选..HEAD 零提交 → HOLD → gate 放行，核验门从未执行（v3.1.7 Release 日志证实无核验判定输出）。修复：候选 tag 场景下 baseline 改为 `git describe --tags --abbrev=0 候选^`（真上一版）+ 候选 tag commit 必须等于 HEAD + 候选区间零提交视为异常直接 `MANUAL_VERIFICATION_REQUIRED`（不再 HOLD 放行）；release_gate.sh 对 **HOLD+候选 tag 阻断**、未知 recommendation 值 fail-closed。CHANGELOG 证据裁剪修正（版本头无尾随空格时匹配失败导致读了旧版证据）。隔离仓四场景验证（缺证据拦/齐证据过/HEAD 不符拦/无候选本地 HOLD 保持）+ gate verdict 分支 6 项 shell 测试。
- **P1 四元组内部错位可通过**：强制 `update.fact_id == 外层键 == rule_id` 三者全等（codex 探针 DIFFERENT-INNER-ID 原可过）；提案顶层拒绝重复 `rule_id`（重复 change 原可通过）。类型层短路修正：unknown-rule / verify-points 绑定 / fact-id 集 / statements 比对四项独立于 updates 形状报告，不再被类型问题遮蔽。
- **P1 重复规则 ID 不被拒**：validate 新增 `seen_rule_ids`（同 ID 两规则原只靠 URL 错位间接拦）+ 重复 `verify_points` 拒绝；七格回归矩阵全绿（重复规则/重复事实/孤儿/缺失/URL 错位/重复核对点/合法）。
- **P2 gate-summary 缺第四道门**：summary 现写入 candidate_tag / baseline_tag / release_recommendation / manual_verification_required / 各平台核验状态——哪版、比哪版、缺哪个平台、多少 unknown 一目了然。
- **P2 文档口径**：CHANGELOG/EVALUATIONS 测试数以 Release 工件为准修正（161→167）；18 号报告删除上一版失实的「门禁首次实战拦截」表述并如实更正（拦截仅验于本地路径，正式 Release 未执行核验——与"空壳指纹"同类的 A 路径验证冒称 B 路径问题）；15 号清理"自动开 PR""影子模式观察期"残留。
- **优化**：`review_guarded` 异常兜底输出异常类型到 stderr（公开码保持脱敏，真实缺陷与恶意输入可区分）；删除 validate 死导入。

### 平台核验（本批）

- alipay facts 人工核验于 2026-08-31 (tag: v3.1.8)
- douyin facts 人工核验于 2026-08-31 (tag: v3.1.8)

（本批复核两平台 facts 无内容变化，核验沿用 2026-08-31 实核结论；证据行 tag 指向本版候选。）

### 验证

- 173 测试全绿（+6：gate verdict 分支 5 项 + P1-1 两负例并入既有探针组）；`-W error::ResourceWarning` 零警告；validate 113 文件；扫描 0 命中；i18n 6/6；导出复验 113 文件；summary 第四道门字段实测写入；**真实失败路径验证见发布说明**（临时 tag 删证据 → Release 必须失败后清理）。

## 3.1.7 - 2026-08-31

### Fixed（codex 六次复核批：3 P1 + 2 P2 + 1 P3 全部修复，按其建议顺序）

- **P1-1 抖音事实标注与规则地图失联**（3.1.6 漏改 facts 机器注释所致）：privacy-protection 注释补指配置隐私协议页。结构性修复：`validate_facts_rule_map_binding` 新增 facts/rule-map 交叉校验——按 **fact.id == rule.id** 强绑定（不再按 URL 推导），fact.source 必须等于 rule.official.url，拒绝孤儿事实/无事实规则/重复 ID。微信旧布局（一规则多事实）一并对齐：release-review-operations 拆分为 operations-spec-scope 与 review-rejection-flow 两条规则，privacy-protection-declarations 更名 privacy-guideline-required，三平台全部 1:1。篡改任一事实 URL → validate 非零 → Release gate 阻断。
- **P1-2 gate2 允许跨规则替换**：codex 探针（r1 陈述+r2 URL/fact）实测穿透。修复：**rule_id 为唯一入口**——change.rule_id → rule-map 规则 → official.url → 同 ID 事实，提案自报的 URL/fact 必须与 rule-map 推导一致，不一致报 `official-url-not-bound-to-rule` / `fact-source-not-bound-to-rule` / `unknown-rule`。
- **P1-3 核验证据错误放行（三处）**：证据改为**按平台独立结构** {platform: {date, tag}}（一条 douyin 不再覆盖 alipay）；证据 tag 必须等于**候选 tag**（`--candidate-tag`，release.yml 传 RESOLVED_TAG；不再把当前 tag 当比较基线）；证据日期必须与该平台 facts.md 全部 verified 一致。合并写法「alipay/douyin facts 人工核验于…」同时为两平台记证据。**接入 release_gate.sh 第四道门**：`MANUAL_VERIFICATION_REQUIRED` / 建议器崩溃 / 解析失败 → 非零退出阻断发布（模拟仓库实测拦截生效；合法双平台证据放行）。平台目录缺失的树（夹具）视为无核验对象，结构完整性由 validate_suite 保证。
- **P2-1 gate2 畸形输入崩溃/静默放行**：`_contract_types_valid` 类型门禁先行——requested_verify_points 必须非空字符串列表且无重复（原重复项被 set 去重后放行）；proposed_fact_updates 必须对象且每项字段集精确匹配四元组、字段非空字符串（原传列表触发 `TypeError: unhashable` 崩溃）。`review_guarded` 异常兜底：任何意外输入统一 `DO_NOT_APPLY + gate2:proposal-contract-invalid`，审计器不再可能 traceback。null/数字/嵌套/列表/重复/空串全负例实测拒绝且进程不崩。
- **P2-2 文档自相矛盾**：15 号第五/六/七节整体重写为现行人工裁决模式（裁决词表、作者动作、诚实边界、门禁地位），旧自动合并设计移入「历史设计（已废弃，不得执行）」章节；正文残留 RECOMMEND_MERGE/自动合并进 main 全部清除（仅存于带废弃横幅的历史章节）。18 号报告速览更新至 3.1.6 终态。
- **P3 测试临时目录泄漏**：夹具提取为模块级函数 `prepare_proposal_fixture` / `build_default_proposal`（不再手动实例化 TestCase——其 addCleanup 永不执行）；`tearDown` 统一清理，`-W error::ResourceWarning` 下全套测试零警告。

### 平台核验（本批）

- alipay facts 人工核验于 2026-08-31 (tag: v3.1.7)
- douyin facts 人工核验于 2026-08-31 (tag: v3.1.7)

（alipay 沿用 2026-08-30 首验结论，本批复核 facts.md 内容无变化，verified 日期统一记 2026-08-31 与证据行对齐；douyin 为二次核验：privacy 页更新时间 2026-08-28 已复核。）

### 验证

- 161 测试（Release 工件实测 167，含 +6 V317 回归）；validate 113 文件（含新交叉校验）；扫描 0 命中；`-W error::ResourceWarning` 零警告。**更正（codex 七次复核）**：原记「release_gate.sh 带候选 tag 实测：缺证据→阻断」仅验于本地（HEAD 领先 tag 的场景）；正式 Release 工作流 checkout 候选 tag 后 `git describe` 将候选自身当作上一版 → 零提交 → HOLD → gate 放行，**核验门在正式路径被整体跳过**（v3.1.7 Release 未执行核验判定）。该 P0 已在 3.1.8 修复。

## 3.1.6 - 2026-08-31

### Fixed（codex 五次复核批：3 P1 + 4 P2 + 1 P3 全部修复）

- **P1 gate2 契约绑定不完整（提案可篡改通过）**：原 gate2 只比 state+fingerprint。codex 探针（FAKE_POINT 替换核对点 + 捏造 unknown-fact）实测穿透。修复：完整契约六维绑定——requested_verify_points == rule-map 的 verify_points；extracted_statements 与漂移报告逐字一致；proposed_fact_updates 键集 == 该规则关联事实集（unknown-fact 拒绝）；更新结构严格为 fact_id/current_text/proposed_text/source_digest 四元组；current_text == facts.md 记录的事实原文（load_fact_annotations 现抽取「- 事实：」行文本）；source_digest == fingerprint == 报告指纹。篡改探针回归锁定（DO_NOT_APPLY + 三类问题码）。
- **P1 核验门禁不能识别"本轮已核验"**：原实现读 facts.md 日期，major 即使当天核验仍报 required。修复（方案 a）：核验证据绑定 CHANGELOG——本发布周期条目内的「alipay/douyin facts 人工核验于 YYYY-MM-DD (tag: vX.Y.Z)」满足要求，仅有历史日期不满足；`changelog_verification_evidence` 按 since_tag 裁剪读取。另一缺陷同修：`classify_commit` 改为返回完整分类集合（`classify_commit_classes`），scripts+facts 混合提交不再丢 data 触发（codex 探针实测）。
- **P1 运维文档反向指导**：16 号教程加废弃声明（自动合并路径已永久移除、`--no-shadow` 不存在，旧章节仅作历史背景）；15 号状态行更新至 v3.1.5 语义（人工裁决词表）。
- **P2 抖音核验记录事实错配**：官方隐私保护标准实为 **28 条**（此前误记 12 条系抓取截断，浏览器重数修正）；privacy-protection 从误挂审核标准页改指专门的「配置隐私协议」页（控制台路径、三种授权方式、未配置限制接口调用），verify_points 同步更新，verified=2026-08-31。
- **P2 release tag 多行绕过**：grep 逐行匹配被 `v1.2.3\nINJECTED=1` 穿透（实测）。改 bash `[[ =~ ]]` 整体变量匹配 + 显式拒 CR/LF；测试改为真实 subprocess bash 管道（十种注入形状含多行全部拒收）。
- **P2 提取器错位嵌套吞正文**：codex 探针（噪声区未闭合 `<span>` 导致外层永不弹出、全文被吞）实测复现。改栈扫描弹出：闭合标签在栈内查找并弹到该位置（丢弃其上未闭合项），未闭合不再阻断外层闭合；全套既有探针（杂散闭合/同标签嵌套/深嵌套/void/变化敏感）回归通过。
- **P2 文档状态矛盾**：platforms/README「verified=unknown 种子占位」过时表述更新为已核验；14 号当前版本行、18 号报告结论速览重写为 v3.1.5 终态。
- **P3**：HTTP 测试补 `server_close()`。

### 平台核验（二次）

- **douyin facts 人工核验于 2026-08-31 (tag: v3.1.6)**：隐私配置改指专门文档页并核验（更新时间 2026-08-28）；发布审核要求确认位于版本审核标准页（隐私标准 28 条）。

### 验证

- 161 测试全绿（+5 回归：篡改提案三问题码/合法提案通过/混合提交保 data 类/本轮 CHANGELOG 证据满足 major·缺证据拒绝/未闭合 span 正文可感知）；validate 113 文件；扫描 0 命中；i18n 6/6；导出复验 113 文件；注入防护测试含真实 bash 多行探针。

## 3.1.5 - 2026-08-30

### Fixed（codex 三次复核批：4 项 P1 残留 + 6 项 P2 残留全部修复，含一项根因再深挖）

上轮「17 项全部闭环」结论被 codex 复核推翻（4 P1 + 6 P2 残留）。本批按用户裁决方案执行：9 项确定性修复 + Gate5 按方案 A 重构 + manual-only 政策落地核验。

- **P1 L2 未绑定请求点与返回点**：`_extract_payload_valid` 现要求返回点集合与请求点**完全一致**（数量+内容），缺项/替换（UNREQUESTED）/额外项/重复项全部拒绝（负例实测原探针 `UNREQUESTED` 替换已拒收）。
- **P1 Gate5 无法证明对官方忠实**：按方案 A 重构为诚实语义——`current_statements` 更名 `extracted_statements`（明确模型抽取物非官方原文）；提案新增 `proposed_fact_updates`（审计有了具体对象）；裁决词表改为 `PROPOSAL_CONSISTENT_WITH_EXTRACTION` / `DO_NOT_APPLY`（全仓清除 RECOMMEND_MERGE/DO_NOT_MERGE）；`--no-shadow` 移除（无自动合并路径）；issue 文案明确「一致性≠官方事实，合并前必须作者核对官方页面」。数据契约：official_url+fingerprint / requested_verify_points / extracted_statements / proposed_fact_updates / consistency verdict；manual approval 为独立人工动作。
- **P1 release.yml tag 注入**：tag 经 `env: RAW_TAG_INPUT` 传入 + 严格正则 `^v[0-9]+\.[0-9]+\.[0-9]+$`（bash 探针实证原 `case v*` 可被 `v"; cmd; #` 注入）；新增 `tests/test_workflow_injection_guards.py`：禁止任何 `${{ }}` 出现在 run: 脚本体（含 steps.context）、注入形状全部拒收。顺带清除 `steps.release.outputs.tag` 内插残留。
- **P1 manual-only 政策未履行**：本批完成首次人工核验（见下方「平台核验」）；政策更新为分级节奏（major 必核/minor 90 天或涉事实变更/patch 仅涉相关事实）并工具化：`release_recommendation.py` 新增 `manual_verification_status`，到期未核验输出 `MANUAL_VERIFICATION_REQUIRED` 不得静默通过。
- **P2 提取器杂散闭合标签**：重写为完整解析栈（void 标签不入栈；end tag 仅匹配栈顶才弹）。codex 探针 `<div class="nav"></p>SECRET</div>` 已不再泄漏。
- **P2 安装器非完整事务**：改为本轮事务日志 + 逆序全量回滚（所有已改目标，不只当前）；备份仅使用本轮记录路径（不再搜索历史「最新备份」）。实测中途失败：已装目标恢复旧版、fresh 目标移除。
- **P2 i18n 缺失检测失效**：版本徽章与 tar 命令改为**必须存在**（删光即报错）；四语言 README 补齐版本化 tar 命令块。
- **P2 Issue 创建失败被吞**：drift_watch 与 drift_audit 的 `emit_issues` 失败均传播非零退出码（CI 显性失败，不再静默漏报）。
- **P2 FAITHFULNESS_SCHEMA 未执行**：`_audit_payload_valid` 真实执行（缺 reason/空 reason/非法枚举/额外字段全拒；原探针 `{"faithful":"faithful"}` 形状已随词表更新为 consistent 枚举并严格校验）。
- **P2 跨文件锚点**：validate_links 新增跨文件锚点校验（`file.md#section` 对目标文件标题解析；修复 /tmp 符号链接别名导致字典键不一致的缺陷）。
- **P2 内部文档旧状态**：06 号笔记已标注为历史快照并指向现行基线文档。

### 平台核验（本批首次人工核验，2026-08-30）

- **alipay facts 人工核验于 2026-08-30**：发布流程页（上传→提审 2 工作日双审→灰度→上架→回滚）证实仍准确；**隐私文档 URL 已失效**（03l9bt 现为 API 页），迁至 03lwro（提审前必须配置隐私政策；2025-04 新增第三方插件/SDK 信息功能），facts 与 rule-map 已修正。
- **douyin facts 人工核验于 2026-08-30**：**原两个 URL 均 404**；现行结构为「经营→版本审核」分组，版本审核标准页含完整隐私保护标准（12 条），facts 与 rule-map 已修正指向。
- **微信基线重录（根因再深挖）**：修复提取器后复跑出现 3 条告警，深挖发现**旧提取器在真实微信页面上把正文几乎全部吞掉**（噪声 div 无配对闭合导致栈永不弹出，可见文本仅 6-21 字符）——旧基线 digest 实为「空壳指纹」，从未真正监测正文。新提取器下三页正文完整提取（3.3 万/1366/273 字符），基线已用新算法重录，同页双跑逐字一致。

### 验证

- 156 测试全绿（+9 新回归：点集绑定四种负例/杂散闭合标签/审计 schema 五种形状/契约必含 proposed_fact_updates/核验门禁/i18n 存在性/跨文件锚点/注入防护四项）；validate 113 文件；扫描 115 候选 0 命中；i18n 6/6 含存在性检查；导出复验 113 文件；foundation 等价 PASS；drift-watch 0 告警（基线重录后）。

## 3.1.4 - 2026-08-30

### Fixed（上线前质检第二批：5 项延期加固全部落地）

3.1.3 批中排为「下一版」的 5 项 P2/升级项本批完成，上线前审计（7 P1 + 10 P2）至此**全部处置完毕**（含证伪与流程项）。

- **P2 第三方 Actions 固定到不可变提交 SHA**：checkout@v7.0.1 → `3d3c42e`、setup-python@v7.0.0 → `5fda3b9`、upload-artifact@v4 → `65c4c4a1`（v4.6.0）、download-artifact@v4 → `d3f86a10`（v4.3.0），三个 workflow 全部固定并注明原版本号，SHA 经 GitHub API 逐 tag 解析（annotated tag 取其指向 commit）。
- **P2 接收端绑定 manifest 版本与 VERSION**：新增 `check_version_binding`——manifest `suite_version` 必须与包内 VERSION 文件一致，否则 `version-metadata-mismatch` 拒绝；manifest 缺 VERSION 条目也判 invalid。篡改负例实测：改 manifest 版本号 → valid=false。+3 单元回归（匹配通过/不匹配拒绝/缺文件拒绝）。
- **P2 安装器多目标事务性**：安装前对全部目标做预检（存在性冲突、父目录可创建、可写），任一失败即「零目标被改动」退出；复制失败自动回滚该目标（删半成品、恢复本次备份）。实测：单目标冲突时其余目标不被触碰；正常路径三目标齐装且版本正确。
- **升级项 敏感扫描文件大小上限**：>32MB 文件不再无界 `read_bytes`，改为报 `oversized-file` finding（fail-closed，提示拆分或显式上调阈值）。当前仓库最大资产 4.4MB，阈值留 7 倍余量。负例实测：超限文件触发 finding；全仓扫描仍 0 命中。
- **P2 文档校验覆盖不足**：i18n 校验新增跨语言事实对齐——六个 README 的徽章版本与 tar 包命令中的版本必须与 VERSION 文件一致（漂移或缺失均报错）。负例实测：单语言 README 版本回退 → valid=false 并指明文件与漂移值。

### 验证

- 143 测试全绿（+3 版本绑定回归）；validate 113 文件；扫描 115 候选 0 命中；i18n 6/6 含新事实对齐；导出复验 113 文件 valid；安装器正/负路径实测；3.1.3 批 CI 绿（a40fcc3）。

## 3.1.3 - 2026-08-30

### Fixed（上线前质检交叉验证批：10 项实修，1 项证伪免修）

上线前审计（codex 产出、zcode 逐项交叉验证）判定 7 项 P1 阻塞 + 10 项 P2。交叉验证后确认 5 项 P1 属实、1 项降级、1 项基本证伪（README 早已如实标注支付宝/抖音 manual-only）；P2 中 HTML 提取器缺陷升格必修。本批修复 10 项，另有关键实证：**12:35 CI 检出的「3 条微信漂移」全部为提取器假阳性**（见 P2-1 条目）。

- **P1 忠实性审计无证据（gate5 空转）**：审计提示词要求对比「提案与源摘录」，但提案只含 digest/规则 ID，从无摘录——结构上不可能做出判断（当天 CI 实测 `agent-output-not-json` 旁证）。修复：L2 抽取的逐点 `current_statements` 写入提案与漂移报告，审计 prompt 现在携带真实 SOURCE EXTRACTS，只把元数据（rule_id/state/reason/not_stated_points）交审计对比；缺摘录即 `no-extracted-statements` fail-closed，不再无证据放行。gate3 同步要求提案必须携带非空 `current_statements`（含长度上限 2000 字符/条），防页面正文伪装成证据。
- **P1 L2 Schema 只定义未执行**：`EXTRACT_SCHEMA` 全仓库零引用，实际仅查顶层 dict/list。修复：`_extract_payload_valid` 真实执行 schema（键集合精确匹配、逐条类型与空值、重复点拒绝），畸形输出统一降级 `extract-output-shape-invalid`，不再可能以 KeyError/TypeError 崩溃审计进程。
- **P1 skip-audit 开关失效**：`github.event.inputs.*`（字符串）与布尔比较恒真——历史上两次修复（`!` 取反 → `!= true`）方向都错。修复：改用 `inputs.skip-audit`（保真布尔），注释记录教训。
- **P1 工作流注入面**：`platform` 输入直接内联进 `run:` 脚本体。修复：经 `env: PLATFORM_INPUT` 传入 + `wechat|alipay|douyin` 白名单 case 校验，未知值 exit 2（drift-watch 两处；release.yml 的 tag 本就有 `v*` 前缀校验且不拼接入脚本命令，维持现状）。
- **P1 基线未裁决 → 实证结案，无需重置**：CI 运行 33311630155 检出 3 条 `fingerprint-changed`、Issue #2–#5 关闭后基线未动，曾判定「下次定时任务必然复发」。**提取器修复后本地实跑：3 条全部 `unchanged`，新算指纹与 facts.md 已记录 digest 逐字一致（同页两次抓取稳定复现）。结论：检出是提取器噪声泄漏制造的假阳性，基线本身正确。**
- **P2-1 升格 HTML 噪声跳过同标签嵌套缺陷（本批根因）**：外层 `class="nav"` div 内出现普通 div 时，内层 `</div>` 会提前弹出外层跳过态，导航噪声泄入指纹——正是上述 3 条假阳性的根因。修复：跳过态内所有 start tag 压入影子标记（None），end tag 与 start tag 一一配对；杂散闭合标签只弹影子标记。
- **P2-2 重定向白名单缺口**：`urlopen` 默认跟跳转，最终目标可离开允许域且 L2 会把内容送外部引擎。修复：`AllowlistRedirectHandler` 逐跳校验，越域即 `redirect-off-allowlist:<domain>` fail-closed；异常捕获顺序修正（RedirectBlocked 是 URLError 子类，须在前，且从被包裹的 reason 中还原该错误）。本地 HTTP 服务器真实 302 集成测试验证。
- **P2-7 审计通知链兜底（残留半项）**：audit job 新增 `always()` 上传 `audit-out` 工件（结构化 verdict 长期保留），运行后缺 `audit-summary.json` 即非零退出。
- **P1-2 rounds 绕过**：`--rounds 0` 使审计循环空转、确定性门禁通过即 RECOMMEND_MERGE。修复：rounds<1 直接 `DO_NOT_MERGE` + `rounds-below-minimum:1`。
- **P1-7 残留**：平台上报 Issue 模板下拉仅 wechat，补 alipay/douyin 选项（README 口径本身已如实，无需改）。
- 证伪免修：三平台产品口径超标——README 早已写明「支付宝与抖音…如实标注为 manual-only…不假装能自动检测」，审计建议的修复内容即现状，无代码可改。

### 验证

- 140 测试全绿（+5 回归：rounds=0 拒绝、缺摘录 fail-closed、嵌套噪声不泄漏、深/错位嵌套存活、真实 302 越域拦截）；drift-watch 本地实跑 actionable_count=0（修复前同日为 3）；结构校验 113 文件；扫描 115 候选 0 命中；导出复验 113 文件 valid。
- 指纹稳定性实验：同页两次抓取（间隔 2s）指纹逐字一致且与 facts.md 基线一致——证明修复后基线可长期稳定，非碰巧匹配。

## 3.1.2 - 2026-08-30

### Fixed（codex 二次复核新注意项）

- Release gate 失败路径三态分离：validate/scan 在正常门禁失败时就是「输出 JSON + 返回 1」（如 valid=false、finding_count>0），此前被误标为 "crashed" 且 gate-summary 不落盘——失败证据丢失且误导排障。重构 release_gate.sh：`set +e` 捕获 stdout+rc → 先解析 JSON → **失败也必写 summary**（哪道门禁拦的、数字多少）→ 按 valid/finding_count 阻断；只有非 JSON 输出才判 crashed（且不伪造 summary）。四场景实测：JSON 失败（写 summary+报 gate failure）、工具崩溃（报 crashed+无 summary）、单测失败（先拦）、真实仓库全绿（rc=0）。
- 回归测试名实相符：`test_green_run_writes_complete_summary` 实际测的是夹具阻断路径（codex 指出的措辞偏满），改名 `test_fixture_repo_blocks_on_invalid_suite_and_writes_summary`，docstring 注明真实绿跑证据位于 Release 工件与 EVALUATIONS.md；新增崩溃路径回归（非 JSON 报 crashed、不伪造 summary）。

### 验证

- 135 测试全绿（+1）；真实仓库 gate 实跑 rc=0、summary 135/113/0；结构校验 113 文件；i18n 6/6；扫描 0 命中；foundation 等价 PASS；导出复验 113 文件。

## 3.1.1 - 2026-08-30

### Fixed（codex 复核报告两项注意，交叉验证后修复）

- repo-only 源图扫描空窗（复核报告注意 1，zcode 深挖加重为 P1.5）：v3.1.0 曾把封面源图加入 SKIP_EXACT_PATHS——经实验证实这不是冗余规则而是实质扫描空窗（1.4 版起二进制资产走 latin-1 逐字节扫描，移除该规则后源图可被扫出文本形态敏感信息，实测 findings=0）。修复：删除该跳过规则恢复完整覆盖（扫描候选 112→115），validate_suite 注释同步改真；源图仍不进公开包。
- Release 门禁缺已提交回归测试（注意 2）：门禁 shell 从 release.yml 内联段抽为 `scripts/release_gate.sh`（workflow 调用之，行为不变），新增 `tests/test_release_gate.py` 五项回归锁定三种失败形态（单测失败、`Ran 1 test` 单数解析、零测试数）与崩溃路径。抽取过程顺带加固：validate/scan 自身崩溃（非 JSON 输出）现在以明确原因阻断发布，而非隐性 traceback。
- 过程记录：新脚本首次提交时被自家 fail-closed 白名单拦截（release_gate.sh 未在 REQUIRED_FILES）——#14 同款模式，循环检查在本地即拦截。

### 验证

- 134 测试全绿（+5 门禁回归）；真实仓库 gate 实跑 rc=0、summary=134 tests / 113 files / 0 findings；结构校验 113 文件；i18n 6/6；扫描 115 候选 0 命中；foundation 等价 PASS；导出复验 113 文件且源图不入包。

## 3.1.0 - 2026-08-30

### Fixed（codex 全面审计交叉验证批，4 问题项全实证后修复）

- **Release 门禁吞单测失败（P0）**：`release.yml` 门禁步骤补 `set -e`；单测管道显式取 `PIPESTATUS[0]` 断言退出码（实测失败被拦截）；`Ran N tests` 解析修单复数（失败输出含 `Ran 1 test` 单数形态，原先匹配为空使 `tests_passed` 变空串进工件）。
- drift_watch 文档与 CI 行为不一致：docstring 改为如实描述「检测恒为确定性；L2/审计在 drift_audit，CI 用 AGENT_API_* Secret 或本地引擎，Secret 缺失降级仅检测」。
- `--no-llm` 语义不真实：该参数原本只改报告 `mode` 字段（`full` 是谎）；现 mode 恒为 `deterministic` 并新增 `llm_stage` 字段指明 L2 归属。
- capability doctor 的 uni-app 判定子串误判：`"uni" in value` 会把 `npm run unit`、`community-modules` 误判为 uni-app（实测坐实）；改为词边界正则，正负向回归测试入套件。

### Fixed（优化项，实证后采纳）

- **HTML 抽取 skip-depth 过度跳过（保鲜漏报）**：扁平计数器遇 `<span class="nav">` 会吞掉其后全部正文（实证：内容变化指纹不变）；改为标签栈精确配对，噪声剥离与 script 跳过行为保持，回归测试入套件。
- 封面源图灰区收口：`assets/readme-cover-2000x849-v2.webp`（定稿源图）改为显式 `REPO_ONLY_ASSETS` 类——被 git 跟踪、被结构校验（仅源码树要求），但**不进公开包**；exporter 前缀容忍规则收敛为精确路径（前缀规则会静默豁免未来未知文件）；修复过程中顺带消除了「repo-only 检查误用于导出包」的缺陷。
- Markdown 同文件锚点校验：`validate_links` 现解析标题 slug 并校验 `#anchor` 存在（篡改实验：坏锚点被拦截）；此前章节改名（如「平台规则保鲜」去版本后缀）会静默断链。

### Added

- manual-only 平台人工核验节奏（platforms/README.md）：minor/major 发布前人工核验、verified 更新为当日、CHANGELOG 记录核验日期、连续两版未核验由周报提示。

### 验证

- 129 测试全绿（+5 回归）；结构校验 112 文件；i18n 6/6；扫描 0 命中；foundation 等价 PASS；导出复验 112 文件且源图不入包；四组修复均含实证/篡改/负向验证。

## 3.0.1 - 2026-08-30

### Fixed（交叉验证台账批量修复 #2 #3 #4 #6 #7）

- #2：移除 `validate_suite.py` 中 `def validate` 空 docstring 桩（phase 4 改造残迹，双定义之一）。
- #3：六语言 README「平台规则保鲜」专节补齐——zh-Hant/ja/th/id 四份各补完整专节（原先仅 zh/en 有），并入 `check_i18n_readme_structure.py` 章节清单受结构校验保护，不可回退。
- #4：README.ja.md 两处中文词混入修正（スキル套件→スキルスイート；套件の記録→本スキルの記録；中文正式名称行保留）。
- #6：EVALUATIONS.md 三处 `skills 10` 加括注（根 Skill + 9 子 Skill），消除与 validate_suite `skill_count: 9` 的表述歧义。
- #7：新增 `platforms/README.md` 基线治理边界说明——「运行时保鲜门禁（永不写回）」与「基线刷新（工具实算 digest 走人工 PR）」两种操作的区别表、检测模式（确定性 vs manual-only）与事实标注规范；主 SKILL 链接之。终结每轮审计对「不写回声明 vs digest 存在」的表面冲突疑问。

### 验证

- 124 测试全绿；结构校验 112 文件；i18n 6/6（含新专节结构保护）；扫描 0 命中；foundation 等价断言 PASS。

## 3.0.0 - 2026-08-30

### Added

- 新增 `foundation/`（evidence-first-engineering 基础技能，领域无关、可独立分发）：SKILL.md（官方 frontmatter 契约）+ 4 份通用治理文档（证据状态模型、工程门禁、判断与确认规则、脱敏规则——其中脱敏规则做了声明式通用化：一处案例句去平台词）+ 4 份通用交付模板 + VALIDATE.md（结构自检与 vendored 同步规则）。
- 新增 `scripts/check_foundation_equivalence.py`：断言 foundation 与 shared/ 原版逐字节等价（声明的通用化差异白名单制，fail-closed）；已接入 `validate_suite.py`（篡改一个词即校验失败，实测验证）。
- 主 SKILL 能力地图新增「基础层」条目；本套件定位为该基础层的第一个垂直应用。

### Changed

- 引擎（agent_cli/指纹/审计）留在 `scripts/` 不迁 foundation：独立分发的依赖关系写在 VALIDATE.md（vendored 方自带等价引擎），避免为迁移而动评测基架 import 路径。
- shared/ 保留原文作为对照源与兼容层（不指针化）：等价性脚本保证不分叉，零既有引用改动。

### Compatibility

- 单仓安装、manifest 完整性、版本成组同步、fail-closed 出包全部不变；对安装者纯增量（foundation 随包分发）。

### Fixed

- 修复 drift 审计闭环三处行为偏差（v2.2.1 独立交叉验证发现）：① `drift_audit.py` 新增 `--report` 消费 detect 作业产物，审计范围以检测报告为准而非全量重扫；② audit 目标解析跳过 `manual-only` 平台（其 digest 恒为 unknown，`no-recorded-digest` 会触发对客户端渲染壳页注定失败的 L2 重试，每规则约 4 次引擎调用——显式 `--platform-dir` 指定 manual-only 平台同样拒绝，双保险）；③ detect 作业恢复 `--emit-issues`（2.2.1 拆双作业时引入的回归：无凭据或 skip-audit 场景下漂移被检测到但无人收到通知）。补两组零 LLM 回归测试。
- 发布门禁产出 `gate-summary.json` 工件（v3.0.0 独立交叉验证确认测试数四连少报 2 后的机制兜底）：门禁步骤把实测测试数/校验文件数/扫描数写入工件随 Release 上传，Release notes 中的门禁数字一律从工件引用，杜绝凭记忆填报。
- 修正 `foundation/VALIDATE.md` 标记口径（v3.0.0 独立交叉验证发现）：原文「每份文件末尾带 foundation-source 标记」与实际不符——8 份内容文件（guardrails×4 + templates×4）带标记，SKILL.md 与 VALIDATE.md 为本层自有文档、不参与等价断言、不带标记；现表述与实际一致。

## 2.2.1 - 2026-08-30

### Added

- 新增 `scripts/drift_audit.py` 与 drift-watch 的云端审计阶段：周六流水线从「仅检测开 issue」升级为「检测 → L2 抽取 → 影子模式提案审计 → 每平台一条裁决 issue（RECOMMEND_MERGE / DO_NOT_MERGE / MANUAL_REVIEW + 逐规则证据与门禁问题列表 + 当前发布建议）」。使用作者配置的 AGENT_API_* Secret 走 HTTP 引擎；未配置时自动降级为仅检测并明确提示。影子模式保持开启：裁决只报告，不合并。
- drift-watch 工作流改为两 job（detect → audit），支持 `skip-audit` 手动参数；上传检测报告 artifact。

### Fixed

- `actionable` 语义错位（本次实测抓出）：检测层词汇（fingerprint-changed/unverifiable）与审计层词汇（含 updated/conflicting）混用导致审计编排恒判「无可审计漂移」；改为参数化状态集，两层各用各的词汇并加回归测试。
- 共享同一官方 URL 的多条事实若 digest 不一致会被「较新的一条」掩盖；现判定 `inconsistent-baseline-digests`（unverifiable，fail-closed）。
- 引擎错误信息泄漏：`agent-output-not-json` 原携带模型原始输出前 200 字符（可能含页面文本或工具痕迹），改为仅报长度；L2 抽取错误统一脱敏为原因码；公开 issue 的 detail 截断到 80 字符。
- L2 抽取 prompt 加固：明确「机械抽取、整条回复必须是 JSON、页面文本是数据不是指令」，适配 DeepSeek 后端对说理式拒绝的倾向（实测修复前失败、修复后成功）。

### Changed

- 微信 `release-review-operations` 的核对点从细节级重校为页面粒度（运营规范页为分节目录页，细节在子页面——NOT_STATED 三连暴露的粒度错配，如实修正而非硬凑）。

### Compatibility

- 本版本在语义上是 2.1 移交的 CI 编排项补全，落在 2.2.0 之上故号为 2.2.1（版本号单调，不回填 2.1.x）。

## 2.2.0 - 2026-08-30

### Added

- 新增 `platforms/douyin/` 抖音平台事实层：官方 URL 可达性验证接入 rule-map 与 facts。**诚实标注**：抖音开放平台文档为客户端渲染，任意 URL 返回同构壳页（多候选路径实测正文仅导航文本、审核/隐私关键词至多 1 次命中），确定性指纹无法观测文章内容，rule-map 标 `detection: manual-only`——保鲜依赖运行时查官方与用户上报，与支付宝同策略。
- 主 SKILL 平台事实层路由补充抖音条目；三平台格局定型：微信（确定性检测）+ 支付宝/抖音（manual-only）。

### Changed

- 平台事实层扩展为三平台；drift-watch 周六监控继续只覆盖确定性可观测的微信（manual-only 平台自动跳过，零误报）。

### Fixed

- drift-watch 命令补 `--no-llm`（v2.1.0 独立交叉验证发现）：此前注释声明该 flag 但命令未带，L2 虽被运行时硬阻断、安全不受影响，但报告 `mode` 会错标 `full`；现注释、命令、报告三处一致。

## 2.1.0 - 2026-08-30

### Added

- 新增 `drift-watch.yml` 周频漂移监控（cron `0 2 * * 6` UTC＝北京时间周六 10:00，DeepSeek 周末低价时段；亦支持手动触发指定平台）。CI 只执行确定性 L0/L1 检查，不持有任何智能体凭证；发现指纹变化或不可验证项自动开带复现命令的 issue 引导本地 L2 审计。
- 新增 `scripts/drift_watch.py`：多平台批量确定性检查与 issue 编排；`manual-only` 平台自动跳过（避免每周误报）。
- 新增 `platforms/alipay/` 支付宝平台事实层：官方 URL 经可达性验证接入 rule-map 与 facts。**诚实标注**：支付宝文档中心为客户端渲染 SPA，不同页面返回字节级相同的 HTML 壳，确定性指纹无法观测内容变化，故 rule-map 标 `detection: manual-only`——该平台保鲜依赖运行时查官方与用户上报，不假装能自动检测。
- 主 SKILL 能力地图升级为平台事实层路由（按 doctor `target_platforms` 入口；未收录平台一律查官方并保持 unknown，不猜测）。
- 微信平台事实基线登记提案已生成（内部提案目录，不入公开包）：三条规则首次记录归一化指纹与核验日期，待作者批准写入 facts.md 后，周六监控将正确报 unchanged。

### Changed

- `drift-watch` 对 L2 的阻断从参数约定改为运行时硬阻断（L2Blocked），确定性模式保证零模型调用。

### Fixed

- 修复 `--no-llm` 模式仍触发 L2 引擎调用的缺陷（首次实测发现）；修复 drift_watch 编辑期产生的重复定义。
- 修复 capability doctor 把 Taro 项目 `dev:mp-weixin` 类脚本名误判为 uni-app 信号导致 `ambiguous` 的缺陷（v2.0.0 独立交叉验证发现）：脚本名不再参与 uni-app 判定，改以脚本值调用 uni CLI 为信号；补 Taro `dev:mp-weixin` 与 uni 脚本值两组回归测试。
- 微信平台事实基线经 `platform_drift.py` L0/L1 实测核验（三条规则全 unchanged，指纹与登记一致）后写入 `facts.md`：三条种子事实更新 verified/digest，新增 toolchain-devtools 事实。

## 2.0.0 - 2026-08-30

### Added

- 单仓三层分层架构：`shared/architecture-layers.md` 声明通用层 / 工程流程层 / 平台事实层边界与引用规则。
- 平台事实层 `platforms/wechat/`：微信平台事实单一事实源（证据层、核对清单、隐私矩阵从平台 Skill 迁入，git 识别为 100% rename）；`facts.md` 逐条核验标注（verified/source/digest，无标注视为 unverified）；`rule-map.json` 规则地图（步骤类 → 官方权威文档 → 核对点 → TTL → 域名白名单），全部 URL 经 L0 实测可达。
- 平台规则保鲜协议工具链：`platform_drift.py` 三级检查（L0 可达+标题 / L1 归一化文本指纹，永不哈希原始 HTML / L2 仅指纹变化时 extract-only 抽取）与四态 fail-closed 报告；`review_drift_proposal.py` 二元裁决审计器（4 道确定性门禁 + K 轮全票忠实性审计，影子模式默认开启）；`release_recommendation.py` 确定性发布建议器；`agent_cli.py` 新增 HTTP 引擎（OpenAI 兼容 API，与 CLI 订阅额度解耦）。
- 漂移上报通道：`.github/ISSUE_TEMPLATE/platform_drift.yml`（用户侧自愿上报，预填规则 ID/来源/差异）。

### Changed

- capability doctor v2：输出 `target_platforms`（uni-app manifest 键 / Taro 脚本名 / 原生配置 → wechat/alipay/douyin），未知目标警告不猜测，schema 只增不改；验证能力矩阵补目标平台与平台事实层路由。
- 「九个分 Skill」清单改为目录枚举单源（`discover_child_names`），并新增根 SKILL.md 路由覆盖校验。
- 平台 Skill 步骤 7 保鲜门禁：核验结果与漂移发现只写入本轮任务报告，不写回 facts/rule-map，不更新 verified/digest 标注。
- 评测引擎可插拔（1.4.0 引入）在本版本成为默认：`EVAL_ENGINE` 环境变量选择 codex/claude/gemini/http，缺省自动探测。

### Compatibility

- 对安装者无破坏：单仓安装方式、manifest 完整性校验、版本成组同步、fail-closed 出包语义全部不变；已安装用户用 `install.sh --force` 升级。

## 1.4.0 - 2026-08-29

### Added

- 新增 `.github/dependabot.yml`，自动跟踪 GitHub Actions 依赖的版本更新。
- 新增 `scripts/summarize_evaluations.py`：把发布门禁的评测产物汇总为只含结论、关键指标和审计元数据的公开摘要，不含提示词、回复或夹具内容。
- 新增 `EVALUATIONS.md`：说明三层评测、判定与独立签署各自能证明什么、公开摘要政策和复现命令。

### Fixed

- Release 工作流增加 concurrency 组，同一 tag 的重复触发不再并发打包。
- README 视频时长校验把标题行纳入视频语境匹配（中/繁/日/英/泰/印尼六语言标题），标题时长与视频元数据漂移时结构校验会失败。
- README 发布包示例版本增加与 `VERSION` 的一致性校验，示例版本漂移时结构校验会失败。

### Changed

- 多语言 README 同步当前版本号与发布包示例版本。

## 1.3.1 - 2026-08-29

### Fixed

- 修正 README 安装表中 Codex 与通用 Agent Skills 安装路径合并表达的问题：Codex App / Codex 本地 Skills 对应 `~/.codex/skills`，通用 Agent Skills 对应 `~/.agents/skills`。
- 补充 `install.sh --help` 中 `codex` 与 `agents` 目标的差异说明，避免用户误以为两者安装到同一读取路径。

### Changed

- 多语言 README 同步当前版本号和 Codex / 通用 Agent 安装路径说明。

## 1.3.0 - 2026-08-29

### Added

- 新增 tag 触发的 GitHub Release 自动化，发布时导出公开包、生成 `package-manifest.json` 和 `SHA256SUMS`，并附加到 Release 页面。
- 新增 `install.sh` 一键安装器，支持 user-level Agent skill 目录和显式项目级 Cursor / GitHub Copilot 安装。
- 新增 GitHub issue 模板，引导用户提交脱敏后的问题复现、证据、环境和 Skill 能力建议。
- 新增 `scripts/check_i18n_readme_structure.py`，检查六种语言 README 的核心章节顺序，防止多语言说明漂移。

### Changed

- README 增加 Release 下载、SHA256 校验、安装器使用方式和 i18n 结构检查命令。
- CI 增加 README 多语言结构检查，`validate_suite.py` 也会把 i18n 漂移纳入结构校验。
- 四份次要语言 README 拆分“验证、包完整性、版本、许可证”段落，让关键公开说明与主 README 保持同构。

## 1.2.0 - 2026-08-29

### Added

- 新增 GitHub Actions CI，自动运行单元测试、结构校验、敏感信息扫描、确定性导出和接收端清单复验。
- CI 工作流使用当前 GitHub 官方 Action 主版本，避免成功运行时出现旧 Node runtime 兼容提醒。
- 新增 `CONTRIBUTING.md` 和 `SECURITY.md`，补齐外部协作入口、变更边界、安全问题报告与复现要求。
- README 增加本地零依赖自检和发布前导出复验命令，让使用者可以自行验证安装包与源码工作副本。
- 敏感扫描规则扩展到云环境 ID、邮箱、手机号、JWT 和腾讯云 COS bucket 形态。
- 评测与最终签署报告增加审计元数据：运行阶段、时间戳、引擎、模型与 prompt/schema 摘要。

### Changed

- 主 Skill 资源说明从“开发批次”改为“能力地图、共享模板与门禁、维护脚本与公开包”，减少内部演进史对使用者的干扰。
- README 说明视频时长校验只识别视频相关语境中的“秒”描述，避免未来把无关性能文案误判为视频时长。
- 主 README 封面图压缩优化，降低仓库和 README 加载负担。
- 接收端包复验器运行时禁用字节码写入，避免在包内生成 `__pycache__` 后被自身判定为额外文件。

## 1.1.4 - 2026-08-29

### Fixed

- 恢复公共导出和敏感扫描的 fail-closed 语义：本地规划草稿不再通过白名单别名被静默隐藏。
- 为二进制/非 UTF-8 命中的 finding 增加 `binary-file:<rule_id>` 标记，便于区分文本泄漏与二进制巧合命中。

### Changed

- 同步更新 `VERSION`、根 Skill 元数据、README 与多语言版本页的版本号，保持版本事实源一致。

## 1.1.3 - 2026-08-25

### Fixed

- 修正 README 说明视频标题与真实视频时长不一致的问题，统一为 32 秒。

### Changed

- 补充公开素材文案规则：标题、链接、说明中的时长、数量、版本等可验证数字必须与实际素材或文件元数据一致。
- `validate_suite.py` 增加 README 说明视频时长文案检查，避免公开页再次出现“标题说 30 秒、视频实际 32 秒”的不一致。

## 1.1.2 - 2026-08-25

### Changed

- 补充版本事实源成组同步规则：版本升级必须同步版本文件、根 Skill 元数据、README、CHANGELOG、发布清单、测试断言和构建/导出清单。
- 强化发布治理与发布清单，避免只更新局部版本号就误判为整条发布链路已升级。
- `validate_suite.py` 增加 README 与 CHANGELOG 版本一致性检查，版本测试改为读取 `VERSION`，减少补丁号硬编码漂移。

## 1.1.1 - 2026-08-25

### Changed

- 补充小程序公开交付说明规则：公开 README、体验二维码、说明视频、安装入口和案例图应兼顾展示质感与稳定访问。
- 补充真实来源案例边界：来源案例只说明方法来源，不作为源码公开、项目验收、审核通过、正式发布或业务数据公开的证据。
- 同步日语、泰语和印尼语 README 的二维码体验边界说明。

## 1.1.0 - 2026-08-13

### Added

- 只读 capability doctor 与原生微信、Taro、uni-app 可选适配矩阵。
- 权限隐私、无障碍、包体/性能、运行错误与发布后观察窗证据矩阵。
- 中断恢复、资产谱系和证据可采信性协议。
- 三层 Skill 路由/行为评测、fail-closed 公共导出和接收端 manifest 复验。
- 根级 README、许可证、兼容说明与维护元数据。

### Changed

- 拆分方案确认、实现、平台审核、用户验收与正式发布状态。
- 公共导出改为明确 allowlist，未知候选默认拒绝。
- 以 MIT License 开源发布，根 README 提供中英文双语版本并新增封面图。

## 1.0.0 - 2026-08-13

### Added

- 首个冻结版本：九个子 Skill、共享工程门禁、模板、结构验证、敏感扫描和确定性公共导出。
