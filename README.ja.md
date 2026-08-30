<p align="center">
  <img src="assets/readme-cover.webp?v=3.1.0" alt="Mini Program Engineering Skill Suite cover" width="100%">
</p>

# Mini Program Engineering Skill Suite

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT">
  <img src="https://github.com/NocodeMrLi/mini-program-engineering-skill-suite/actions/workflows/ci.yml/badge.svg" alt="CI">
  <img src="https://img.shields.io/badge/platform-WeChat%20%7C%20Alipay%20%7C%20Douyin-07C160.svg" alt="Platform: WeChat | Alipay | Douyin">
  <img src="https://img.shields.io/badge/type-Agent%20Skill%20Suite-7B61FF.svg" alt="Type: Agent Skill Suite">
  <img src="https://img.shields.io/badge/category-Evidence--First%20Engineering-FF6B35.svg" alt="Category: Evidence-First Engineering">
  <img src="https://img.shields.io/badge/stack-Taro%20%7C%20uni--app%20%7C%20native-4CAF50.svg" alt="Stack: Taro / uni-app / native">
  <img src="https://img.shields.io/badge/runtime-Python%203.9%2B-3776AB.svg" alt="Runtime: Python 3.9+">
  <img src="https://img.shields.io/badge/lang-日本語-DC2626.svg" alt="Language: 日本語">
  <img src="https://img.shields.io/badge/status-Active%20Development-22C55E.svg" alt="Status: Active Development">
  <img src="https://img.shields.io/badge/version-3.1.0-0EA5E9.svg" alt="Version: 3.1.0">
</p>

<p align="center">
  <a href="./README.md">中文</a> ·
  <a href="./README.zh-Hant.md">繁體中文</a> ·
  <a href="./README.en.md">English</a> ·
  <a href="./README.ja.md">日本語</a> ·
  <a href="./README.th.md">ไทย</a> ·
  <a href="./README.id.md">Bahasa Indonesia</a>
</p>

**Mini Program Engineering Skill Suite** は、Agent がミニプログラム開発を段階的に進めるためのスキルスイートです。主な対象は WeChat Mini Program で、0 から 1 の開発、既存プロジェクトの引き継ぎ、リリース前の確認を支援します。

中国語名：**小程序开发工程技能套件**。

> 注意：プラットフォームファクト層は現在 WeChat・Alipay・Douyin の 3 プラットフォームをカバーしています（検出能力は正直に区分、下記「プラットフォーム規則の鮮度保持」参照）。LINE MINI App、Telegram Mini Apps などのその他のエコシステムにも考え方を転用できますが、各プラットフォームの規則に合わせた追加適配は必要です。

---

## ハイライト

- **3プラットフォームのファクト層**：WeChat / Alipay / Douyin のプラットフォーム規則の単一の事実ソース。capability doctor がプロジェクトの技術スタックと対象プラットフォームを自動判定します。検出能力は正直に区分——WeChat は決定論的フィンガープリント監視に対応し、Alipay / Douyin は実行時の公式確認とユーザー報告に依存するもので、自動検出できるとは偽りません（[プラットフォーム規則の鮮度保持](#プラットフォーム規則の鮮度保持)参照）。
- **プラットフォーム規則の鮮度保持パイプライン**：実行層は常に公式の現行ドキュメントに即時整合し、内容層は週次の自動ドリフト検出（指紋比較 → 抽出 → シャドウ監査 → 判定 issue）を行います。ローカルのバージョンが少し古くても、タスクが期限切れの規則で実行されることはありません（[プラットフォーム規則の鮮度保持](#プラットフォーム規則の鮮度保持)参照）。
- **実 Agent CLI によるフルゲート検証**：リリースゲートの 3 層評価（構造 / ルーティング / 振る舞い）と独立署名は、実際の Agent CLI セッションでフル実行されます——初期バージョンは Codex CLI で実測受入され、現在の評価エンジンは差し替え可能（Codex CLI / Claude Code / Gemini / OpenAI 互換 API）。エンジンを跨いだ合格はより強い証拠です（[検証](#検証)と [EVALUATIONS.md](EVALUATIONS.md) 参照）。
- **証拠優先のエンジニアリング規律**：ステータスには必ず対応する証拠が必要で、なければ unknown と正直に記録します。3.0 からはこの規律がドメイン非依存の基礎スキル層 `foundation/` として整理され、任意の Agent エンジニアリングスイートで再利用可能です（[設計原則](#設計原則)参照）。
- **層別評価と独立署名**：tier1 構造 / tier2 ルーティング / tier3 振る舞いの 3 層評価、with-skill と baseline の独立判定、リリースまで凍結される held-out バッチ——全ゲート PASS でのみリリースします（[EVALUATIONS.md](EVALUATIONS.md) 参照）。
- **サプライチェーン級のリリースガバナンス**：SHA256 + 二重 manifest + fail-closed パッケージング + 受け側再検証 + 機密情報スキャンゼロ。6 言語 README の構造一致性もスクリプトで守ります（[パッケージ完全性](#パッケージ完全性)参照）。

---

## 32 秒で概要を見る

この Skill が何を解決し、どの実プロジェクトから生まれ、どのように使うのかを [32 秒の説明動画](https://raw.githubusercontent.com/NocodeMrLi/mini-program-engineering-skill-suite/main/assets/readme-promo.mp4) で確認できます。

https://github.com/user-attachments/assets/d382951e-5175-48be-b0c0-44ba210706f1

<sub>この動画は、スイートの位置づけ、由来、利用境界を説明するためのものです。</sub>

---

## ステータス

このリポジトリは本スイートの公開ホームです。**MIT License** で公開されており、閲覧、利用、変更、再配布が可能です。詳細は [LICENSE](LICENSE) を参照してください。

---

## 解決する課題

ミニプログラム開発で難しいのは、単にコードを書くことだけではありません。最初に何を確認するべきか、どの意思決定が後工程に影響するのか、どの時点で検証を止めて証拠を残すべきか、リリース前に何を勝手に進めてはいけないのかが重要です。

よくある問題：

- 開発環境や設定が途中で食い違う；
- 権限、プライバシー、プラットフォーム規則の確認が遅れる；
- UI が端末によって崩れ、シミュレーターと実機で挙動が違う；
- 提出版、受入版、公開版が混同される；
- 未確認の変更がオンラインに出てしまい、緊急ロールバックが必要になる。

この Skill は、目標と境界の整理、仕様化、設計、実装、段階的検証、リリース準備を Agent が実行しやすい形に分解します。ビジネス判断を代行するものではありませんが、「次に何をするか」「なぜ必要か」「どの証拠で完了と言えるか」を明確にします。

---

## 実プロジェクト由来：WordPet

この Skill は抽象的なチュートリアルから作られたものではなく、実際の WeChat Mini Program **WordPet** の長期開発協力から抽出されたものです。ここで公開しているのは、製品分解、実装、検証、受け入れ、リリース準備、証拠管理の再利用可能な工程方法です。

<p align="center">
  <img src="assets/wordpet-origin-case.png" alt="WordPet real project origin case" width="100%">
</p>

<sub>WordPet は方法の由来を示す実例としてのみ掲載しています。このリポジトリには、アプリのソースコード、AppID、クラウド資源、非公開設定、業務データ、審査状態、内部開発記録は含まれません。QR コードは実例を体験するためだけに提供しており、スキャン結果は現在の WeChat プラットフォームの状態に依存します。</sub>

---

## Agent ができるようになること

- **プロジェクト引き継ぎ**：既存状態を読み取り、受け入れ済み機能を壊さない；
- **要求整理**：曖昧なアイデアを検証可能な仕様にする；
- **意思決定の固定**：設計、データ、API、権限、例外処理に落とし込む；
- **安全な実装**：小さく、戻せる変更で進める；
- **段階的検証**：UI プレビュー、ユーザー確認、統合検証、端末検証、最終受け入れを区別する；
- **証拠ベースのデバッグ**：推測ではなく証拠で問題を切り分ける；
- **正直な報告**：検証済みの範囲だけを報告する。

---

## コンポーネント一覧

| 領域 | 目的 |
| --- | --- |
| Project intake | 読み取り専用で現状、リスク、変更境界を把握 |
| Product specification | MVP、ユーザーフロー、状態、受け入れ基準 |
| Architecture | モジュール、データ、API、権限、障害対応 |
| Platform adaptation | WeChat Mini Program の工具链、プライバシー、権限、平台証拠 |
| Implementation | 小さな変更、テスト、既存成果の保護 |
| UI and device adaptation | デザイン再現、プレビュー、端末検証 |
| Debugging | 再現、仮説比較、原因特定、回帰防止 |
| Verification | 静的、単体、統合、シミュレーター、実機、クラウド、リリース層の証拠 |
| Release readiness | バージョン、ビルド、安全、プライバシー、ロールバック、提出 / 審査 / 公開 |

---

## 設計原則

- 事実が先、変更は後：現状を確認する前に既存プロジェクトを変更しない。
- 状態は証拠に合わせる：証明された範囲だけを報告する。
- 工程を混同しない：プレビュー、実装、ビルド、提出、審査、受け入れ、公開は別の段階。
- 外部操作は個別承認：クラウド変更、アップロード、審査提出、公開はそれぞれ許可が必要。
- 非公開情報を分離する：公開パッケージと README 素材は機密情報スキャンを通す。

---

## プラットフォーム規則の鮮度保持

プラットフォーム規則は変化し続けるため、スキルに書き込まれた規則はいずれ陳腐化します。2.0 以降、本スイートは「実行時は常に最新、内容は管理された進化」を採用：

- **実行は常に公式ソースが優先**：アップロード・審査提出・審査・リリース・プライバシー申告・枠などのプラットフォーム接触ステップでは、記録された事実の鮮度（検証日とソース指紋付き）を先に確認し、期限切れまたは高リスクのステップは公式の現行ドキュメントを確認してから実行します。**ローカル版が少し古くても、古い規則で実行されることはありません**——影響するのは公式確認の頻度だけで、正確性には影響しません。
- **内容は管理された進化**：維持者がドリフト検出ツール（公式ページの指紋比較）で規則の変化を発見し、複数ラウンドの独立監査を経て更新します。発見した規則変化は Issues の **Platform rule drift** テンプレートで自主報告できます。
- **最新版を使うには**：Releases から新パッケージを取得し `install.sh --force` で再インストール；ローカルをサイレント自動更新することはありません。

プラットフォーム事実とルールマップはリポジトリの `platforms/` にあり、現在は WeChat・Alipay・Douyin の 3 プラットフォームをカバーします。WeChat は決定論的フィンガープリント監視（週次の自動ドリフト検出）に対応。Alipay と Douyin の公式ドキュメントはクライアントサイドレンダリングのため、指紋では内容変化を観測できず、正直にも `manual-only` と記録しています——鮮度保持は実行時の公式確認とユーザー報告に依存し、自動検出できると偽りません。未収録のプラットフォームは一律で公式を確認し `unknown` を保持し、推測しません。

---

## 使い方

`SKILL.md` またはプロジェクトルールを認識できる Agent アプリのスキルディレクトリに、このリポジトリを clone します。手動でコマンドを打ちたくない場合は、利用中の Agent に次の文を渡してください。

```text
https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git このスキルをインストールしてください
```

Codex App / Codex ローカルスキルの場合：

```bash
git clone https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git \
  ~/.codex/skills/mini-program-engineering-suite
```

汎用 Agent Skills ランナーの場合：

```bash
git clone https://github.com/NocodeMrLi/mini-program-engineering-skill-suite.git \
  ~/.agents/skills/mini-program-engineering-suite
```

インストーラを使う場合、`--target codex` は `~/.codex/skills`、`--target agents` は `~/.agents/skills` に対応します。

利用例：

```text
/mini-program-engineering-suite WeChat Mini Program を 0 から作りたいので、まず製品範囲と開発ステップを整理してください。
```

---

## しないこと

このスイートは、依存関係の自動インストール、クラウド資源の作成、パッケージのアップロード、審査提出、公開、オンライン状態の変更を自動では行いません。外部の書き込み操作は、それぞれ明示的な許可が必要です。

---

## 検証

公開前には、構造検証、機密情報スキャン、公開パッケージ出力、マニフェスト確認、ルーティング評価、行動評価、独立レビューを行います。

2.0 から**プラットフォーム規則の鮮度保持**を導入：アップロード・審査提出・プライバシー申告などのプラットフォーム接触ステップは、常に公式の現行ルールに従って実行されます（本スキルの記録は検証日付きキャッシュ）。ローカル版が少し古くても、古いルールで実行されることはありません。評価エンジンとモデルは差し替え可能です（codex / claude / gemini / OpenAI 互換 API）。

評価レイヤー、証拠の境界、バージョンごとの公開サマリーは [EVALUATIONS.md](EVALUATIONS.md) を参照してください。

ローカル検証：

```bash
python3 -m unittest discover -s tests -q
python3 scripts/validate_suite.py .
python3 scripts/check_i18n_readme_structure.py .
python3 scripts/scan_sensitive_content.py . --format json
```

---

## パッケージ完全性

[GitHub Releases](https://github.com/NocodeMrLi/mini-program-engineering-skill-suite/releases) のバージョン付き公開パッケージを優先してください。各 Release にはアーカイブ、`package-manifest.json`、`SHA256SUMS` が含まれます。Linux / GitHub Actions では `sha256sum -c SHA256SUMS`、macOS では `shasum -a 256 -c SHA256SUMS` を使えます。展開後、同梱の `verify_public_package.py` でマニフェストを再検証してください。

公開パッケージを受け取った場合の完全性確認：

```bash
python3 <package-dir>/scripts/verify_public_package.py <package-dir>
```

---

## バージョン

現在のバージョン：**3.1.0**。

---

## ライセンス

ライセンス：**MIT License**。
