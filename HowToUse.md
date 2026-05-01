# 利用ガイド (HowToUse)

学習者と管理者の操作手順をまとめたドキュメント。

---

## 学習者として使う

1. ブラウザで本番 SWA URL を開く: `https://victorious-field-05c451000.7.azurestaticapps.net/`
2. 「サインイン」→ 招待された Entra ID アカウントでログイン
3. 試験コレクション一覧が表示される → 興味のある試験をクリック
4. 配下のラーニングパス → モジュール → ユニット を辿る
5. 各ユニットを開くと **AI 要約** が自動生成される（初回は数十秒）
6. 「クイズを生成」ボタンで 4 択問題が出題される

---

## 管理者：コンテンツを追加する

> ⚠️ **本番環境ではサーバー側スクレイピングは無効です** (`DISABLE_SCRAPE=true`)。
> Playwright が Linux Consumption で動作しないため、コンテンツ追加は **管理者がローカル PC** で実行し、本番 Cosmos に直接書き込む方式を取っています。

### 1. 準備（初回のみ）

#### 1-1. ローカル環境のセットアップ

```bash
# このリポジトリを clone 済みの前提
cd backend
python -m venv .venv
source .venv/Scripts/activate    # Windows Git Bash の場合
pip install -r requirements-dev.txt
playwright install chromium
```

#### 1-2. Azure CLI ログイン（本番テナント）

```bash
az login
az account set --subscription b3dc3a21-7bc2-4846-9a83-251d149649b0
```

#### 1-3. 自分の Azure アカウントに Cosmos 権限を付与（一度だけ）

本番 Cosmos は `disableLocalAuth: true` のため、Entra ID 認証で操作します。
管理者アカウントに **Cosmos DB Built-in Data Contributor** ロールを付与:

```bash
MY_OID=$(az ad signed-in-user show --query id -o tsv)

az cosmosdb sql role assignment create \
  --account-name cosmos-training-murokawa \
  --resource-group rg-microsoft-training \
  --scope "/" \
  --principal-id "$MY_OID" \
  --role-definition-id 00000000-0000-0000-0000-000000000002
```

#### 1-4. フロントエンドの管理者バイパス設定

`frontend/.env.local` を作成（または編集）し、以下を設定:

```
VITE_LOCAL_ADMIN_BYPASS=true
```

> Vite 開発サーバーには SWA 認証 (`/.auth/me`) が存在しないため、これを `true` にしないとローカル UI で管理者操作（URL 入力フォーム）が表示されません。
> 設定変更後は **`npm run dev` を再起動** すること（Vite は起動時に環境変数を読むため）。
> このファイルは `.gitignore` 済みでコミットされません。本番側には影響しません。

#### 1-5. バックエンドのローカル設定確認

`backend/local.settings.json` が以下の値になっているか確認（本番 Cosmos に向ける）:

```json
{
  "Values": {
    "COSMOS_DB_ENDPOINT": "https://cosmos-training-murokawa.documents.azure.com:443/",
    "COSMOS_DB_DATABASE": "cosmos-training-murokawa",
    "AZURE_OPENAI_ENDPOINT": "https://foundry-training-murokawa.cognitiveservices.azure.com/",
    "AZURE_OPENAI_DEPLOYMENT": "gpt-5.4",
    "FOUNDRY_AGENT_URL_SUMMARY": "https://foundry-training-murokawa.services.ai.azure.com/api/projects/proj-default/applications/summary-agent/protocols/openai/responses?api-version=2025-11-15-preview",
    "FOUNDRY_AGENT_URL_QUIZ": "https://foundry-training-murokawa.services.ai.azure.com/api/projects/proj-default/applications/quiz-agent/protocols/openai/responses?api-version=2025-11-15-preview",
    "LOCAL_ADMIN_BYPASS": "true"
  }
}
```

> `DISABLE_SCRAPE` は **設定しない**（または `false`）。これがあるとローカルでも動かない。
> `LOCAL_ADMIN_BYPASS=true` でローカル開発時は Entra ID 認証チェックをスキップ。

---

### 2. 毎回の作業手順（コンテンツ追加）

#### 2-1. ローカル backend を起動

```bash
cd backend
func start --port 7071
```

`Found Python version 3.11` などのログの後、`http://localhost:7071/api/exams` などの URL が表示されれば OK。

#### 2-2. 別ターミナルでフロントエンドを起動

```bash
cd frontend
npm install   # 初回のみ
npm run dev
```

`Local: http://localhost:5173/` が表示される。

#### 2-3. ブラウザでローカル UI を開く

`http://localhost:5173/` を開く。`LOCAL_ADMIN_BYPASS=true` のため自動で管理者扱いになり、URL 入力フォームが見える。

#### 2-4. URL を入力して「試験を追加」

対応する Microsoft Learn URL（以下のいずれか）:
- 認定資格ページ: `https://learn.microsoft.com/ja-jp/credentials/certifications/azure-security-engineer/`
- 認定試験ページ: `https://learn.microsoft.com/ja-jp/credentials/certifications/exams/az-500/`
- 単一ラーニングパス: `https://learn.microsoft.com/ja-jp/training/paths/manage-identity-access/`
- コース: `https://learn.microsoft.com/ja-jp/training/courses/az-500t00`

スクレイピング所要時間: 1 ラーニングパスあたり 30 秒〜2 分。複数まとめて取得する場合 5〜15 分かかることもあります。

完了するとメッセージに `〜 に N 件のラーニングパスを追加しました` と表示。書き込み先は **本番 Cosmos** です。

#### 2-5. 本番 SWA で確認

`https://victorious-field-05c451000.7.azurestaticapps.net/` を開くと、追加した試験コレクションが表示されます。
ユニットを開けば Foundry エージェントが要約を自動生成します。

---

### 3. トラブルシューティング

| 症状 | 対処 |
|---|---|
| `func start` で「Python ランタイムが見つからない」 | Azure Functions Core Tools v4 をインストール (`npm i -g azure-functions-core-tools@4`) |
| `playwright._impl._api_types.Error: ...` | `playwright install chromium` を再実行 |
| ローカル UI で URL 入力フォームが表示されない | `frontend/.env.local` の `VITE_LOCAL_ADMIN_BYPASS=true` を確認後、`npm run dev` を再起動 |
| ローカル UI でフォーム送信時に 401/403 | `local.settings.json` に `"LOCAL_ADMIN_BYPASS": "true"` があるか確認 |
| Cosmos 書き込みで 403 / `Forbidden` | 1-3 のロール割り当てが完了していない。`az cosmosdb sql role assignment list --account-name cosmos-training-murokawa --resource-group rg-microsoft-training` で確認 |
| 本番 SWA で要約が出ない | Application Insights で例外確認: <br>`az monitor app-insights query --app bd87bf45-3b52-4d29-b025-27b2b389fe5e --analytics-query "exceptions \| order by timestamp desc \| take 10"` |
| ブラウザで「Invitation invalid」 | 招待先メールが Entra テナントの所属ユーザーになっているか確認（iCloud などの個人アドレスは不可） |

---

### 4. 終了時の片付け

開発を終えたら、`backend/local.settings.json` の `COSMOS_DB_ENDPOINT` を **ローカル開発用** に戻すと安全です（誤って本番を書き換えないため）。
