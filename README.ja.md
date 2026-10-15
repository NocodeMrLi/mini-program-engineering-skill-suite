<p align="center">
  <img src="assets/readme-cover.webp?v=3.6.0" alt="Mini Program Engineering Skill Suite cover" width="100%">
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
  <img src="https://img.shields.io/badge/version-3.6.0-0EA5E9.svg" alt="Version: 3.6.0">
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

3.6.0 は三つの判断を補強します。データの更新遅延と実際の不整合を区別し、状態とともに本人性・環境・完全な対象範囲を確認し、削除などのプレビュー・確認・実行を一致させます。既存の操作を尊重し、失敗時は入力を保持し、結果が不明な場合は再試行前に照合して、重複操作や変更のない再テストを減らします。

> 注意：プラットフォームファクト層は現在 WeChat・Alipay・Douyin の 3 プラットフォームをカバーしています（検出能力は正直に区分、下記「プラットフォーム規則の鮮度保持」参照）。LINE MINI App、Telegram Mini Apps などのその他のエコシステムにも考え方を転用できますが、各プラットフォームの規則に合わせた追加適配は必要です。

---

## ハイライト

- **3プラットフォームのファクト層**：WeChat / Alipay / Douyin のプラットフォーム規則の単一の事実ソース。capability doctor がプロジェクトの技術スタックと対象プラットフォームを自動判定します。検出能力は正直に区分——WeChat は決定論的フィンガープリント監視に対応し、Alipay / Douyin は実行時の公式確認とユーザー報告に依存するもので、自動検出できるとは偽りません（[プラットフォーム規則の鮮度保持](#プラットフォーム規則の鮮度保持)参照）。
- **プラットフォーム規則の鮮度保持パイプライン**：実行層は現行の公式ドキュメントを確認し、内容層は週次でドリフトを検出します。監査で一致した `facts.md` 更新のみ PR を自動作成し、CI 通過後に自動マージします。それ以外の結果は issue に残します（[プラットフォーム規則の鮮度保持](#プラットフォーム規則の鮮度保持)参照）。
- **実 Agent セッションと成果物検証**：tier1 はローカル静的検査、tier2/3 と独立判定は実 Agent セッションで行い、振る舞い変更版には tier4 の匿名プロジェクト比較も必要です。3.6.0 は ZCode / GLM による段階別評価を完了し、成果物比較と最終独立品質判定には GLM-5.3-Flash を使用しました。モデル・検証範囲・証拠は [EVALUATIONS.md](EVALUATIONS.md) を参照してください。
- **日常操作の境界を詳しく確認**：戻った際の更新、ダイアログの閉じ直し、入力継続と自動保存、クラウド障害からの復旧を確認し、古い状態が新しい操作を妨げないよう導きます。結果は対象プロジェクトで検証します。
- **品質を優先し進捗を見える形に**：主な利用経路を進め、確認できる成果を示します。変更・実際の失敗・証拠不足に応じて再検証し、利用者が選んだ手動操作を適時に引き継ぎます。
- **証拠優先のエンジニアリング規律**：ステータスには必ず対応する証拠が必要で、なければ unknown と正直に記録します。この規律はドメイン非依存の基礎スキル層 `foundation/` として整理され、任意の Agent エンジニアリングスイートで再利用可能です（[設計原則](#設計原則)参照）。
- **層別評価と独立署名**：tier1 構造 / tier2 ルーティング / tier3 振る舞い / tier4 匿名の合成プロジェクト成果物の非退化評価、with-skill と baseline の独立判定、リリースまで凍結される held-out バッチ——全ゲート PASS でのみリリースします（[EVALUATIONS.md](EVALUATIONS.md) 参照）。
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

プラットフォーム規則は変化し続けるため、スキルに書き込まれた規則はいずれ陳腐化します。本スイートは「実行時は常に最新、内容は管理された進化」を採用：

- **実行前に公式の根拠を確認**：アップロード、審査提出、公開、プライバシー申告、割当について、事実の日付・出典・適用範囲を確認し、古い情報や高リスク事項は最新の公式資料を確認するよう求めます。確認できなければ unknown とし、それに依存する操作を止めます。この手順は旧版の正確性を保証しないため、ローカル版も更新してください。
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

### インストール済みの版を更新

リポジトリのマージや tag の公開はローカルのスキルを更新しません。Releases の公開パッケージを取得・検証し、展開したディレクトリで実行します：

```bash
cd mini-program-engineering-suite-v3.6.0
bash install.sh --target auto --force
```

インストーラーは旧ディレクトリを、その隣にあるタイムスタンプ付きバックアップへ移します。今回の出力に示されたバックアップを、スキル検索対象外のディレクトリへ移動してください。各インストール先の VERSION を確認し、個別に配置した子スキルのコピーや入口も更新して、版の混在を防ぎます。次のターンまたは新しいセッションで更新内容を読み込めます。

---

## しないこと

このスイートは、依存関係の自動インストール、クラウド資源の作成、パッケージのアップロード、審査提出、公開、オンライン状態の変更を自動では行いません。外部の書き込み操作は、それぞれ明示的な許可が必要です。

---

## 検証

公開前には、構造検証、機密情報スキャン、公開パッケージ出力、マニフェスト確認、ルーティング評価、行動評価、独立レビューを行います。

プラットフォームの事実は日付・出典・適用範囲で確認し、不明なら unknown のまま関連操作を止めます。対応エンジンと実測範囲は区別し、[EVALUATIONS.md](EVALUATIONS.md) に記録します。

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

[GitHub Releases](https://github.com/NocodeMrLi/mini-program-engineering-skill-suite/releases) のバージョン付き公開パッケージを優先してください。各 Release にはアーカイブ、`package-manifest.json`、`gate-summary.json`、および三つを対象にした `SHA256SUMS` が含まれます。Immutable Releases が有効で、全アセットをドラフト中に添付し、公開後は tag とアセットを差し替えられません。`gate-summary.json` で SemVer と署名付き評価ゲートの結果を確認できます。Linux / GitHub Actions では `sha256sum -c SHA256SUMS`、macOS では `shasum -a 256 -c SHA256SUMS` を使えます。展開後、同梱の `verify_public_package.py` でマニフェストを再検証してください。

公開パッケージを受け取った場合の完全性確認：

```bash
python3 <package-dir>/scripts/verify_public_package.py <package-dir>
```

v3.6.0 の例（Release からダウンロード後）：

```bash
tar -xzf mini-program-engineering-suite-v3.6.0.tar.gz
python3 mini-program-engineering-suite-v3.6.0/scripts/verify_public_package.py \
  mini-program-engineering-suite-v3.6.0
```

---

## バージョン

3.6.0 では、複数時点の照合、状態と本人性の独立検証、破壊的操作のプレビューとアトミック実行の範囲一致を補強します。既存の操作を尊重し、不要な再確認・アップロード・再テストを減らします。GLM 評価範囲と実際の公開結果は [EVALUATIONS.md](EVALUATIONS.md) と Release を参照してください。

現在のバージョン：**3.6.0**。[v3.6.0 は正式公開済みで、公開パッケージをダウンロードできます](https://github.com/NocodeMrLi/mini-program-engineering-skill-suite/releases/tag/v3.6.0)。本ページは現在の機能を説明します。履歴は [CHANGELOG.md](CHANGELOG.md)、評価範囲と証拠の限界は [EVALUATIONS.md](EVALUATIONS.md) を参照してください。

v3.6.0 の公開検証では、確定的テスト386/386、署名済み最終コミットのCI9/9、技術・協業シナリオ12/12が合格しました。2事例・最終報告8件の成果物比較は平均2.7375点改善し、候補の重大エラーと重要評価軸の退行はいずれも0でした。2回の最終独立品質判定と信頼されたRSA署名検証も合格しました。公開資産4点のチェックサムと公開ファイル129件はtagからのエクスポートとバイト単位で一致します。この管理された検証は対象プロジェクトの実機・クラウド・実取引の受入検証を代替せず、開発速度の向上を定量的に証明するものでもありません。

---

## ライセンス

ライセンス：**MIT License**。
