# Microsoft Learn 学習サポートアプリ

Microsoft Learn の資格試験ラーニングパス（AZ-500 / SC-300 / SC-100 など）をスクレイピングし、Azure AI Foundry（gpt-4o）で**自然な日本語要約**と**4択クイズ**を自動生成する学習サポートツール。

---

## 目次

1. [アプリ概要](#アプリ概要)
2. [技術スタック](#技術スタック)
3. [画面構成](#画面構成)
4. [セットアップ](#セットアップ)
5. [ローカル起動手順](#ローカル起動手順)
6. [APIエンドポイント](#apiエンドポイント)
7. [スクレイピング処理の仕組み](#スクレイピング処理の仕組み)
8. [データモデル（Cosmos DB）](#データモデルcosmos-db)
9. [技術的な決定事項・注意点](#技術的な決定事項注意点)
10. [プロジェクト構成](#プロジェクト構成)

---

## アプリ概要

Microsoft Learn の英語/機械翻訳日本語コンテンツは**専門用語の訳が不自然**で学習効率を下げがち。本アプリは以下を自動化します：

1. **Microsoft Learn URL を入力** → ページ構造をスクレイピング
2. **Azure AI Foundry が要約** → 「プロエンジニアが教える自然な日本語」に変換
3. **試験対策クイズを自動生成** → 4択・解説付き
4. **学習進捗を保存** → ユニット完了率・クイズ正答率をCosmos DB に記録

3階層のUI：

```
試験コレクション (AZ-500 / SC-300 / SC-100)
    └─ ラーニングパス
          └─ ユニット（要約 + クイズ）
```

---

## 技術スタック

| レイヤー | 技術 |
|---|---|
| Frontend | React 18 + Vite + TypeScript + react-router-dom + react-markdown |
| Backend | Azure Functions (Python v2 programming model) |
| Database | Azure Cosmos DB (NoSQL API, サーバーレス) |
| AI | Azure AI Foundry (`azure-ai-projects` SDK, gpt-4o) |
| Scraping | Playwright (Chromium headless) |
| 認証 | Managed Identity / `DefaultAzureCredential`（キーレス） |
| デプロイ先 | Azure Static Web Apps + Azure Functions |

---

## 画面構成

| ルート | ページ | 役割 |
|---|---|---|
| `/` | ExamListPage | 試験カード一覧（AZ-500, SC-300, SC-100） |
| `/exam/:examId` | ExamPage | 試験別ラーニングパス一覧 + URL入力フォーム |
| `/path/:pathId` | PathPage | ラーニングパス内モジュール/ユニット一覧 |
| `/unit/:unitId` | UnitPage | AI要約 (Markdown) + 4択クイズ |

---

## セットアップ

### 前提

- Node.js 18+ / npm
- Python 3.11+（3.14 でも動作確認済み）
- Azure Functions Core Tools v4
- Azure CLI (`az login` 済み)
- Azurite（ローカルストレージエミュレータ）

### 初回セットアップ

```bash
# フロントエンド依存関係
cd frontend && npm install

# バックエンド依存関係（仮想環境推奨）
cd ../backend
python -m venv .venv
source .venv/Scripts/activate  # Windows (Git Bash)
pip install -r requirements.txt
playwright install chromium
```

### `backend/local.settings.json`（例）

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "COSMOS_DB_ENDPOINT": "https://<your-account>.documents.azure.com:443/",
    "COSMOS_DB_DATABASE": "<your-db>",
    "AZURE_OPENAI_ENDPOINT": "https://<foundry>.services.ai.azure.com/api/projects/<proj>",
    "AZURE_OPENAI_DEPLOYMENT": "gpt-4o"
  }
}
```

### Azure リソースの準備

```bash
# Cosmos DB（サーバーレス）
az cosmosdb create -n <name> -g <rg> --capabilities EnableServerless
az cosmosdb sql database create -a <name> -g <rg> -n <db-name>

# 4つのコンテナを作成（--throughput オプション不可）
for c in learning_paths units quizzes user_progress; do
  az cosmosdb sql container create -a <name> -g <rg> -d <db-name> -n $c --partition-key-path "/id"
done

# ローカル開発ユーザーに RBAC ロール付与
MSYS_NO_PATHCONV=1 az cosmosdb sql role assignment create \
  --account-name <name> -g <rg> \
  --scope "/" \
  --principal-id <your-object-id> \
  --role-definition-id 00000000-0000-0000-0000-000000000002
```

> **Git Bash の注意**：`--scope "/"` は Git Bash が Windows パスに変換してしまうため `MSYS_NO_PATHCONV=1` が必須。

---

## ローカル起動手順

3つのターミナルで：

```bash
# 1. ストレージエミュレータ
npx azurite

# 2. バックエンド
cd backend && func start
# → http://localhost:7071

# 3. フロントエンド
cd frontend && npm run dev
# → http://localhost:5173
```

ブラウザで `http://localhost:5173` を開く。

---

## APIエンドポイント

| メソッド | パス | 概要 |
|---|---|---|
| GET | `/api/exams` | 試験コレクション一覧（learning_paths から集計） |
| GET | `/api/learning-paths?exam_id=az-500` | 試験別ラーニングパス一覧 |
| PATCH | `/api/learning-paths/{path_id}` | 試験タグ（exam_id/exam_name）を後付け設定 |
| POST | `/api/scrape` | URL を受けてスクレイピング開始（コース/パス両対応） |
| GET | `/api/units/{module_id}` | モジュール内ユニット一覧 |
| GET | `/api/content/{unit_id}` | 要約取得（なければその場で生成） |
| POST | `/api/quiz/{unit_id}` | 4択クイズ生成（キャッシュあり再利用） |
| GET | `/api/progress/{user_id}` | 学習進捗取得 |
| POST | `/api/progress/{user_id}` | 学習進捗保存（ユニット完了・クイズ結果） |

### `POST /api/scrape` のリクエスト例

```json
{
  "url": "https://learn.microsoft.com/ja-jp/training/courses/az-500t00",
  "exam_id": "az-500",
  "exam_name": "AZ-500"
}
```

レスポンス：

```json
{
  "status": "ok",
  "paths": [
    {"learning_path_id": "secure-identity-access", "title": "ID とアクセス..."},
    {"learning_path_id": "secure-networking", "title": "ネットワーク..."}
  ]
}
```

---

## スクレイピング処理の仕組み

### 全体像

Microsoft Learn は SPA（Single Page Application）で、ページ遷移後に JavaScript で DOM が動的に生成される。`requests` + `BeautifulSoup` のような静的HTTP取得ではほぼ空のHTMLしか取れないため、**Playwright（Chromium headless）** を採用している。

### 処理のレイヤー構造

```
POST /api/scrape (Azure Functions)
        │
        ▼
scrape_from_url(url)   ← URL種別を判定してディスパッチ
        │
        ├─ コースURL ?  →  _extract_path_urls_from_course()  → 複数パスURL
        │                           │
        └─ パスURL       ←─────────┘
                │
                ▼
        _scrape_path_structure(page, url)   ← ラーニングパス目次
                │
                ▼
        _scrape_module_units(page, url, ...)   ← モジュール内ユニット一覧
                │
                ▼
        _scrape_unit_content(page, url)   ← 本文抽出 + クリーニング
                │
                ▼
        Cosmos DB に保存
```

### 1. URL ディスパッチ

```python
if "/training/courses/" in source_url:
    path_urls = await _extract_path_urls_from_course(page, source_url)
elif "/training/paths/" in source_url:
    path_urls = [source_url]
else:
    raise ValueError(...)
```

コースURL なら「このコースに含まれるラーニングパス一覧」を抽出してから通常のパススクレイピングを繰り返す。AZ-500 でも SC-300 でも同じ手順で動く**汎用構造**。

### 2. `page.evaluate()` を多用している理由

Playwright には2通りのDOM操作方法がある：

**A. ElementHandle 経由（避けるべき）**

```python
els = await page.query_selector_all('a')
for el in els:
    href = await el.get_attribute('href')  # ← ページ遷移後に無効化される
```

**B. `page.evaluate()` で JS 実行して値だけ取る（推奨）**

```python
hrefs = await page.evaluate("""() => {
    return Array.from(document.querySelectorAll('a')).map(a => a.href);
}""")
```

前者は**ページ遷移するとハンドルが破壊される**ため、「リンク一覧を取得 → 各リンクに遷移 → 次のリンクを参照」のパターンで必ず壊れる。本スクレイパーは目次ページで取った情報を持って次々遷移する構造なので、値を Python 側に即時コピーできる `evaluate()` 一択。

### 3. セレクタの複数フォールバック戦略

Microsoft Learn の DOM 構造は時期によって微妙に変わるため、1つのセレクタに依存すると壊れる。

```js
const selectors = [
    'a[href*="/training/modules/"]',
    '.module-card a',
    '[data-bi-name="module-card"] a',
];
for (const sel of selectors) {
    const els = ...
    if (els.length > 0) return els;  // 最初にマッチしたものを採用
}
```

**URL パターンベース** (`a[href*="/training/modules/"]`) を第一優先にしているのは、CSS クラスよりリンクURL のほうが Microsoft 側でも変えにくいため。

### 4. ユニットURL の絞り込みロジック

モジュールページには「同モジュール内ユニット」「他モジュールへのリンク」「マーケ系リンク」が混在する。**モジュールスラッグを使って正規表現でフィルタ**する：

```python
# モジュールURL: /training/modules/<module-slug>/
# ユニットURL : /training/modules/<module-slug>/<unit-slug>/
m = re.search(r"/training/modules/([^/?#]+)", module_url)
module_slug = m.group(1)

# スラッグ部分が英数字+ハイフンのみ = 正規ユニット
if not re.match(r"^[a-z0-9][a-z0-9\-]*$", slug_part):
    continue
```

### 5. 本文抽出：ノイズ除去 → コンテンツセレクタ探索

**Step 1: ノイズ除去**

```python
_REMOVE_SELECTORS = [
    "header", "footer", "nav", ".feedback-section",
    ".rating-section", "script", "style", ...
]
# page.evaluate() で一括 remove()
```

**Step 2: 本文コンテナを優先順位で探索**

```python
_CONTENT_SELECTORS = [
    "div.content", "main#main", "article", "div[role='main']"
]
for selector in _CONTENT_SELECTORS:
    text = ... .innerText
    if len(text) > 100:   # 100文字未満ならセレクタが外れている
        return text
# 全滅なら body.innerText にフォールバック
```

**`innerText` を使う理由**：`textContent` だと非表示要素のテキストも取れてしまうのに対し、`innerText` は**ブラウザで見える通り**のテキスト（改行・スペース込み）を返すため、後の要約品質が良くなる。

### 6. テキストのクリーニング

```python
def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)   # 3連改行 → 2連に圧縮
    # 連続する空行を1行に畳む
```

AI に食わせる前に**無駄な改行を削る**ことで、OpenAI のトークン消費を約20〜30%削減できる（Foundry はトークン従量課金）。

### 7. レート制限対策

```python
for unit in module["units"]:
    unit["raw_content"] = await _scrape_unit_content(page, unit["url"])
    await page.wait_for_timeout(800)   # 800ms ウェイト
```

`learn.microsoft.com` は公開ドキュメントだが、同一IPから秒間大量リクエストは WAF に弾かれる可能性がある。800ms は人間の閲覧速度を模倣する値。1パス（30〜40ユニット）で約30〜40秒の遅延になる。

### 8. Cosmos DB への保存戦略

```python
for module in path_data.get("modules", []):
    for unit in module.get("units", []):
        units_container.upsert_item(unit)      # units コンテナへ
    module.pop("units", None)                  # 親から除去
container.upsert_item(path_data)                # learning_paths へ
```

**ユニットを親ドキュメントから分離**する理由：

1. **Cosmos DB の1ドキュメント上限 2MB** — ユニット数 × 本文量で簡単に超える
2. **コンテンツ要約はユニット単位**で更新される — 親を毎回書き換えるのは無駄
3. **クエリの柔軟性** — 「要約済のユニットだけ取得」のような絞り込みが効く

パーティションキーは `/id` なので**ユニットごとに分散**し、スケール時もホットスポットになりにくい。

### ハマりポイント一覧

| 症状 | 原因 | 対処 |
|---|---|---|
| `Element handle is disposed` | ページ遷移でハンドル破壊 | `page.evaluate()` に移行 |
| セレクタが何もマッチしない | DOM構造のバリエーション | 複数セレクタのフォールバック |
| ユニットリンクに変なURLが混じる | ナビゲーション全リンク抽出 | モジュールスラッグで正規化 |
| 本文が100文字程度で切れる | `textContent` 使用時のバグ | `innerText` + 連鎖フォールバック |
| f-string 内で JS のクォート衝突 | `[data-bi-name='x']` が死ぬ | `evaluate(js, args)` 引数で渡す |

---

## データモデル（Cosmos DB）

### コンテナ一覧

| コンテナ | パーティションキー | 主な用途 |
|---|---|---|
| `learning_paths` | `/id` | ラーニングパスメタデータ（モジュール一覧含む、units は別コンテナ） |
| `units` | `/id` | ユニットメタデータ + 本文 + AI要約 |
| `quizzes` | `/id` | AI生成クイズ（unit_id でフィルタ可能） |
| `user_progress` | `/user_id` | ユーザーごとの進捗（完了ユニット・クイズ結果） |

### ドキュメント例

**learning_paths**

```json
{
  "id": "secure-identity-access",
  "title": "Microsoft Entra ID で ID とアクセスを管理する",
  "url": "https://learn.microsoft.com/ja-jp/training/paths/secure-identity-access/",
  "exam_id": "az-500",
  "exam_name": "AZ-500",
  "modules": [
    {"id": "...-mod-001", "title": "...", "unit_count": 8, "order": 1}
  ],
  "created_at": "2026-04-19T...",
  "updated_at": "2026-04-19T..."
}
```

**units**

```json
{
  "id": "secure-identity-access-mod-001-unit-001",
  "module_id": "secure-identity-access-mod-001",
  "learning_path_id": "secure-identity-access",
  "title": "はじめに",
  "url": "https://learn.microsoft.com/.../",
  "order": 1,
  "raw_content": "<スクレイピングしたテキスト>",
  "summary_ja": "<AI要約、Markdown形式>",
  "summary_generated_at": "2026-04-20T..."
}
```

**quizzes**

```json
{
  "id": "quiz-<unit_id>-<uuid>",
  "unit_id": "...",
  "question": "条件付きアクセス (Conditional Access) について正しいものは？",
  "choices": [
    {"key": "A", "text": "..."}, {"key": "B", "text": "..."},
    {"key": "C", "text": "..."}, {"key": "D", "text": "..."}
  ],
  "correct_key": "B",
  "explanation": "..."
}
```

---

## 技術的な決定事項・注意点

### Azure AI Foundry 接続

- `services.ai.azure.com/api/projects/<proj>` 形式のエンドポイントは **`azure-ai-projects` SDK 必須**
- `openai.AzureOpenAI` SDK では audience / APIバージョンが合わず接続不可
- `AIProjectClient.get_openai_client()` が正しい `/openai/v1/` パスを解決してくれる

### Cosmos DB

- **サーバーレスアカウントは `--throughput` 不可** — コンテナ作成時は省略
- **`order` は予約語** — `SELECT c.order` は構文エラー、`SELECT c["order"]` と書く
- **RBAC のスコープ** — `MSYS_NO_PATHCONV=1` が Git Bash では必須

### 認証

- **キーレス** — `DefaultAzureCredential` のみ使用
- ローカル：`az login` の認証情報でフォールバック
- 本番：Functions の SystemAssigned Managed Identity を使用

### Python 3.14 互換性

以下のパッケージは**プレビルドホイールがある版**を使用（C++コンパイラ不要）：

```
playwright>=1.49.0
aiohttp>=3.11.0
pydantic>=2.10.0
greenlet>=3.4.0
```

---

## プロジェクト構成

```
microsoft-training/
├── backend/                          # Azure Functions (Python v2)
│   ├── function_app.py               # 全エンドポイント（@app.route デコレータ）
│   ├── scraping/
│   │   └── ms_learn_scraper.py       # Playwright スクレイパー
│   ├── shared/
│   │   ├── cosmos_client.py          # Cosmos DB クライアント
│   │   └── openai_client.py          # Foundry クライアント
│   ├── local.settings.json           # ローカル環境変数（git管理外）
│   └── requirements.txt
├── frontend/                         # React + Vite + TypeScript
│   └── src/
│       ├── pages/
│       │   ├── ExamListPage.tsx      # / : 試験カード一覧
│       │   ├── ExamPage.tsx          # /exam/:examId : ラーニングパス一覧
│       │   ├── PathPage.tsx          # /path/:pathId : ユニット一覧
│       │   └── UnitPage.tsx          # /unit/:unitId : 要約 + クイズ
│       ├── api/client.ts             # 型付きAPIクライアント
│       └── App.tsx                   # ルーティング定義
├── infra/
│   └── main.bicep                    # Cosmos DB / Functions / Static Web Apps
├── docs/                             # 設計ドキュメント・スクリーンショット
├── progress-summary.md               # セッション進捗記録
├── CLAUDE.md                         # プロジェクト指示書
└── README.md                         # このファイル
```

---

## ライセンス

個人学習用プロジェクト。スクレイピングした Microsoft Learn コンテンツの著作権は Microsoft に帰属します。
