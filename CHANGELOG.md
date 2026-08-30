# Changelog

本文件记录公共套件能力变化。版本标题表示套件已通过对应冻结门禁，不代表已经安装到任何全局目录或发布到外部平台。

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
