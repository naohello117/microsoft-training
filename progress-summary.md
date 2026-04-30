# 進捗サマリー

## 最終更新：2026-04-26

---

## ✅ 完了した作業

### 2026-04-26（第4セッション）

**機能追加（汎用URL投入・再要約）→ Entra ID 管理者認証 → 本番デプロイ用 IaC + CI/CD 整備。**

- **トップページに汎用URL投入機能を追加**
  - `ExamListPage.tsx` に URL 入力フォームを設置 — 任意の試験URLを投入してコレクションが自動追加される
  - 試験ID判別ロジックをバックエンド側 (`scrape_from_url`) に集約 — フロントは `isSupportedUrl()` で軽くチェックするだけ
  - レスポンスに `exam_id` / `exam_name` を含める形に拡張し、UI 側で「○○ に N 件追加しました」と表示

- **超汎用URL対応（認定資格ページ自体を解決）**
  - 例: `/credentials/certifications/azure-network-engineer-associate/?practice-assessment-type=certification`（AZ-700）
  - `_extract_exam_ids_from_certification_page()` を新規追加 — `/credentials/certifications/exams/<id>/` リンク + HTML 内の `exam.XX-NNN` パターンの両方を抽出
  - 認定資格ページ → 試験ページ → コース → パス を再帰的に解決

- **再要約機能（`force=true` / `↻ 再要約` ボタン）**
  - `GET /api/content/{id}?force=true` でキャッシュを無視して summary-agent に再投入
  - `UnitPage.tsx` の要約見出し横に「↻ 再要約」ボタンを追加（管理者のみ表示・後述）
  - 進捗インジケータを再利用

- **Entra ID 管理者認証（コスト保護）**
  - 動機：本番公開時に悪意あるユーザーが過剰スクレイピング・AI生成を呼び出すコスト爆発を防ぐ
  - 方針：**読み取りは全公開、コスト発生操作は管理者限定**。Entra ID で `admin` ロールを持つユーザーだけがスクレイピング/再要約できる
  - **多層防御**：
    1. `staticwebapp.config.json` のルートで `POST /api/scrape` と `PATCH /api/learning-paths/*` を `allowedRoles: ["admin"]` に
    2. バックエンド `shared/auth.py` の `require_admin()` で `x-ms-client-principal` をデコード → 二重ガード
  - **エンドポイントごとの方針**：
    - `POST /api/scrape`: 管理者のみ
    - `PATCH /api/learning-paths/*`: 管理者のみ
    - `GET /api/content/{id}` キャッシュあり: 全員可
    - `GET /api/content/{id}` 初回生成: **全員可**（管理者が全パスを事前生成する負担を回避するため）
    - `GET /api/content/{id}?force=true`: 管理者のみ
    - `POST /api/quiz/{id}` 初回生成: **全員可**
    - `POST /api/quiz/{id}` キャッシュあり: 全員可
  - **ローカル開発バイパス**：
    - バックエンド: `LOCAL_ADMIN_BYPASS=true` （`local.settings.json`）
    - フロント: `VITE_LOCAL_ADMIN_BYPASS=true` （`.env.local`）
    - これで `/.auth/me` が無いローカルでも管理者UIで動作確認できる

- **フロント認証UI**
  - `frontend/src/auth.tsx` 新規作成 — `AuthProvider` + `useAuth()` フック + `AUTH_URLS`
  - `App.tsx`：ヘッダー右側に「管理者サインイン」リンク or ユーザー名+「管理者」バッジ+「サインアウト」
  - `ExamListPage.tsx` / `ExamPage.tsx`：URL入力フォームと注釈を `isAdmin` で条件付き表示
  - `UnitPage.tsx`：「↻ 再要約」ボタンを管理者のみ表示。「クイズを生成する」ボタンは全員に表示（初回生成OK方針のため）

- **本番デプロイ準備（IaC + CI/CD）**
  - **`infra/main.bicep` 大幅拡張**：
    - SWA を **Free → Standard** に変更（linkedBackend を使うため必須・$9/月）
    - 既存 Cosmos `cosmos-training-murokawa` を `existing` 参照で再利用（破壊しない）
    - Function App: 全 App Settings (`COSMOS_*`, `AZURE_OPENAI_*`, `FOUNDRY_AGENT_URL_*`) + `DISABLE_SCRAPE=true` + `LOCAL_ADMIN_BYPASS=false`
    - SWA `linkedBackends` で Function App を `/api/*` として連携
    - SWA appSettings に `AAD_CLIENT_ID` / `AAD_CLIENT_SECRET` を注入
    - Application Insights を新規追加（Functions 監視用）
    - System-Assigned MI に Cosmos DB Built-in Data Contributor を付与
  - **GitHub Actions 3本作成**：
    - `.github/workflows/infra.yml` — `infra/**` 変更時に Bicep デプロイ
    - `.github/workflows/backend.yml` — `backend/**` 変更時に Functions デプロイ（Oryx remote build）
    - `.github/workflows/frontend.yml` — `frontend/**` 変更時に SWA デプロイ。PR は自動でプレビュー環境
    - 認証はすべて **OIDC (Workload Identity Federation)** で長期シークレット不要
  - **本番でスクレイピング無効化**：
    - `_scrape_disabled()` ヘルパーを `function_app.py` に追加
    - `POST /api/scrape` と `GET /api/content/{id}` の遅延スクレイピング経路で 503 を返す
    - 運用：管理者がローカルで `func start` し、本番 Cosmos に直接書き込み（Playwright のためにコンテナ化するコストを回避）

- **ドキュメント**
  - `docs/deployment.md` 新規作成 — アーキ図 / 初回手動セットアップ全手順（RG / Entra IDアプリ / UAMI+OIDC / Bicepデプロイ / SWA トークン / 管理者ロール / GitHub Secrets/Variables）/ 運用フロー / トラブルシュート / コスト見積
  - `README.md` に「本番デプロイ・CI/CD」セクションを追加

### 2026-04-22（第3セッション）

**AIエージェント化（Foundry Agents / Responses API）・進捗UI改善・リンク保持・認定試験URL対応。**

- **Foundry Agents 化（Chat Completions → Responses API）**
  - Foundry Portal で `summary-agent` / `quiz-agent` を作成し、アプリから `/protocols/openai/responses?api-version=2025-11-15-preview` を呼び出す方式に変更
  - プロンプトは Foundry Portal 側の Instructions で管理 → **アプリ再デプロイ不要で更新可能**
  - `quiz-agent` は Response format = **JSON Schema**（`strict: true`）で厳密な出力構造を保証
  - 認証は Managed ID（ローカルは `az login`）＋ トークンスコープ `https://ai.azure.com/.default`、5分バッファでキャッシュ
  - 既存の `openai_client.py` に依存する Chat Completions 経路は廃止

- **`shared/foundry_agent.py` 新規作成**
  - `aiohttp` で Responses API に直接 POST
  - `_extract_text()` で `output_text` / `output[].content[].text` どちらのレスポンス形にも対応

- **UI 進捗インジケータ**
  - 要約・クイズ生成中に「① 取得中 → ② 生成中 → ③ 最終調整中 → ④ まだ処理中」と秒数付きで段階表示
  - スピナーCSS + `setInterval(250ms)` で経過秒更新

- **リンク改善（フロント）**
  - Markdown リンクを `target="_blank"` で別タブ表示
  - URL を en-us → ja-jp に自動書き換え（`toJaLocaleHref`）

- **根本原因調査：新規要約にリンクが出ない問題**
  - 原因：`_scrape_unit_content` が `el.innerText` を使っており `<a href>` の URL が捨てられていた
  - これまで出ていた URL は AI のハルシネーション（学習データからの推測）の可能性大
  - **対策：** スクレイパーで `<a href>` を `[text](href)` 形式に事前変換してから `innerText` 抽出
  - summary-agent の Instructions に「リンクの扱い」ルールを追記（入力の URL をそのまま保持・創作禁止）
    → ユーザー側で Foundry Portal に反映する運用

- **認定試験URL対応（SC-100 対応）**
  - `/credentials/certifications/exams/<id>/` パターンを新規サポート
  - `_extract_links_from_certification()` を追加 — ページ内の `/training/courses/` と `/training/paths/` を分けて抽出
  - 直接リンクのパス + コース経由のパスを統合・重複排除
  - `ExamPage.tsx` の入力欄プレースホルダと例示も更新

### 2026-04-19（第2セッション）

**UIを3階層構造に刷新。バックエンドに試験コレクション概念を追加。**

- **UI 3階層リデザイン**
  - 試験一覧 `/` → ラーニングパス一覧 `/exam/:examId` → ユニット一覧 `/path/:pathId` → 学習 `/unit/:unitId`
  - `ExamListPage.tsx`：AZ-500 / SC-300 / SC-100 のカードを表示（未スクレイピングでも表示）
  - `ExamPage.tsx`：試験ごとにラーニングパス一覧 + URLスクレイピングフォーム
  - `PathPage.tsx`：モジュール展開 + ユニット行（要約済バッジ）
  - `UnitPage.tsx`：← 戻るボタン追加

- **バックエンド API 追加**
  - `GET /api/exams`：learning_paths から試験一覧を集計して返す
  - `GET /api/learning-paths?exam_id=az-500`：試験IDでフィルタ
  - `PATCH /api/learning-paths/{path_id}`：既存パスに exam_id / exam_name を後付けで設定
  - `POST /api/scrape` に `exam_id` / `exam_name` パラメータを追加

- **既存データの移行**
  - `manage-identity-and-access` を PATCH で `exam_id: "az-500"` にタグ付け済み
  - `GET /api/exams` が `[{"exam_id":"az-500","exam_name":"AZ-500","path_count":1}]` を返すことを確認

### 2026-04-19（第1セッション）

**アプリ全体の骨格を実装。ローカルでの Cosmos DB・Foundry 接続確認まで完了。**

- **Cosmos DB 設計・構築**
  - 4コンテナ設計（`learning_paths` / `units` / `quizzes` / `user_progress`）
  - Azure CLI でサーバーレスアカウントにDB・コンテナを作成（`--throughput` 不要）
  - ローカル開発ユーザーに `Cosmos DB Built-in Data Contributor` RBACロールを付与
  - Git Bash での `/` パス変換バグ → `MSYS_NO_PATHCONV=1` で回避

- **Azure Functions バックエンド（Python）**
  - v2 プログラミングモデル（`function_app.py` 単ファイル + `@app.route` デコレータ）
  - `POST /api/scrape` : URL受付→スクレイピング→Cosmos DB保存
  - `GET /api/content/{unit_id}` : 要約キャッシュ取得 or OpenAIで生成
  - `POST /api/quiz/{unit_id}` : 4択クイズ生成（キャッシュあり再利用）
  - `GET/POST /api/progress/{user_id}` : 学習進捗の読み書き
  - `GET /api/units/{module_id}` : モジュール内ユニット一覧（`c["order"]` で予約語回避）
  - `GET /api/learning-paths` : ラーニングパス一覧

- **Azure AI Foundry 接続の修正（ハマりポイント）**
  - `local.settings.json` のエンドポイントが `services.ai.azure.com/api/projects/...` 形式
  - `AzureOpenAI` SDK では audience・APIバージョンが合わず接続不可
  - `azure-ai-projects` SDK の `AIProjectClient.get_openai_client()` に切り替えで解決

- **スクレイピングロジック（Playwright）**
  - `page.evaluate()` を使い ElementHandle の無効化バグを回避
  - モジュールスラッグ正規表現でユニットURL以外を除外
  - セレクタを `page.evaluate(js, args)` の引数で渡しクォート衝突を回避

- **フロントエンド（React + Vite + TypeScript）**
  - ダッシュボード：URL入力・スクレイピング開始
  - ユニットページ：要約表示 + 4択クイズ・回答判定・進捗保存
  - `tsconfig.json` 追加でコンパイルエラー解消

- **接続テスト結果**
  - Cosmos DB ✅（`learning_paths` コンテナへのクエリ成功）
  - Azure AI Foundry gpt-4o ✅（`azure-ai-projects` SDK 経由で応答確認）
  - スクレイピング ✅（`manage-identity-and-access` 128ユニット取得・保存済み）

---

## 🔧 技術的な決定事項・注意点

- **Playwright を本番 Functions に持ち込まない方針**：Consumption (Y1) Linux ではブラウザバイナリ + 共有ライブラリの導入が困難。Premium Plan やコンテナ化は月¥10,000+/¥1,000+ のコスト増。代わりに **管理者がローカルで `func start` → 本番 Cosmos に直接書き込む運用** を採用。本番では `DISABLE_SCRAPE=true` で 503 を返して経路自体を塞ぐ。

- **SWA は Standard tier 必須**：linkedBackend 機能（`/api/*` を別 Function App に転送）は Free tier では使えない。+$9/月コストはかかるが、これにより Function App 側で MI 認証 + 自由な依存関係（Playwright 等）が使える設計になる。Free tier の Managed Functions に詰め込む案は MI 不可・Cosmos キーが必要になりセキュリティで劣る。

- **既存 Cosmos / Foundry の再利用**：Bicep で `existing` キーワード参照に切り替え、新規作成しない。`rg-microsoft-training` 内の `cosmos-training-murokawa` / `foundry-training-murokawa` は手で作った既存リソース。新規作成されるのは Functions / SWA / Storage / App Insights の4つだけ。

- **二層認証アーキテクチャ**：SWA `staticwebapp.config.json` のルート保護はネットワークレイヤー（外部からの直接POSTを弾く）、バックエンド `require_admin()` はアプリレイヤー（Functions URL を直接叩かれた場合の保険）。両方が必要。

- **初回生成は全員 OK 方針**：「再要約・スクレイピングのみ管理者限定」とすることで、コンテンツ運用負担を分散。管理者は初回スクレイピングのみ行えば、ユニット閲覧で初回要約は一般ユーザーが各自トリガーできる。

- **OIDC (Workload Identity Federation) 採用**：GitHub Actions ↔ Azure 間の認証は長期 Service Principal シークレットでなく OIDC。User-Assigned Managed Identity に GitHub の `repo:owner/repo:ref:refs/heads/main` と `:pull_request` を `subject` として federated credential を作成。

- **Foundry Agents（Responses API）採用**：プロンプト変更のたびに再デプロイ不要。Foundry Portal で Instructions / Model / Temperature を編集 → 即反映。`quiz-agent` は JSON Schema（strict）で出力構造を保証する。

- **innerText は `<a href>` の URL を捨てる**：スクレイパーで AI に渡す前に DOM を `[text](href)` に書き換えるパターン必須。URL 情報を保持しないと AI が URL をハルシネーションする。

- **summary-agent の Instructions はコードではなく Foundry Portal で管理**：`docs/foundry-agents.md` はソースオブトゥルースの仕様書として扱い、変更時はユーザーが Portal に反映する運用。

- **Foundry エンドポイント形式**：`services.ai.azure.com/api/projects/<proj>` 形式は `azure-ai-projects` SDK 必須。`openai` SDK の `AzureOpenAI` では接続不可。

- **`func start` は必ず `.venv` 有効化後に**：忘れると system Python 3.14 が使われて `aiohttp` 等が import 失敗する。

- **Cosmos DB サーバーレス**：`--throughput` オプション不可。`disableLocalAuth: true` のためキー認証は使わず MI 経由。

- **Git Bash のパス変換**：`az cosmosdb ... --scope "/<path>"` で `/` がWindowsパスに変換されるバグ。`MSYS_NO_PATHCONV=1` で回避。

- **`order` は Cosmos DB の予約語**：`SELECT c["order"]` と書くこと。

- **フロントエンドの `USER_ID`**：`UnitPage.tsx` 内で `"demo-user"` にハードコード。本番化時は `useAuth().principal.userId` から取得するよう変更が必要（Entra ID 認証は実装済みなので簡単に直せる）。

---

## 📋 残課題・ネクストアクション

### 優先度：高（次回セッションで必ず着手）

- [ ] **本番デプロイ手順の実行**（`docs/deployment.md` の Step 1〜7）
  - Step 2: Entra ID アプリ登録 → AAD_CLIENT_ID / AAD_CLIENT_SECRET / TENANT_ID を取得
  - Step 3: User-Assigned Managed Identity 作成 + GitHub OIDC federation
  - Step 4: 初回 Bicep デプロイ（`az deployment group create`）→ 新規 4 リソース作成
  - Step 5-6: SWA デプロイトークン取得 + 管理者ロール付与
  - Step 7: GitHub Secrets / Variables 登録 → `git push` で CI/CD 起動

- [ ] **`staticwebapp.config.json` の `<tenant-id>` を実テナントIDに置換**
  - 現在プレースホルダのまま。Step 2 で取得したテナントIDで置換してコミット

- [ ] **Foundry Portal の summary-agent Instructions を更新**（前セッションからの持ち越し）
  - `docs/foundry-agents.md` の「# リンクの扱い」セクションを Portal に貼り付け
  - これをやらないと AI がリンクを創作する可能性が残る

### 優先度：中

- [ ] **`UnitPage.tsx` の `USER_ID` ハードコード解消**
  - `useAuth().principal?.userId` から取得するよう変更
  - 一般ユーザーも認証されている場合（Entra IDサインイン）は実IDを使う

- [ ] **新しいスクレイパー（リンク保持版）の本番動作確認**
  - 未キャッシュのユニットで要約→リンクが Markdown で表示・別タブで開き・ja-jp URL になることを目視確認

- [ ] **SC-100 / SC-300 のラーニングパスをスクレイピング**
  - 今は AZ-500 のみ。本番 Cosmos に向けて管理者ローカル運用フローで投入

- [ ] **要約プロンプトのチューニング確認**
  - 実コンテンツで要約を生成し品質を目視確認

### 優先度：低

- [ ] **未使用コード整理**
  - `frontend/src/pages/Dashboard.tsx`（旧ダッシュボード、ルート未登録だがビルド時に型エラー）
  - `backend/shared/openai_client.py`（Foundry Agents 移行後に未使用）
  - `backend/scraping/__pycache__` / `backend/__pycache__` を `.gitignore` に追加（既に追加済みなら不要）

- [ ] **進捗ダッシュボード**
  - 完了率・スコアのグラフ表示
  - エラートースト実装

- [ ] **Bicep で Foundry / Cosmos を `existing` 参照する代わりに、IaC で完全管理する選択肢の検討**
  - 現状は手作りリソースを使い回しているため、別環境（dev/staging）を立てたい場合に再現性が落ちる
  - 必要になった時点で対応

---

## 🗂 プロジェクト構成・環境メモ

```
microsoft-training/
├── backend/                        # Azure Functions (Python v2)
│   ├── function_app.py             # 全エンドポイント + DISABLE_SCRAPE / require_admin ガード
│   ├── scraping/ms_learn_scraper.py  # Playwright + リンク保持版
│   ├── shared/cosmos_client.py
│   ├── shared/foundry_agent.py     # Responses API 呼び出し
│   ├── shared/auth.py              # ★NEW (4/26): x-ms-client-principal デコード + admin判定
│   ├── shared/openai_client.py     # （未使用、削除候補）
│   ├── local.settings.json         # ローカル環境変数（git管理外推奨）
│   └── requirements.txt
├── frontend/                       # React + Vite + TypeScript
│   ├── .env.local                  # ★NEW (4/26): VITE_LOCAL_ADMIN_BYPASS=true (ローカル管理者扱い)
│   ├── staticwebapp.config.json    # SWA 認証 + ロールベースルート保護
│   └── src/
│       ├── auth.tsx                # ★NEW (4/26): AuthProvider + useAuth() + AUTH_URLS
│       ├── pages/ExamListPage.tsx  # / : 試験カード一覧 + 汎用URL投入フォーム (admin)
│       ├── pages/ExamPage.tsx      # /exam/:examId : ラーニングパス一覧 + URL投入 (admin)
│       ├── pages/PathPage.tsx      # /path/:pathId : ユニット一覧
│       ├── pages/UnitPage.tsx      # /unit/:unitId : 要約 + クイズ + 再要約ボタン (admin)
│       ├── api/client.ts           # 型付きAPIクライアント (force=true / exam_id 対応)
│       └── App.tsx                 # ルーティング + AuthProvider + ヘッダー認証コントロール
├── infra/main.bicep                # 既存Cosmos参照 / SWA Standard / Functions / linkedBackend
├── docs/
│   ├── deployment.md               # ★NEW (4/26): 本番デプロイ全手順
│   └── foundry-agents.md           # Foundry Agents 仕様書（Portal設定のソース）
├── .github/workflows/              # ★NEW (4/26)
│   ├── infra.yml                   # Bicep デプロイ (OIDC)
│   ├── backend.yml                 # Functions デプロイ (OIDC + Oryx)
│   └── frontend.yml                # SWA デプロイ (PR プレビュー対応)
├── progress-summary.md
└── README.md                       # 本番デプロイセクション追加済
```

**接続先リソース（rg-microsoft-training）**

| リソース | 名前 | 状態 |
|---|---|---|
| リソースグループ | `rg-microsoft-training` | 既存 (japaneast) |
| Cosmos DB アカウント | `cosmos-training-murokawa` | 既存（Bicep `existing` 参照） |
| Cosmos DB データベース | `cosmos-training-murokawa` | 既存 |
| Azure AI Foundry | `foundry-training-murokawa` | 既存 |
| Foundry プロジェクトエンドポイント | `https://foundry-training-murokawa.services.ai.azure.com/api/projects/proj-default` | 既存 |
| OpenAI デプロイ名 | `gpt-4o` | 既存 |
| summary-agent URL | `.../applications/summary-agent/protocols/openai/responses?api-version=2025-11-15-preview` | 既存 |
| quiz-agent URL | `.../applications/quiz-agent/protocols/openai/responses?api-version=2025-11-15-preview` | 既存 |
| **Function App (新規)** | `mslearn-func` | Bicep で作成予定 |
| **App Service Plan (新規)** | `mslearn-plan` (Y1 / Linux) | Bicep で作成予定 |
| **Static Web Apps (新規)** | `mslearn-swa` (Standard) | Bicep で作成予定 |
| **Storage Account (新規)** | `mslearnst` | Bicep で作成予定 |
| **Application Insights (新規)** | `mslearn-ai` | Bicep で作成予定 |

**環境変数（`backend/local.settings.json`）**

| キー | 用途 |
|---|---|
| `COSMOS_DB_ENDPOINT` | Cosmos DB のエンドポイント |
| `COSMOS_DB_DATABASE` | Cosmos DB のデータベース名 |
| `FOUNDRY_AGENT_URL_SUMMARY` | summary-agent の Responses API URL |
| `FOUNDRY_AGENT_URL_QUIZ` | quiz-agent の Responses API URL |
| `AZURE_OPENAI_ENDPOINT` | （旧 Chat Completions 経由・現在は未使用） |
| `AZURE_OPENAI_DEPLOYMENT` | （旧 Chat Completions 経由・現在は未使用） |
| `LOCAL_ADMIN_BYPASS` | `true` でローカル開発時に管理者扱いになる（本番では絶対 false） |

**環境変数（`frontend/.env.local`）**

| キー | 用途 |
|---|---|
| `VITE_LOCAL_ADMIN_BYPASS` | `true` で `/.auth/me` が無いローカルでも管理者UIを表示 |

**スクレイピング済みデータ**

| 試験 | ラーニングパスID | ユニット数 |
|---|---|---|
| AZ-500 | `manage-identity-and-access` | 128 |

**Claude Code スキルコマンド**

| コマンド | タイミング | 内容 |
|---|---|---|
| `/save-progress` | セッション終了時 | 今日の作業・ハマりポイント・ネクストアクションをこのファイルに書き出す |

**ローカル開発の起動手順**
```bash
# 1. ストレージエミュレーター（別ターミナル）
npx azurite

# 2. バックエンド（※ .venv 有効化を忘れない）
cd backend
source .venv/Scripts/activate
func start --port 7071
# → http://localhost:7071

# 3. フロントエンド（別ターミナル）
cd frontend && npm run dev
# → http://localhost:5173
```

**APIエンドポイント一覧（admin 必要かどうか）**

| メソッド | パス | 一般 | 管理者 |
|---|---|---|---|
| GET | `/api/exams` | ✅ | ✅ |
| GET | `/api/learning-paths?exam_id=az-500` | ✅ | ✅ |
| PATCH | `/api/learning-paths/{path_id}` | ❌ 403 | ✅ |
| POST | `/api/scrape` | ❌ 403 (本番は 503) | ✅ (本番は 503) |
| GET | `/api/units/{module_id}` | ✅ | ✅ |
| GET | `/api/content/{unit_id}` | ✅ (初回生成OK) | ✅ |
| GET | `/api/content/{unit_id}?force=true` | ❌ 403 | ✅ |
| POST | `/api/quiz/{unit_id}` | ✅ (初回生成OK) | ✅ |
| GET/POST | `/api/progress/{user_id}` | ✅ | ✅ |

**スクレイピング対応URL形式**

| パターン | 例 | 動作 |
|---|---|---|
| `/credentials/certifications/<cert-slug>/` | `azure-network-engineer-associate/` | 認定資格ページ → 試験ID解決 → 配下を再帰取得 |
| `/credentials/certifications/exams/<id>/` | SC-100 試験ページ | 配下コース＋直接パスを再帰取得 |
| `/training/courses/<id>` | `az-500t00` | コース配下の全パスを取得 |
| `/training/paths/<slug>/` | `manage-identity-and-access` | 単体パスを取得 |

**CI/CD ワークフロー（本番デプロイ後に有効化）**

| ファイル | トリガー | 内容 |
|---|---|---|
| `.github/workflows/infra.yml` | `infra/**` 変更 / 手動 | Bicep デプロイ |
| `.github/workflows/backend.yml` | `backend/**` 変更 / 手動 | Functions zip + Oryx remote build |
| `.github/workflows/frontend.yml` | `frontend/**` 変更 / PR | SWA 静的サイトデプロイ。PR は自動でプレビュー環境作成 |

**必要な GitHub Secrets**（次回セッションで設定）

| Name | Value 取得元 |
|---|---|
| `AZURE_CLIENT_ID` | UAMI Client ID (Step 3) |
| `AZURE_TENANT_ID` | `az account show --query tenantId` |
| `AZURE_SUBSCRIPTION_ID` | `az account show --query id` |
| `AAD_CLIENT_SECRET` | Entra アプリのシークレット (Step 2) |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | SWA デプロイトークン (Step 5) |

**必要な GitHub Variables**（次回セッションで設定）

| Name | Value |
|---|---|
| `AZURE_RG` | `rg-microsoft-training` |
| `RESOURCE_PREFIX` | `mslearn` |
| `FUNCTION_APP_NAME` | `mslearn-func` |
| `EXISTING_COSMOS_ACCOUNT` | `cosmos-training-murokawa` |
| `EXISTING_COSMOS_DATABASE` | `cosmos-training-murokawa` |
| `AZURE_OPENAI_ENDPOINT` | `https://foundry-training-murokawa.services.ai.azure.com/api/projects/proj-default` |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` |
| `FOUNDRY_AGENT_URL_SUMMARY` | summary-agent URL |
| `FOUNDRY_AGENT_URL_QUIZ` | quiz-agent URL |
| `AAD_CLIENT_ID` | Entra アプリの Client ID (Step 2) |
