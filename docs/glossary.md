# 技術用語集（managers.md / architects.md 補助資料）

本プロジェクトの報告書 ([report-for-managers.md](report-for-managers.md) / [report-for-architects.md](report-for-architects.md)) で使われる技術用語を、なるべく平易に解説します。「何のための技術か」「本プロジェクトでの役割」をセットで掴めるよう構成しました。

## 目次

1. [Azure サービス](#1-azure-サービス)
2. [認証・セキュリティ](#2-認証セキュリティ)
3. [インフラ自動化と CI/CD](#3-インフラ自動化と-cicd)
4. [Web フロントエンド技術](#4-web-フロントエンド技術)
5. [サーバーレス（Functions）関連](#5-サーバーレスfunctions関連)
6. [データベース（Cosmos DB）](#6-データベースcosmos-db)
7. [AI / LLM 関連](#7-ai--llm-関連)
8. [スクレイピング技術](#8-スクレイピング技術)
9. [ネットワーク・公開・防御](#9-ネットワーク公開防御)
10. [監視・運用](#10-監視運用)
11. [略語ミニ辞典](#11-略語ミニ辞典)

---

## 1. Azure サービス

### Azure Static Web Apps (SWA)
**何か**: 静的ウェブサイト（HTML/CSS/JS）を世界中に配信できる Azure の PaaS サービス。フロントエンドの「家」。
**本プロジェクト**: React で作った SPA を配信するベースとして利用。Microsoft Entra ID 認証や、バックエンド API のプロキシ機能（linkedBackend）が標準装備されているため、自前で実装しなくて済む。プランは Standard。

### Azure Functions
**何か**: コード（関数）をリクエストが来た時だけ実行してくれるサーバーレスサービス。サーバーの管理や再起動、OS パッチ適用は不要。
**本プロジェクト**: バックエンド API として利用。`/api/exams` などのエンドポイントを Python で実装。

### Azure Cosmos DB
**何か**: Microsoft 製のグローバル分散 NoSQL データベース。世界規模で低レイテンシ。
**本プロジェクト**: ラーニングパス・ユニット・クイズ・ユーザー進捗を保存。Serverless プランで利用量に応じた課金。

### Azure AI Foundry
**何か**: Azure 上で生成 AI（OpenAI モデル等）をホストし、エージェント（プロンプト・モデル・ツール一式の単位）として再利用可能な形に管理するプラットフォーム。
**本プロジェクト**: `summary-agent`（要約用）と `quiz-agent`（クイズ生成用）を Foundry 上に作成し、バックエンドから呼び出す。

### Microsoft Entra ID
**何か**: 旧称 Azure Active Directory。組織のユーザー認証を一元管理する ID 基盤。Microsoft 365 のサインインも同じ仕組み。
**本プロジェクト**: 管理者ログイン用に使用。一般ユーザーは未認証で閲覧可能。

### Managed Identity (MI)
**何か**: Azure リソース（Functions など）に Azure 自身が自動付与する「身分証」。アプリ側が ID/パスワードを持たなくても、他の Azure リソースに対して認証された通信ができる。
**本プロジェクト**: Function App から Cosmos DB と Foundry へのアクセスを **パスワードレス** で実現。ソースコードに secret を一切持たない。

### Application Insights
**何か**: アプリの稼働状況・例外・パフォーマンスを記録する Azure の監視サービス。
**本プロジェクト**: バックエンドのエラー検知・処理時間計測に利用。KQL で過去ログを検索できる。

### Container Apps（言及のみ）
**何か**: コンテナイメージを動かすためのサーバーレスサービス。Functions より自由度が高く、重いライブラリ（Playwright 等）も動かせる。
**本プロジェクト**: 拡張ロードマップ（§9.1）で「Playwright をクラウドで動かす場所」として候補に挙げている。

### Azure Storage
**何か**: ファイル・BLOB（バイナリデータ）を保管するストレージサービス。
**本プロジェクト**: Functions ランタイムが内部的に必要とする領域として利用（自動構成）。

---

## 2. 認証・セキュリティ

### OIDC (OpenID Connect)
**何か**: OAuth 2.0 を拡張した「サインイン用の業界標準プロトコル」。トークン（ID トークン）を使って身元を証明する。
**本プロジェクト**: ユーザーが Entra にサインインする際、SWA と Entra の間で OIDC が走る。GitHub Actions と Azure 間も OIDC で連携。

### Federated Credentials（フェデレーション資格情報）
**何か**: 「外部の ID プロバイダ（GitHub など）に対して、Azure リソースに代わってサインインを許す」設定。クライアントシークレット（パスワード）が不要になる。
**本プロジェクト**: GitHub Actions が Azure にデプロイする際、パスワードを持たずに OIDC でサインインできる。

### UAMI (User Assigned Managed Identity)
**何か**: Managed Identity の一種。複数のリソースから共有できるよう、ユーザー（管理者）が明示的に作成する。
**本プロジェクト**: `ms-learning-deploy` という UAMI を作り、GitHub Actions のフェデレーション資格情報を紐づけ、Azure リソースの作成・更新権限を付与している。

### RBAC (Role-Based Access Control)
**何か**: 「誰に」「どのリソースに対して」「何の操作を」許すかをロールで管理する仕組み。
**本プロジェクト**: Functions のマネージド ID に "Cosmos DB Built-in Data Contributor" ロールを与えて、データ操作を許可している。

### single tenant / multi-tenant
**何か**: Entra アプリ登録の設定。
- single tenant: 自分の組織のユーザーのみサインイン可能
- multi-tenant: 他組織のユーザーもサインイン可能
**本プロジェクト**: single tenant。管理者は社内ユーザー限定。

### EasyAuth
**何か**: Azure App Service / Functions に組み込みの認証機能。サインイン要件をコード変更なしで設定できる。
**本プロジェクト**: SWA-Functions のリンクで自動的に有効化されるが、本プロジェクトでは globalValidation を OFF にし、アプリコードでロール判定する方式を採用。

### `x-ms-client-principal` ヘッダー
**何か**: SWA がバックエンドに転送する HTTP ヘッダーで、サインイン中ユーザーの情報（名前・ロール等）を Base64 エンコードした JSON で渡す。
**本プロジェクト**: `require_admin` 関数がこのヘッダーをデコードして、`admin` ロールがあるかチェックする。

### TLS / HTTPS
**何か**: 通信を暗号化するプロトコル。HTTPS は HTTP の TLS 版。
**本プロジェクト**: ブラウザ↔SWA、SWA↔Functions、Functions↔Cosmos/Foundry、すべて TLS 暗号化。

### Private Endpoint / VNET Integration / WAF / IP allowlist
**何か（強化策の選択肢）**:
- **Private Endpoint**: リソースをインターネットから隔離し、特定の仮想ネットワーク内からのみアクセス可能にする
- **VNET Integration**: Functions などを仮想ネットワークに接続する
- **WAF (Web Application Firewall)**: SQL インジェクション等の攻撃を入口で遮断する
- **IP allowlist**: 特定 IP からのアクセスのみ許可
**本プロジェクト**: 現状は採用していない。「社内限定運用に切り替える場合の強化案」として §4.5 に記載。

---

## 3. インフラ自動化と CI/CD

### IaC (Infrastructure as Code)
**何か**: インフラ（仮想マシン、データベース、ネットワーク等）を **コード（テキストファイル）で記述** し、ボタン一発で再構築できるようにする手法。
**本プロジェクト**: Bicep ファイルでインフラ全体を記述。

### Bicep
**何か**: Azure 専用の IaC 言語。ARM テンプレート（JSON）の簡潔な書き方版。
**本プロジェクト**: `infra/main.bicep` 1 ファイルで Functions / SWA / Cosmos 連携設定などをすべて定義。

### ARM Template
**何か**: Bicep のコンパイル先である JSON 形式のリソース定義。Azure Portal の「カスタムテンプレート」で扱える。
**本プロジェクト**: Bicep がデプロイ時に内部で ARM JSON に変換される。直接編集することはない。

### GitHub Actions
**何か**: GitHub に組み込まれた CI/CD パイプライン。リポジトリへの push 等をきっかけにスクリプトを自動実行できる。
**本プロジェクト**: `infra.yml` `backend.yml` `frontend.yml` の 3 つのワークフローで自動デプロイ。

### CI/CD (Continuous Integration / Continuous Deployment)
**何か**: コード変更を自動的にビルド・テスト・配置まで行う一連の仕組み。
**本プロジェクト**: main ブランチへ push すると、変更されたパス (infra/backend/frontend) に応じて該当ワークフローが起動。

### environment scope（GitHub）
**何か**: GitHub の secrets/variables を「特定の環境（例: prod）でのみ使える」ようスコープを切れる仕組み。デプロイ前の承認者設定なども付けられる。
**本プロジェクト**: prod 環境を作成し、本番用の secret/variable をすべて prod スコープに格納。

### App Settings
**何か**: Azure の Web App / Functions に保管される環境変数のような設定値。コードから `os.environ['...']` で読める。
**本プロジェクト**: AAD_CLIENT_ID, AZURE_OPENAI_ENDPOINT 等をここに保管。Bicep デプロイ時に流し込まれる。

---

## 4. Web フロントエンド技術

### React
**何か**: Meta（旧 Facebook）製の人気 JavaScript UI ライブラリ。ボタン・フォーム等を「コンポーネント」として組み立てる。
**本プロジェクト**: SPA の UI をすべて React で構築。

### Vite
**何か**: 高速な JavaScript / TypeScript のビルドツール。開発サーバー起動も超速い。
**本プロジェクト**: `npm run dev` で開発サーバー、`npm run build` でデプロイ用静的ファイル生成。

### TypeScript
**何か**: JavaScript に型定義を追加した言語。実行前に型エラーを検出できるためバグが減る。
**本プロジェクト**: フロントエンド全コードが TS。

### SPA (Single Page Application)
**何か**: HTML を 1 枚だけ配信し、画面遷移は JavaScript で動的にコンテンツを切り替える方式の Web アプリ。
**本プロジェクト**: React のルーティング機能で複数ページを 1 つの HTML で提供。

### CDN (Content Delivery Network)
**何か**: 世界各地の配信拠点に静的ファイルをキャッシュし、ユーザーから最も近い拠点が応答する仕組み。レイテンシが低い。
**本プロジェクト**: SWA Standard が CDN 配信を内蔵。

### DOM (Document Object Model)
**何か**: ブラウザがロードした HTML のツリー構造。JavaScript はこの DOM を操作することで画面を変える。
**本プロジェクト**: React が裏で DOM を効率的に更新する。Playwright スクレイピング時にも DOM を解析する。

### `fetch` / API
**何か**: ブラウザから別のサーバーに HTTP リクエストを送る JavaScript 標準関数。SPA のデータ取得に使う。
**本プロジェクト**: フロントエンドは `fetch('/api/exams')` のように Functions のエンドポイントを呼ぶ。

### linkedBackend
**何か**: SWA に「このパスのリクエストは Functions などのバックエンドに転送する」と紐付ける機能。
**本プロジェクト**: `/api/*` を Functions に自動転送。SWA がサインイン情報を `x-ms-client-principal` ヘッダーに乗せて転送する。

### `staticwebapp.config.json`
**何か**: SWA のルーティング・認証要件・レスポンス書き換え等を定義する設定ファイル。
**本プロジェクト**: `/api/scrape` は admin 必須、`/api/*` は anonymous 許可、などのルール定義。

---

## 5. サーバーレス（Functions）関連

### Linux Consumption Plan (Y1)
**何か**: Functions の最安ホスティングプラン。Linux ベース、リクエストが来た時だけ起動、アイドル時は無課金。
**制約**: ディスク領域・メモリ（1.5GB）・実行時間（最大 10 分）に制約あり。重いライブラリ（Playwright + Chromium）は動かない。
**本プロジェクト**: アクセスが少ない学習用途に最適なため採用。Playwright の制約は別途回避。

### `host.json`
**何か**: Functions ランタイムの全体設定ファイル。タイムアウト、ロギング、拡張機能の指定など。
**本プロジェクト**: `functionTimeout: "00:10:00"` (Consumption の上限 10 分) を設定。

### `function_app.py`
**何か**: Python v2 モデルでの Functions のメインエントリポイント。ルート定義をデコレータ (`@app.route`) で書く。
**本プロジェクト**: API 全エンドポイントの定義をここに集約。

### `requirements.txt`
**何か**: Python 依存ライブラリ一覧。デプロイ時にこれを元にライブラリがインストールされる。
**本プロジェクト**: 本番依存（aiohttp, beautifulsoup4 等）を `requirements.txt`、Playwright のような重い開発専用依存は `requirements-dev.txt` に分離。

### `local.settings.json`
**何か**: ローカル開発時の Functions 環境変数を定義するファイル。本番では App Settings が同役を担う。
**本プロジェクト**: 管理者がローカル PC で `func start` する際に Cosmos エンドポイントや Foundry URL を指定。

### `func start`
**何か**: Azure Functions Core Tools コマンド。ローカル PC で Functions ランタイムを起動する。
**本プロジェクト**: 管理者がローカルで `func start --port 7071` を実行してカタログスクレイプ機能を使う。

### `AuthLevel.ANONYMOUS` / `AuthLevel.FUNCTION`
**何か**: Functions の HTTP トリガー認証レベル。
- ANONYMOUS: 誰でも呼べる
- FUNCTION: 関数キー（API Key）が必要
**本プロジェクト**: ANONYMOUS。SWA が `x-ms-client-principal` で渡す情報をコード側で検証する設計。

### `WEBSITE_RUN_FROM_PACKAGE`
**何か**: Functions / App Service が「指定された URL の zip ファイルから実行する」モード。デプロイ手段の一つ。
**本プロジェクト**: GitHub Actions のデプロイがこのモードを使い、ビルドした zip を Storage に置いて Function App にその URL を伝える。

### Sync Trigger
**何か**: Functions のデプロイ後、ホストにトリガー定義を再読み込みさせる API 操作。
**本プロジェクト**: 過去にここで失敗（"malformed content"）したことがあり、原因は zip サイズ過大（Playwright 入り）と host.json の不正設定だった。両方修正済み。

---

## 6. データベース（Cosmos DB）

### NoSQL API
**何か**: Cosmos DB がサポートする 5 つの API のうち、JSON ドキュメントを直接保存・SQL ライクに検索できる API。
**本プロジェクト**: ラーニングパス・ユニット等を JSON で保管。リレーショナル DB ほど厳格なスキーマ設計が不要。

### RU (Request Units)
**何か**: Cosmos DB の処理コストの単位。読み込み・書き込み・クエリ操作ごとに RU を消費する。
**本プロジェクト**: Serverless プランで利用、利用 RU に応じて課金。

### Serverless プラン (Cosmos DB)
**何か**: 利用 RU に応じた従量課金、アイドル時はほぼ無課金。低トラフィック向き。
**本プロジェクト**: 学習者が多い時間帯だけ RU を使うパターンに合致するため採用。

### partition key（パーティションキー）
**何か**: Cosmos DB がデータを内部的に分散保管する単位。クエリ性能とコストに大きく影響する。
**本プロジェクト**: `learning_paths` は `/exam_id`、`units` は `/learning_path_id` 等で分散。

### `disableLocalAuth: true`
**何か**: Cosmos DB のキーベース認証（主キー文字列でアクセス）を無効化し、Entra ID 認証のみ受け付けるようにする設定。
**本プロジェクト**: 万が一接続文字列が漏れても不正アクセスを防げる。マネージド ID + RBAC で常時アクセス。

### point read
**何か**: パーティションキー + id を指定してドキュメントを 1 件取る最速の読み方。RU 消費が最小（通常 1 RU）。
**本プロジェクト**: 性能チューニングの選択肢として §6.3 に記載。

### Cosmos Vector Search（言及のみ）
**何か**: Cosmos DB のベクトル検索機能。AI 埋め込みベクトルを使った類似検索が可能。
**本プロジェクト**: 模擬試験モード等の拡張ロードマップ（§9.2）で候補。

---

## 7. AI / LLM 関連

### LLM (Large Language Model)
**何か**: 大量のテキストで学習された大規模言語モデル。文章生成・要約・質問応答ができる。
**本プロジェクト**: 要約とクイズ生成の中核。

### gpt-5.4 / gpt-5-mini / o3-mini
**何か**: OpenAI 系のモデル名。
- gpt-5.4: 高品質・高コスト・遅め
- gpt-5-mini / o3-mini: 速い・安い・品質はやや劣る
**本プロジェクト**: gpt-5.4 を採用中。コスト最適化として mini 系へ切替が候補（§6.3）。

### Foundry Agents
**何か**: Foundry 上で「プロンプト + モデル + ツール + 出力スキーマ」を 1 つのエンドポイントとしてラップしたもの。再利用しやすい。
**本プロジェクト**: `summary-agent` と `quiz-agent` を作成し、バックエンドから URL 1 本を叩くだけで利用。

### `reasoning.effort`（推論努力レベル）
**何か**: モデルがどれだけ深く考えるかの設定値（low / medium / high）。
- low: 速い・浅い
- high: 遅い・深い
**本プロジェクト**: 当初 high で 45 秒超かかることがあったため medium に変更。応答時間が約 30% 短縮。

### `tool_choice` / `web_search` ツール
**何か**:
- `tool_choice`: モデルがツール（外部関数）をいつ呼ぶかの設定（auto / required / none）
- `web_search`: モデルが Web を検索できる組み込みツール
**本プロジェクト**: 当初 required (毎回 web 検索) だったため遅かった → auto (モデル判断) に変更し、不要な検索を抑制。

### TPM (Tokens Per Minute)
**何か**: AI モデルの 1 分あたり処理可能トークン数。デプロイメントごとに上限がある。
**本プロジェクト**: gpt-5.4 deployment の TPM 5000。同時実行が多いと制限に当たる。

### prompt-based agent
**何か**: モデルへの指示文（プロンプト）と数行の設定だけで作れるシンプルな Foundry エージェント形態。
**本プロジェクト**: summary-agent / quiz-agent はこの形式。

### token（トークン）
**何か**: LLM が文章を扱う最小単位。日本語 1 文字 ≒ 1〜3 token、英単語 1 個 ≒ 1〜2 token のイメージ。
**本プロジェクト**: 課金単位がトークン数なので、長文を送ると料金増。要約入力は 6000 文字に制限。

### JSON Schema 出力
**何か**: AI に「こういう構造の JSON で答えてください」と強制できる機能。
**本プロジェクト**: quiz-agent が「3 問 × 4 択 + 正解 + 解説」の決まった JSON を返すよう Schema を指定。

---

## 8. スクレイピング技術

### スクレイピング (Scraping)
**何か**: Web ページから情報を機械的に抜き出す行為。
**本プロジェクト**: Microsoft Learn のラーニングパス・ユニットを取り込むコア機能。

### Playwright
**何か**: ブラウザ（Chromium 等）を **プログラムから自動操縦** するライブラリ。JavaScript 実行後の DOM を取得できる。
**重さ**: ブラウザバイナリ約 200MB + 実行時 RAM 数百 MB。
**本プロジェクト**: 認定試験ページなど **JS で動的にリンクを生成するページ** の解析に必須。Linux Consumption では動かないので **管理者ローカル PC のみ** で実行。

### Chromium
**何か**: Google Chrome や Microsoft Edge の元になっているオープンソースのブラウザエンジン。
**本プロジェクト**: Playwright が裏で起動するブラウザ。

### headless ブラウザ
**何か**: 画面表示なしでバックグラウンド動作するブラウザ。スクレイピングや自動テストに使う。
**本プロジェクト**: Playwright を headless モードで起動。

### aiohttp
**何か**: Python の **非同期 HTTP クライアント** ライブラリ。Playwright のようなブラウザ起動なしに HTTP リクエストだけする軽量ツール。
**本プロジェクト**: ユニット本文の取得（Microsoft Learn のページが静的 HTML だったため、これだけで十分）。本番 Linux Consumption で動作。

### BeautifulSoup (bs4)
**何か**: HTML をパースして「このタグの中身を取り出す」「このセレクタの要素を消す」等を Python から簡単に操作できるライブラリ。
**本プロジェクト**: aiohttp で取得した HTML から本文だけ抽出、不要なヘッダー・フッターを除去、リンクを Markdown 形式に書き換える等の処理。

### server-rendered (SSR) HTML
**何か**: サーバー側で HTML を完成形に組み立ててから返す形式。JavaScript 実行なしでも内容が見える。
**本プロジェクト**: Microsoft Learn のユニットページがこの形式だったため、Playwright 不要と判明した。

### CSS セレクタ
**何か**: HTML 要素を指定するための表記法（例: `main#main`、`div.content`）。
**本プロジェクト**: BeautifulSoup の `select()` メソッドでコンテンツエリアを特定するのに使用。

### Markdown
**何か**: テキストで書ける軽量マークアップ言語。`# 見出し`、`**太字**`、`[text](url)` などのシンプル記法。
**本プロジェクト**: 要約の出力形式として利用。フロントは ReactMarkdown ライブラリでレンダリング。

---

## 9. ネットワーク・公開・防御

### public endpoint
**何か**: インターネットから直接アクセスできる URL を持つリソース。
**本プロジェクト**: Function App は public endpoint 状態（mslearn-func.azurewebsites.net）。

### 認可マトリクス (authorization matrix)
**何か**: 「どの操作を、どのロールが、どのリソースに対してできるか」の対応表。
**本プロジェクト**: §4.2 で各 API ルートに対する SWA ガード × Function ガードを表形式で示している。

### globalValidation
**何か**: EasyAuth の設定項目。「すべてのリクエストで認証必須」にするか「未認証でもアプリに渡す」かを選べる。
**本プロジェクト**: OFF（未認証も通す）に設定し、アプリ側で必要な箇所のみガード。

### linkedBackend timeout
**何か**: SWA が backend にリクエストを転送する際の応答待ち時間制限。Standard プランは 45 秒固定。
**本プロジェクト**: AI 呼び出しが 45 秒超で失敗する問題を「ポーリング」で回避（§5.1）。

### CORS (Cross-Origin Resource Sharing)
**何か**: 異なるドメインの API を呼ぶ際のブラウザのセキュリティ規則。
**本プロジェクト**: SWA と Functions が同一オリジン（linkedBackend）なので基本不要。SWA hostname を Functions の許可リストに追加して念のため対応済み。

---

## 10. 監視・運用

### KQL (Kusto Query Language)
**何か**: Application Insights や Log Analytics のログ検索用 SQL ライク言語。`|`（パイプ）で処理を繋ぐ。
**本プロジェクト**: 例外検索などに利用。
```kusto
exceptions | where timestamp > ago(1h) | take 10
```

### traces / exceptions / requests
**何か**: Application Insights が記録する代表的なテーブル。
- traces: アプリのログメッセージ
- exceptions: 例外スタックトレース
- requests: HTTP リクエスト記録
**本プロジェクト**: KQL でこれらを検索して障害解析。

### dependency tracking
**何か**: アプリが呼び出した外部 API（Cosmos、Foundry 等）の応答時間や成否を記録する機能。
**本プロジェクト**: Foundry エージェントの応答時間が変動する様子をここで追跡できる。

### point-in-time restore (PITR)
**何か**: データベースを過去の任意の時点の状態に巻き戻す機能。
**本プロジェクト**: Cosmos の標準バックアップで 30 日まで遡って復元可能。

---

## 11. 略語ミニ辞典

頻出する略語の対応表。

| 略語 | 正式名 | 一言 |
|---|---|---|
| SWA | Static Web Apps | Azure の静的サイトホスティング |
| MI | Managed Identity | Azure 内部での「身分証」 |
| UAMI | User Assigned Managed Identity | 共有可能な MI |
| OIDC | OpenID Connect | サインイン用業界標準プロトコル |
| RBAC | Role-Based Access Control | ロールベースのアクセス制御 |
| IaC | Infrastructure as Code | インフラをコードで定義 |
| CI/CD | Continuous Integration / Delivery | 自動ビルド & デプロイ |
| LLM | Large Language Model | 大規模言語モデル |
| TPM | Tokens Per Minute | LLM の 1 分処理上限 |
| RU | Request Unit | Cosmos DB の処理コスト単位 |
| SPA | Single Page Application | 1 枚 HTML で動的画面遷移 |
| CDN | Content Delivery Network | 世界中に配信キャッシュ |
| PaaS | Platform as a Service | プラットフォームのサービス |
| KQL | Kusto Query Language | Azure ログ検索用言語 |
| WAF | Web Application Firewall | アプリ層のファイアウォール |
| VNET | Virtual Network | Azure 仮想ネットワーク |
| DOM | Document Object Model | HTML のツリー構造 |
| SSR | Server-Side Rendering | サーバー側で HTML 完成形を返す |
| API | Application Programming Interface | プログラム間のやり取り口 |
| HTTP/HTTPS | HyperText Transfer Protocol (Secure) | Web 通信プロトコル |
| TLS | Transport Layer Security | 通信暗号化 |

---

## 補足: 本プロジェクトで「使っていない」が報告書に登場する用語

念のため、強化案や将来計画で言及される技術も一言だけ:

| 用語 | 用途 |
|---|---|
| Container Apps Job | コンテナを cron 的に or オンデマンド実行するサービス。Playwright クラウド化の候補 |
| Functions Premium | Consumption の上位プラン。常時起動・ネットワーク統合・タイムアウト緩和 |
| Front Door | Azure の CDN + WAF 統合サービス。本格的な公開時の入口 |
| Entra B2B | 別組織のユーザーをゲストとして招待する仕組み。マルチテナント拡張で使用 |
| Service Bus | Azure のメッセージングサービス。非同期処理キューに使用 |
| Durable Functions | 長時間処理を分割実行する Functions 拡張 |
