<p align="center">
  <img src="assets/readme-cover.webp?v=3.1.12" alt="小程式開發工程技能套件 封面" width="100%">
</p>

# 小程式開發工程技能套件

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT">
  <img src="https://github.com/NocodeMrLi/mini-program-engineering-skill-suite/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/platform-WeChat%20%7C%20Alipay%20%7C%20Douyin-07C160.svg" alt="Platform: WeChat | Alipay | Douyin">
  <img src="https://img.shields.io/badge/type-Agent%20Skill%20Suite-7B61FF.svg" alt="Type: Agent Skill Suite">
  <img src="https://img.shields.io/badge/category-Evidence--First%20Engineering-FF6B35.svg" alt="Category: Evidence-First Engineering">
  <img src="https://img.shields.io/badge/stack-Taro%20%7C%20uni--app%20%7C%20native-4CAF50.svg" alt="Stack: Taro / uni-app / native">
  <img src="https://img.shields.io/badge/runtime-Python%203.9%2B-3776AB.svg" alt="Runtime: Python 3.9+">
  <img src="https://img.shields.io/badge/lang-%E7%B9%81%E9%AB%94%E4%B8%AD%E6%96%87-7C3AED.svg" alt="Language: 繁體中文">
  <img src="https://img.shields.io/badge/status-Active%20Development-22C55E.svg" alt="Status: Active Development">
  <img src="https://img.shields.io/badge/version-3.1.12-0EA5E9.svg" alt="Version: 3.1.12">
</p>

<p align="center">
  <a href="./README.md">中文</a> ·
  <a href="./README.zh-Hant.md">繁體中文</a> ·
  <a href="./README.en.md">English</a> ·
  <a href="./README.ja.md">日本語</a> ·
  <a href="./README.th.md">ไทย</a> ·
  <a href="./README.id.md">Bahasa Indonesia</a>
</p>

**小程式開發工程技能套件** 是一套面向 Agent 的技能套件，主要服務微信小程式從 0 到 1 開發、既有專案接手與上線前治理。它把「先弄清楚要做什麼、怎麼做、做到哪一步、是否有證據」拆成可執行流程，讓不熟悉小程式工程的人也能在 Agent 協助下少踩坑、少返工、不越權。

英文名：**Mini Program Engineering Skill Suite**。

> 說明：平台事實層現已覆蓋微信、支付寶、抖音三個平台（檢測能力如實分級，見下文「平台規則保鮮」）。LINE MINI App、Telegram Mini Apps 等其他生態可借鑑本套件方法，但仍需針對平台規則另行適配。

---

## 核心亮點

- **三平台事實層**：微信 / 支付寶 / 抖音的平台規則單一事實源，capability doctor 自動識別專案技術棧與目標平台；檢測能力如實分級——微信支援確定性指紋監測，支付寶 / 抖音依賴執行時查官方與用戶上報，不假裝能自動檢測（見[平台規則保鮮](#平台規則保鮮)）。
- **平台規則保鮮流水線**：執行層即時對齊官方現行文件，內容層每週自動漂移檢測（指紋比對 → 抽取 → 影子審計 → 裁決 issue）；本地安裝的版本稍舊，也不會導致任務按過期規則執行（見[平台規則保鮮](#平台規則保鮮)）。
- **真實 Agent CLI 全量驗證**：發布門禁的三層評測（結構 / 路由 / 行為）與獨立簽署在真實 Agent CLI 會話中全量執行——早期版本經 Codex CLI 實測驗收，現行評測引擎可插拔（Codex CLI / Claude Code / Gemini / OpenAI 相容 API），跨引擎通過是更強證據（見[驗證](#驗證)與 [EVALUATIONS.md](EVALUATIONS.md)）。
- **證據優先工程紀律**：狀態必須由匹配證據支撐，沒有證據就如實標註 unknown；3.0 起這套紀律沉澱為領域無關的基礎技能層 `foundation/`，可被任何 Agent 工程套件復用（見[設計原則](#設計原則)）。
- **分層評測 + 獨立簽署**：tier1 結構 / tier2 路由 / tier3 行為三層評測、with-skill 與 baseline 獨立判定、held-out 批凍結前不可用於調參，門禁全 PASS 才發布（見 [EVALUATIONS.md](EVALUATIONS.md)）。
- **供應鏈級發布治理**：SHA256 + 雙 manifest + fail-closed 出包 + 接收端複驗 + 敏感資訊掃描清零，六語言 README 結構一致性由腳本守護（見[包完整性](#包完整性)）。

---

## 32 秒看懂這套技能

如果你想先快速了解這套 Skill 解決什麼問題、從哪裡沉澱而來、適合怎麼用，可以先看這個 [32 秒說明影片](https://raw.githubusercontent.com/NocodeMrLi/mini-program-engineering-skill-suite/main/assets/readme-promo.mp4)。

https://github.com/user-attachments/assets/d382951e-5175-48be-b0c0-44ba210706f1

<sub>影片僅用於說明這套 Skill 的定位、來源與使用邊界。</sub>

---

## 專案狀態

本倉庫是這套套件的公開專案首頁，已依 **MIT License** 開源發布。任何人都可以查看、使用、修改與再分發，完整條款見 [LICENSE](LICENSE)。

---

## 它解決了什麼問題

做小程式，難點往往不是某一段程式碼，而是一開始就不知道先確認什麼、哪些決策會影響後續、什麼時候該停下來驗證，以及上線前哪些事情不能憑感覺跳過。

常見踩坑包括：

- 環境與配置前後不一致；
- 權限、隱私協議或平台規則到上線後才發現漏項；
- UI 在不同機型上錯位，模擬器與真機表現不同；
- 提審版本、驗收版本、發布版本混淆；
- 未確認的改動被推到線上，需要緊急回滾。

這套 Skill 把這些環節打包成 Agent 可執行的工程能力：先梳理目標與邊界，再形成產品規格與工程方案，接著小步實作、分層驗證、收口發布風險。它不替你做商業或產品決策，但能幫助你知道下一步該做什麼、為什麼做、做到什麼程度才算有證據。

---

## 真實專案來源：語寵精靈

這套 Skill 不是從抽象教程寫出來的，而是從真實微信小程式「語寵精靈」的長期開發協作中提煉出來的。它沉澱的是小程式從 0 到 1 的產品拆解、工程實施、驗證驗收、發布準備與證據管理方法。

<p align="center">
  <img src="assets/wordpet-origin-case.png" alt="語寵精靈真實專案來源案例：學習卡片、讀一讀、成長地圖與小程式二維碼" width="100%">
</p>

<sub>「語寵精靈」僅作為真實來源案例展示。本倉庫只公開可復用的小程式開發工程方法，不包含該小程式源碼、AppID、雲資源、私有配置、業務資料、審核狀態或內部開發記錄。小程式二維碼僅用於體驗真實案例，掃碼結果以微信平台目前狀態為準。</sub>

---

## 它幫助 Agent 做到這些事

- **接手專案**：先摸清既有狀態再動手，避免破壞已完成成果；
- **釐清需求**：把模糊想法轉成可驗收的明確規格；
- **沉澱決策**：把產品決策落到架構、資料、介面、權限與兜底邏輯；
- **安全改程式碼**：小顆粒、可回滾地實作變更；
- **逐級驗證**：區分 UI 預覽、使用者確認、整合驗證、機型適配與最終驗收；
- **用證據排錯**：依據真實證據定位問題，而不是猜；
- **如實彙報**：只報告已驗證到的狀態，不誇大也不省略。

---

## 能力清單

| 模組 | 作用 |
| --- | --- |
| 專案摸排 | 只讀摸清專案，輸出事實、風險與變更邊界 |
| 產品規格 | MVP 範圍、使用者流程、狀態矩陣、驗收標準 |
| 架構設計 | 模組、資料、API、權限、異常處理策略 |
| 平台適配 | 微信小程式工具鏈、隱私、權限與平台證據 |
| 落地實作 | 小顆粒改動、測試與既有成果保護 |
| UI 與機型適配 | 設計還原、預覽先行、多機型核驗 |
| 調試排錯 | 復現、並列假設、根因定位、防回歸 |
| 驗證 | 靜態、單元、整合、模擬器、真機、雲端與上線證據分級 |
| 上線就緒 | 版本、構建、安全、隱私、回滾、上傳 / 審核 / 發布治理 |

---

## 設計原則

- 事實先於動作：未摸清現狀，不修改既有專案。
- 證據對齊狀態：只報告已被證明的工程狀態。
- 階段邊界分明：預覽、實作、構建、上傳、審核、驗收、發布不可互相替代。
- 外部動作獨立授權：雲端、上傳、提審、發布等寫操作必須逐項確認。
- 私有資訊隔離：公開包與 README 素材必須先通過脫敏與敏感資訊檢查。

---

## 平台規則保鮮

平台規則會持續變化，寫死在技能裡的規則終會過期。2.0 起本套件採「執行層即時保鮮、內容層受控進化」：

- **執行時永遠以官方為準**：上傳、提審、審核、發布、隱私申報、配額等平台觸點步驟，Agent 會先核對套件記錄的平台事實是否仍然新鮮（每條事實帶核驗日期與來源指紋）；過期或高風險步驟直接查官方現行文件再執行。**本地版本稍舊不會導致按過期規則執行**——只影響查官方的頻率，不影響正確性。
- **套件內容受控升級**：維護方透過漂移檢測工具（對官方文件做指紋比對）發現規則變化後，經多輪獨立審計提交更新；你可以在 Issues 用 **Platform rule drift** 模板自願上報發現的規則變化。
- **想用最新版**：從 Releases 下載新包並 `install.sh --force` 重裝；套件永不靜默自動更新本地安裝。

平台事實與規則地圖位於倉庫 `platforms/` 目錄，現覆蓋微信、支付寶、抖音三個平台：微信支援確定性指紋監測（每週自動漂移檢測）；支付寶與抖音的官方文件為客戶端渲染，確定性指紋無法觀測內容變化，如實標註為 manual-only——保鮮依賴執行時查官方與用戶上報，不假裝能自動檢測。未收錄的平台一律查官方並保持 unknown，不猜測。

---

## 使用方法

把本倉庫克隆到支援 `SKILL.md` 或專案規則的 Agent 應用目錄中；如果不想手動操作，可以把這句話交給你的 Agent：

```text
https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git 幫我安裝這個技能
```

常見安裝位置：

| 應用 / 執行器 | 建議位置 | 調用方式 |
| --- | --- | --- |
| Codex App / Codex 本地 Skills | `~/.codex/skills/mini-program-engineering-suite` | `/mini-program-engineering-suite` |
| 通用 Agent Skills | `~/.agents/skills/mini-program-engineering-suite` | `/mini-program-engineering-suite` |
| Claude Code | `~/.claude/skills/mini-program-engineering-suite` | `/mini-program-engineering-suite` |
| GitHub Copilot Coding Agent | `.github/skills/mini-program-engineering-suite` | 在倉庫任務中按 Skill 說明觸發 |
| Cursor | `.cursor/rules/mini-program-engineering-suite` | 作為專案規則 / Skill 說明使用 |

如果使用安裝器，`--target codex` 對應 `~/.codex/skills`，`--target agents` 對應 `~/.agents/skills`。

安裝後重新開啟一個 Agent 會話，直接描述任務即可，例如：

```text
/mini-program-engineering-suite 我想從 0 到 1 做一個微信小程式，請先幫我梳理產品範圍和開發步驟。
```

---

## 它不會做什麼

這套套件不會自動安裝依賴、建立雲端資源、上傳包、提交審核、發布版本或改動線上狀態。它可以準備證據和操作指引，但每個外部動作仍需獨立授權。

---

## 驗證

當前套件版本在發布前會經過結構校驗、敏感資訊掃描、公開包導出、清單核對、路由評估、行為評估與獨立終審。

2.0 起新增**平台規則保鮮**：執行上傳、提審、隱私申報等平台觸點步驟時一律以官方現行規則為準（套件記錄的事實僅作帶核驗日期的快取），本地版本稍舊不會導致按過期規則執行；詳見中文主 README 的「平台規則保鮮」。评测引擎與模型可插拔（codex / claude / gemini / OpenAI 相容 API）。

評測分層、證據邊界與各版本公開摘要見 [EVALUATIONS.md](EVALUATIONS.md)。

本地自檢：

```bash
python3 -m unittest discover -s tests -q
python3 scripts/validate_suite.py .
python3 scripts/check_i18n_readme_structure.py .
python3 scripts/scan_sensitive_content.py . --format json
```

---

## 包完整性

建議優先使用 [GitHub Releases](https://github.com/NocodeMrLi/mini-program-engineering-skill-suite/releases) 中的版本化公開包。每個 Release 會附帶壓縮包、`package-manifest.json`、`gate-summary.json` 與涵蓋三者的 `SHA256SUMS`。倉庫已啟用不可變 Release：所有附件先在草稿階段附齊，發布後 tag 與附件不可替換；`gate-summary.json` 可回讀 SemVer 與簽名評測門禁結果。Linux / GitHub Actions 可用 `sha256sum -c SHA256SUMS`；macOS 可用 `shasum -a 256 -c SHA256SUMS`。解壓後再用包內 `verify_public_package.py` 復驗清單。

接收公開包時校驗完整性：

```bash
python3 <包目錄>/scripts/verify_public_package.py <包目錄>
```

以 v3.1.12 為例（從 Release 下載後）：

```bash
tar -xzf mini-program-engineering-suite-v3.1.12.tar.gz
python3 mini-program-engineering-suite-v3.1.12/scripts/verify_public_package.py \
  mini-program-engineering-suite-v3.1.12
```

---

## 目前版本

目前版本：**3.1.12**。

---

## 授權

本專案採用 **MIT License**。
