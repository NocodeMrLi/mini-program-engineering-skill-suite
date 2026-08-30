# 证据状态模型

状态只能由匹配证据支持，低级状态不得自动推导为高级状态。交付生命周期与用户验收是两个正交维度，必须分别记录。

## 交付生命周期

| 状态 | 中文含义 | 最低证据 |
| --- | --- | --- |
| `proposed` | 已提出方案 | 方案、草图或预览可查 |
| `proposal-approved` | 方案已确认 | 用户在当前上下文明确确认当前方案 |
| `implemented` | 已实现 | 源码差异或新增文件可查 |
| `built` | 已构建 | 本轮构建命令成功且产物可定位 |
| `locally-verified` | 已本地验证 | 本轮测试、静态检查或本地运行成功 |
| `device-verified` | 已真机验证 | 真机步骤、日志或截图证据 |
| `cloud-verified` | 已云端验证 | 云端状态、日志或真实接口返回 |
| `release-ready` | 已具备发布条件 | 目标版本的验证、安全、配置和回滚门禁通过 |
| `uploaded` | 已上传平台 | 平台上传记录和版本信息 |
| `review-submitted` | 已提交审核 | 平台审核提交回执和对应版本 |
| `review-approved` | 已审核通过 | 平台审核结果和对应版本 |
| `released` | 已正式发布 | 正式环境或平台发布证据 |

## 用户验收维度

| 状态 | 中文含义 | 最低证据 |
| --- | --- | --- |
| `accepted` | 已正式验收 | 用户明确验收或正式验收记录 |

- `accepted` 独立记录，不自动由方案确认、实现、验证、审核或发布状态推出。
- `accepted` 也不自动推出 `release-ready`、`review-approved` 或 `released`；缺少正式验收证据时，验收维度保持 `unknown`。

## 操作性结论

这些值描述证据或门禁结论，不是交付生命周期中的更高阶段。

| 状态 | 中文含义 | 最低证据 |
| --- | --- | --- |
| `unknown` | 当前状态未知 | 当前证据不足、不可查或彼此冲突 |
| `not-ready` | 当前不具备发布条件 | 至少一项发布门禁未通过或仍有硬阻塞 |

- `unknown` 不能被当作失败或成功；必须列出缺失、冲突或待刷新证据。
- `not-ready` 只表示发布门禁结论，不自动降低已被独立证据支持的实现或验证状态。

## 使用规则

- 每次汇报写清证据来自本轮还是历史记录。
- 历史证据可能过期时重新验证，不能用旧日志证明当前状态。
- `proposed` 不等于 `proposal-approved`；`proposal-approved` 不等于 `implemented`。
- `implemented` 不等于 `locally-verified`；`built` 不等于 `device-verified`。
- `release-ready` 不等于 `uploaded`；`uploaded` 不等于 `review-submitted`；`review-submitted` 不等于 `review-approved`；`review-approved` 不等于 `released`。
- 平台状态与用户验收是不同维度；预览认可或正式发布都不自动等于 `accepted`。
- 无法取得高一级证据时，保留当前状态并列出缺失验证。
<!-- foundation-source: evidence-first-engineering v3.0 -->
