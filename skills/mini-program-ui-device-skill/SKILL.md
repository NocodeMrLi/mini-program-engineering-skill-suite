---
name: mini-program-ui-device-skill
description: >-
  Design, preview, implement, and assess mini-program interfaces against an approved prototype, screenshot, visual reference, design system, or bounded UI request while preserving product semantics and existing accepted behavior. Use when users ask to reproduce a mini-program screen, refine visual hierarchy, adapt layouts across device sizes, handle safe areas or keyboards, inspect touch targets, scrolling, media, or gesture conflicts, compare an implementation with a reference, or prepare a device-verification matrix. Separates proposed visual previews, user approval, source integration, local checks, and real-device evidence; never invents product functionality for visual completeness or claims device validation without device-specific proof.
---

# /mini-program-ui-device-skill — 小程序界面与真机适配

以已确认参考目标和产品语义为准完成界面工作，并严格区分视觉预览、用户确认、正式集成、本地检查与真机证据。参考存在时，忠实度是可验证目标，不用主观“更漂亮”替代。

## 输入与阶段边界

- 接收已确认原型、截图、参考页面、设计系统、界面问题或设备反馈；先记录权威参考、允许变化、必须保护交互与未知项。
- 若请求涉及高影响视觉风格、角色形象、关键动画或大范围布局，先产出可独立查看的视觉预览，取得用户确认后才能正式集成。
- 缺少可渲染素材时，当场提供 2–3 个具名文字候选，分别说明视觉重点、变化范围与保持不变的产品语义，供用户先选方向；具名文字候选不等于已渲染预览，不能声称视觉效果、动效或设备表现已经得到验证。
- 用户明确要求立即查看效果且当前只读时，在回复中为每个候选附自包含 SVG 或 HTML 预览代码/可直接查看的数据内容，不写入项目；说明预览尺寸、状态和占位素材。它只证明候选画面可查看，不证明正式源码、动效、交互或真机表现。
- 不为了填满页面新增按钮、入口、奖励、状态或数据规则；产品语义冲突时退回产品决策。
- 模拟器或桌面预览不是真机；没有机型、操作步骤、截图/日志或设备结果时，不报告真机通过。

## 界面与设备流程

1. 将参考目标拆为布局、层级、间距、尺寸、形态、色彩、字体、素材、交互和状态，并标记可精确比较项。
2. 建立 `proposed` → `proposal-approved` → `implemented` → `locally-verified` → `device-verified` 阶段记录；任何阶段不得自动升级。
3. 先制作视觉预览或最小差异方案；用户确认后，仅在授权范围内正式集成并保护已有资产与交互。
4. 检查最窄屏、最长文案、最大数字、空/加载/错误、动态字体（若支持）、安全区、键盘、横竖屏（若支持）和媒体容器。
5. 核对触控热区、滚动容器、固定层、弹层、返回/下拉/横滑等行为，建立手势冲突矩阵并给出优先级与失败路径。
6. 分别记录静态检查、桌面/模拟器预览和真实设备结果；视觉对比采用相同状态、尺寸与素材，不能拿不同条件作结论。
7. 图片、图标、动画、音频或字体发生新增、处理或替换时，按 [资产谱系记录模板](assets/asset-lineage-record.md) 记录原始/衍生关系、处理方式、槽位、尺寸、透明通道、哈希、批准范围和替换关系。
8. 批准只覆盖点名文件、变体和目标槽位。旧资产默认保留到新资产验证完成且回滚入口可查；没有明确删除授权时不得删除旧资产，替换关系本身也不授权删除。
9. 使用 [无障碍验证矩阵](assets/accessibility-matrix.md) 分开检查 ARIA/读屏语义、动态字体、对比度、触控热区和焦点顺序；静态结果不冒充真机证据。
10. 使用 [界面与设备工作流](references/ui-device-workflow.md) 自检，并按 [界面与设备证据模板](assets/ui-device-evidence-record.md) 交付。

## 最低输出

- 权威参考目标、状态/尺寸、允许变化、必须保护项和未知项。
- 参考与实现的差异表，以及视觉预览或集成文件清单。
- 发生资产处理时提供资产谱系；预览批准只覆盖点名文件、变体和目标槽位。
- 批准或替换证据不完整时，明确输出“批准仅限已点名的文件、变体与槽位”和“当前必须保留旧资产并维护可复查回滚入口”；不能只把保留与回滚列为 unknown。
- 即使任务只读，也由只读输出本身形成可复查回滚记录：旧/新 asset-id、路径与哈希、目标槽位、当前引用、恢复条件和批准边界；记录不等于修改项目。
- 屏幕/内容边界矩阵、触控与手势冲突矩阵。
- 已执行的本地或真机步骤、证据、未覆盖机型/状态和残余风险。
- 当前阶段与状态；预览认可不等于正式集成，正式集成不等于真机验收。

## 停止条件

参考目标互相冲突、关键视觉方向未获用户确认、实现会改变未确认产品行为、需要真实设备但无法取得证据，或现有用户改动无法安全保护时停止在对应阶段。不得用裁切内容、禁用手势或隐藏错误状态伪造适配完成。

## 独立与套件协作

独立安装时，本 Skill 可完成界面方案、受控集成和设备矩阵。位于套件中时，接收稳定产品语义与实现边界，输出视觉/设备证据和验证入口，不直接调用其他组件脚本。
