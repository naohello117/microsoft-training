# 進捗サマリー

## 最終更新：2026-04-22

---

## ✅ 完了した作業

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

- **Foundry Agents（Responses API）採用**：プロンプト変更のたびに再デプロイ不要。Foundry Portal で Instructions / Model / Temperature を編集 → 即反映。`quiz-agent` は JSON Schema（strict）で出力構造を保証する（json_object より厳密）。

- **Responses API の応答パース**：`output_text` と `output[].content[].text`（`text` が文字列 or `{value}` オブジェクト）の両パターンを `_extract_text()` で吸収すること。

- **`func start` は必ず `.venv` 有効化後に**：`source .venv/Scripts/activate` を忘れると system Python 3.14 が使われ `aiohttp` 等が import 失敗する。

- **innerText は `<a href>` の URL を捨てる**：スクレイパーで AI に渡す前に DOM を `[text](href)` に書き換えるパターン必須。URL 情報を保持しないと AI が URL をハルシネーションする。

- **summary-agent の Instructions はコードではなく Foundry Portal で管理**：`docs/foundry-agents.md` はソースオブトゥルースの仕様書として扱い、変更時はユーザーが Portal に反映する運用。

- **認定試験URL（`/credentials/certifications/exams/...`）対応**：ページ内に training paths / courses 両方のリンクが混在。両方を抽出し、コース経由で解決したパスも合流させる。

- **Foundry エンドポイント形式**：`services.ai.azure.com/api/projects/<proj>` 形式は `azure-ai-projects` SDK 必須。`openai` SDK の `AzureOpenAI` では接続不可（audience・APIバージョン不一致）。

- **Cosmos DB サーバーレスアカウント**：`--throughput` オプション不可。コンテナ作成時は省略すること。

- **Git Bash のパス変換**：`az cosmosdb sql role assignment create --scope "/<path>"` で `/` がWindowsパスに変換されるバグ。コマンド先頭に `MSYS_NO_PATHCONV=1` をつけること。

- **Managed Identity 認証**：キーを使わず `DefaultAzureCredential` のみ。ローカルでは Azure CLI ログイン（`az login`）でフォールバック。本番は Functions の SystemAssigned ID を使用。マネージド ID には `Azure AI Administrator` ロール付与済み。

- **`order` は Cosmos DB の予約語**：`SELECT c.order` は構文エラー → `SELECT c["order"]` と書くこと。

- **試験コレクションの概念**：`learning_paths` ドキュメントに `exam_id` / `exam_name` フィールドを追加。`GET /api/exams` で集計取得。既存パスは `PATCH /api/learning-paths/{id}` で後付け可能。

- **フロントエンドの `USER_ID`**：`UnitPage.tsx` 内で `"demo-user"` にハードコード。本番化時は Static Web Apps の AAD 認証ヘッダー（`x-ms-client-principal`）から取得するよう変更が必要。

---

## 📋 残課題・ネクストアクション

### 優先度：高（次回セッションで必ず着手）

- [ ] **Foundry Portal の summary-agent Instructions を更新**
  - `docs/foundry-agents.md` の「# リンクの扱い」セクションを Portal に貼り付け
  - これをやらないと AI がリンクを創作する可能性が残る

- [ ] **SC-100 / SC-300 のラーニングパスをスクレイピング**
  - `https://learn.microsoft.com/ja-jp/credentials/certifications/exams/sc-100/`
  - `https://learn.microsoft.com/ja-jp/credentials/certifications/exams/sc-300/`
  - ExamPage の URL 追加フォームから投入（認定試験URL対応実装済み）

- [ ] **新しいスクレイパー（リンク保持版）の動作確認**
  - 未キャッシュのユニットで要約→リンクが Markdown で表示され・別タブで開き・ja-jp URL になることを目視確認

### 優先度：中

- [ ] **要約プロンプトのチューニング確認**
  - 実コンテンツで要約を生成し、品質を目視確認
  - 「★試験ポイント」の抽出精度を評価

- [ ] **フロントエンド機能拡充**
  - 進捗ダッシュボード（完了率・スコアのグラフ表示）
  - エラートースト実装
  - `PathPage` で全モジュールの要約生成済みユニット数を表示

- [ ] **Azure へのデプロイ**
  - Functions: `func azure functionapp publish <app-name>`
  - Static Web Apps: GitHub Actions ワークフロー設定

### 優先度：低

- [ ] **Bicep テンプレートの完成**
  - Foundry / Azure OpenAI リソース定義を追加
  - `az deployment group create` でワンコマンドプロビジョニングを確認

- [ ] **認証統合**
  - `UnitPage.tsx` の `USER_ID` を AAD トークン（`x-ms-client-principal` ヘッダー）から取得
  - Static Web Apps の `/.auth/me` エンドポイントを利用

- [ ] **未使用コードの整理**
  - `shared/openai_client.py` は Foundry Agents 移行で未使用（削除可能か確認）
  - 旧 `Dashboard.tsx` の TypeScript エラーが残っている場合は対処

---

## 🗂 プロジェクト構成・環境メモ

```
microsoft-training/
├── backend/                        # Azure Functions (Python v2)
│   ├── function_app.py             # 全エンドポイント（@app.route デコレータ）
│   ├── scraping/ms_learn_scraper.py  # Playwright + リンク保持版
│   ├── shared/cosmos_client.py
│   ├── shared/foundry_agent.py     # ★NEW: Responses API 呼び出し
│   ├── shared/openai_client.py     # （未使用、削除候補）
│   ├── local.settings.json         # ローカル環境変数（git管理外推奨）
│   └── requirements.txt
├── frontend/                       # React + Vite + TypeScript
│   └── src/
│       ├── pages/ExamListPage.tsx  # / : 試験カード一覧
│       ├── pages/ExamPage.tsx      # /exam/:examId : ラーニングパス一覧
│       ├── pages/PathPage.tsx      # /path/:pathId : ユニット一覧
│       ├── pages/UnitPage.tsx      # /unit/:unitId : 要約 + クイズ (進捗UI / リンクja-jp化)
│       ├── api/client.ts           # 型付きAPIクライアント
│       └── App.tsx                 # ルーティング定義
├── docs/foundry-agents.md          # ★NEW: Foundry Agents 仕様書（Portal設定のソース）
├── infra/main.bicep
├── progress-summary.md
└── .claude/skills/save-progress/
```

**接続先リソース（rg-microsoft-training）**

| リソース | 名前 |
|---|---|
| Cosmos DB アカウント | `cosmos-training-murokawa` |
| Cosmos DB データベース | `cosmos-training-murokawa` |
| Azure AI Foundry | `foundry-training-murokawa` |
| Foundry プロジェクトエンドポイント | `https://foundry-training-murokawa.services.ai.azure.com/api/projects/proj-default` |
| OpenAI デプロイ名 | `gpt-4o` |
| summary-agent URL | `.../applications/summary-agent/protocols/openai/responses?api-version=2025-11-15-preview` |
| quiz-agent URL | `.../applications/quiz-agent/protocols/openai/responses?api-version=2025-11-15-preview` |

**環境変数（`backend/local.settings.json`）**

| キー | 用途 |
|---|---|
| `COSMOS_DB_ENDPOINT` | Cosmos DB のエンドポイント |
| `COSMOS_DB_DATABASE` | Cosmos DB のデータベース名 |
| `FOUNDRY_AGENT_URL_SUMMARY` | summary-agent の Responses API URL |
| `FOUNDRY_AGENT_URL_QUIZ` | quiz-agent の Responses API URL |
| `AZURE_OPENAI_ENDPOINT` | （旧 Chat Completions 経由・現在は未使用） |
| `AZURE_OPENAI_DEPLOYMENT` | （旧 Chat Completions 経由・現在は未使用） |

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

**APIエンドポイント一覧（ローカル）**

| メソッド | パス | 概要 |
|---|---|---|
| GET | `/api/exams` | 試験コレクション一覧 |
| GET | `/api/learning-paths?exam_id=az-500` | 試験別ラーニングパス一覧 |
| PATCH | `/api/learning-paths/{path_id}` | 試験タグ付け |
| POST | `/api/scrape` | スクレイピング（認定試験/コース/パスURL対応） |
| GET | `/api/units/{module_id}` | モジュール内ユニット一覧 |
| GET | `/api/content/{unit_id}` | 要約取得（なければ summary-agent で生成） |
| POST | `/api/quiz/{unit_id}` | クイズ生成（quiz-agent / キャッシュあり） |
| GET | `/api/progress/{user_id}` | 進捗取得 |
| POST | `/api/progress/{user_id}` | 進捗保存 |

**スクレイピング対応URL形式**

| パターン | 例 | 動作 |
|---|---|---|
| `/credentials/certifications/exams/<id>/` | SC-100 試験ページ | 配下コース＋直接パスを再帰的に取得 |
| `/training/courses/<id>` | `az-500t00` | コース配下の全パスを取得 |
| `/training/paths/<slug>/` | `manage-identity-and-access` | 単体パスを取得 |
