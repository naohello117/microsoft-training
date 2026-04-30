# デプロイ・CI/CD ガイド

Microsoft Learn 学習サポートを Azure に本番デプロイし、GitHub Actions による継続的デプロイを構成する手順。
**Azure Portal (GUI) 中心**で記載しています。CLI が大幅に楽な箇所のみ補助的にコマンドを併記します。

## アーキテクチャ

```
       ┌──────────────────────────┐
       │ User (Browser)            │
       └────────────┬──────────────┘
                    │ HTTPS
                    ▼
       ┌──────────────────────────────────────────┐
       │ Azure Static Web Apps (Standard)          │
       │  ├─ React SPA (frontend/dist)             │
       │  ├─ Entra ID 認証 (admin ロール判定)      │
       │  └─ /api/* → linkedBackend                │
       └────────────┬─────────────────────────────┘
                    │ x-ms-client-principal ヘッダー注入
                    ▼
       ┌──────────────────────────────────────────┐
       │ Azure Functions (Python 3.11 / Linux Y1)  │
       │  ├─ システム割り当てマネージドID          │
       │  └─ DISABLE_SCRAPE=true (本番)            │
       └─────┬───────────────┬──────────┬────────┘
             │ MI            │          │ HTTPS
             ▼               ▼          ▼
       ┌──────────┐   ┌─────────┐   ┌─────────────┐
       │ Cosmos DB│   │  AOAI   │   │ Foundry     │
       │ (Server- │   │ gpt-4o  │   │ summary/    │
       │  less)   │   │         │   │ quiz-agent  │
       └──────────┘   └─────────┘   └─────────────┘
```

スクレイピングは管理者がローカルで `func start` 実行 → 本番 Cosmos に直接書き込み。

---

## 前提条件 (既存利用)

- **Azure サブスクリプション** (Contributor 以上)
- **リソースグループ** `rg-microsoft-training` (既存 / japaneast)
- **Cosmos DB アカウント** `cosmos-training-murokawa` (既存 / 同 RG / `disableLocalAuth: true` / コンテナ作成済み: `learning_paths`, `units`, `quizzes`, `user_progress`)
- **Foundry プロジェクト** `foundry-training-murokawa` + summary-agent / quiz-agent (既存)
- **GitHub リポジトリ** `naohello117/microsoft-training`
- **Web ブラウザ** (Microsoft Edge / Chrome)

> Bicep は既存の Cosmos / Foundry を **`existing` 参照**で再利用します（破壊しません）。
> 新規作成されるのは **Functions / SWA / Storage / Application Insights / App Service Plan** のみ。

---

## 初回セットアップ (手動・1回のみ)

### 1. 控えておく値の確認

Portal のグローバル検索 (上部の虫眼鏡) で以下を確認しておきます。

1. **テナント ID**: Portal 右上のアカウント → 「ディレクトリ + サブスクリプション」 → 「Default Directory」のディレクトリ ID
   - もしくは「Microsoft Entra ID」 → 「概要」 → 「テナント ID」
2. **サブスクリプション ID**: 「サブスクリプション」 → 該当サブスクリプションを開く → 「サブスクリプション ID」

メモ:
- `TENANT_ID = ________________`
- `SUB_ID = ________________`

---

### 2. Entra ID アプリ登録 (SWA 認証用)

#### 2-1. アプリ登録

1. Portal 検索で **「Microsoft Entra ID」** を開く
2. 左メニュー → **「アプリの登録」** → 上部 **「+ 新規登録」**
3. 入力:
   - **名前**: `MS Learning SWA`
   - **サポートされているアカウントの種類**: 「この組織ディレクトリのみに含まれるアカウント (シングルテナント)」
   - **リダイレクト URI**: 一旦空のまま (SWA のホスト名が後で確定するため、Step 4 で更新)
4. **「登録」** をクリック
5. 登録後の概要ページで以下を控える:
   - **アプリケーション (クライアント) ID** → `AAD_CLIENT_ID`
   - **ディレクトリ (テナント) ID** → 上記 1 の `TENANT_ID` と同じはず

#### 2-2. クライアントシークレット作成

1. 左メニュー → **「証明書とシークレット」** → **「+ 新しいクライアント シークレット」**
2. **説明**: `swa-auth` / **有効期限**: `24 か月` (任意)
3. **「追加」** → 表示された **値 (Value)** をすぐコピー → `AAD_CLIENT_SECRET`
   - ⚠️ ページを離れると二度と表示されない

#### 2-3. ID トークン発行を有効化

1. 左メニュー → **「認証」** → **「+ プラットフォームを追加」** → 「Web」
2. **リダイレクト URI**: 仮に `https://localhost/.auth/login/aad/callback` (Step 4 で正規 URL に更新)
3. **「暗黙的な許可およびハイブリッド フロー」** で **「ID トークン (暗黙的およびハイブリッド フローに使用)」** にチェック
4. **「保存」**

#### 2-4. `staticwebapp.config.json` のテナント ID 置換

ローカルの `frontend/staticwebapp.config.json` にある `<tenant-id>` プレースホルダを上記の **テナント ID** に置換し、コミットしておきます。

---

### 3. ユーザー割り当てマネージド ID + GitHub OIDC

#### 3-1. UAMI の作成

1. Portal 検索で **「マネージド ID」** を開く
2. **「+ 作成」** をクリック
3. 入力:
   - **サブスクリプション**: 該当のもの
   - **リソース グループ**: `rg-microsoft-training`
   - **リージョン**: `Japan East`
   - **名前**: `ms-learning-deploy`
4. **「確認および作成」** → **「作成」**
5. 作成後、概要ページで以下を控える:
   - **クライアント ID** → `AZURE_CLIENT_ID`
   - **オブジェクト (プリンシパル) ID** → 後で使用

#### 3-2. RG への Contributor 付与

1. リソースグループ **`rg-microsoft-training`** を開く
2. 左メニュー → **「アクセス制御 (IAM)」** → **「+ 追加」** → **「ロール割り当ての追加」**
3. **「ロール」** タブ:
   - 検索 → **「共同作成者 (Contributor)」** を選択 → **「次へ」**
4. **「メンバー」** タブ:
   - **アクセスの割り当て先**: 「マネージド ID」
   - **「+ メンバーを選択」** → **マネージド ID 種類**: `ユーザー割り当てマネージド ID` → `ms-learning-deploy` を選択
5. **「レビューと割り当て」** → **「割り当て」**

#### 3-3. Cosmos DB Operator 付与 (Bicep が sqlRoleAssignment を作成するため)

1. Cosmos DB アカウント **`cosmos-training-murokawa`** を開く
2. 左メニュー → **「アクセス制御 (IAM)」** → **「+ 追加」** → **「ロール割り当ての追加」**
3. **「ロール」** タブ:
   - 検索 → **「Cosmos DB Operator」** を選択 → **「次へ」**
4. **「メンバー」** タブ:
   - 「マネージド ID」 → `ms-learning-deploy` を選択
5. **「レビューと割り当て」** → **「割り当て」**

#### 3-4. GitHub Actions OIDC 連携 (フェデレーション資格情報)

1. マネージド ID **`ms-learning-deploy`** に戻る
2. 左メニュー → **「フェデレーション資格情報」** → **「+ 資格情報の追加」**
3. **main ブランチ用** (1 件目):
   - **フェデレーション資格情報のシナリオ**: 「GitHub Actions による Azure リソースのデプロイ」
   - **組織**: `naohello117`
   - **リポジトリ**: `microsoft-training`
   - **エンティティの種類**: `ブランチ`
   - **GitHub ブランチ名**: `main`
   - **名前**: `github-main`
   - 「追加」
4. **PR 用** (2 件目): 再度 「+ 資格情報の追加」
   - **エンティティの種類**: `プル要求`
   - **名前**: `github-pr`
   - 「追加」

---

### 4. 初回 Bicep デプロイ (Portal カスタムデプロイ)

CI/CD を回す前に Azure リソースを作成します。
既存 Cosmos / Foundry は破壊されず、Functions / SWA / Storage / App Insights のみ新規作成されます。

#### 4-1. カスタム テンプレート画面を開く

1. Portal 検索で **「カスタム テンプレートのデプロイ」** を開く
2. **「エディターで独自のテンプレートを作成する」** をクリック
3. **「ファイルの読み込み」** → ローカルの `infra/main.bicep` を選択
   - Portal が自動的に Bicep → ARM JSON にコンパイルします (数秒)
4. **「保存」**

#### 4-2. パラメーター入力

| パラメーター | 値 |
|---|---|
| サブスクリプション | (該当のもの) |
| リソース グループ | `rg-microsoft-training` |
| リージョン | `Japan East` |
| `prefix` | `mslearn` |
| `existingCosmosAccountName` | `cosmos-training-murokawa` |
| `existingCosmosDatabaseName` | `cosmos-training-murokawa` |
| `openAiEndpoint` | `https://foundry-training-murokawa.cognitiveservices.azure.com/` |
| `openAiDeployment` | `gpt-5.4` |
| `foundryAgentUrlSummary` | `https://foundry-training-murokawa.services.ai.azure.com/api/projects/proj-default/applications/summary-agent/protocols/openai/responses?api-version=2025-11-15-preview` |
| `foundryAgentUrlQuiz` | `https://foundry-training-murokawa.services.ai.azure.com/api/projects/proj-default/applications/quiz-agent/protocols/openai/responses?api-version=2025-11-15-preview` |
| `aadClientId` | Step 2-1 で控えた **AAD_CLIENT_ID** |
| `aadClientSecret` | Step 2-2 で控えた **AAD_CLIENT_SECRET** |
| `swaRepositoryUrl` | (空のまま) |

#### 4-3. デプロイ実行

1. **「確認と作成」** → **「作成」**
2. 5〜10 分待機
3. 完了後、デプロイの **「出力」** タブで以下を控える:
   - `staticWebAppHostname` (例: `mslearn-swa-xxxxx.eastasia.2.azurestaticapps.net`)
   - `functionAppName` (例: `mslearn-func`)

#### 4-4. リダイレクト URI を正規化

1. **Microsoft Entra ID** → **アプリの登録** → `MS Learning SWA` → **「認証」**
2. 既存の Web プラットフォームのリダイレクト URI を編集:
   - `https://<staticWebAppHostname>/.auth/login/aad/callback`
3. **「保存」**

---

### 5. SWA デプロイトークン取得

1. Portal 検索で **「Static Web Apps」** → `mslearn-swa` を開く
2. 左メニュー → **「概要」** → 上部の **「デプロイ トークンの管理」** をクリック
3. 表示されたトークンをコピー → `AZURE_STATIC_WEB_APPS_API_TOKEN`

---

### 6. 管理者ロール付与

#### 6-1. 管理者ユーザーを招待 (招待リンク方式)

1. Portal 検索で **「Static Web Apps」** → `mslearn-swa` を開く
2. 左メニュー → **「ロール管理」** → **「+ 招待」**
3. 入力:
   - **承認プロバイダー**: `Microsoft Entra ID` (旧 `aad`)
   - **招待者の詳細**: `naohello117@blogontec.com`
   - **ドメイン**: `https://<staticWebAppHostname>` (Step 4-3 で控えた値)
   - **ロール**: `admin`
   - **有効期限**: `168` 時間 (7 日)
4. **「生成」** をクリック
5. 表示された招待 URL を開く → サインインして「承諾」

> 招待を受けた直後は SWA のロール反映に数分かかる場合があります。

---

### 7. GitHub Secrets / Variables 登録

GitHub リポジトリ **`naohello117/microsoft-training`** で:

#### 7-1. Settings → Environments → `prod` 作成 (推奨)

1. **Settings** → 左メニュー **Environments** → **New environment** → 名前 `prod` → 作成
2. (任意) **Required reviewers** にチェック → 自分を追加すると、本番デプロイに承認必須になる

#### 7-2. Secrets

**Settings → Secrets and variables → Actions → Secrets** タブ → **New repository secret** で以下を登録:

| Name | Value |
|---|---|
| `AZURE_CLIENT_ID` | UAMI Client ID (Step 3-1) |
| `AZURE_TENANT_ID` | テナント ID (Step 1) |
| `AZURE_SUBSCRIPTION_ID` | サブスクリプション ID (Step 1) |
| `AAD_CLIENT_SECRET` | Entra アプリのシークレット (Step 2-2) |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | SWA デプロイトークン (Step 5) |

#### 7-3. Variables

**Settings → Secrets and variables → Actions → Variables** タブ → **New repository variable** で以下を登録:

| Name | Value |
|---|---|
| `AZURE_RG` | `rg-microsoft-training` |
| `RESOURCE_PREFIX` | `mslearn` |
| `FUNCTION_APP_NAME` | `mslearn-func` |
| `EXISTING_COSMOS_ACCOUNT` | `cosmos-training-murokawa` |
| `EXISTING_COSMOS_DATABASE` | `cosmos-training-murokawa` |
| `AZURE_OPENAI_ENDPOINT` | `https://foundry-training-murokawa.cognitiveservices.azure.com/` |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-5.4` |
| `FOUNDRY_AGENT_URL_SUMMARY` | `https://foundry-training-murokawa.services.ai.azure.com/api/projects/proj-default/applications/summary-agent/protocols/openai/responses?api-version=2025-11-15-preview` |
| `FOUNDRY_AGENT_URL_QUIZ` | `https://foundry-training-murokawa.services.ai.azure.com/api/projects/proj-default/applications/quiz-agent/protocols/openai/responses?api-version=2025-11-15-preview` |
| `AAD_CLIENT_ID` | Entra アプリの Client ID (Step 2-1) |

> **注**: `FOUNDRY_AGENT_URL_*` を Variable にしているのは「URL 自体は機密ではない」ため。
> Foundry エージェントの保護は別途 MI 認証で行うこと。

---

## 通常運用 (CI/CD)

| 変更箇所 | トリガーされるワークフロー | 内容 |
|---|---|---|
| `infra/**` | `infra.yml` | Bicep を `az deployment group create` |
| `backend/**` | `backend.yml` | Functions に zip deploy (Oryx remote build) |
| `frontend/**` | `frontend.yml` | SWA に静的サイトをデプロイ |
| `frontend/**` (PR) | `frontend.yml` | プレビュー環境を自動作成 |

すべて `main` ブランチへの push で発火。GitHub の **Actions** タブから **Run workflow** で手動実行も可能。

---

## 管理者によるコンテンツ追加 (運用フロー)

1. ローカルで `backend/local.settings.json` の `COSMOS_DB_ENDPOINT` を **本番** Cosmos に向ける
2. `LOCAL_ADMIN_BYPASS=true` のまま `func start --port 7071`
3. ローカル Vite (`npm run dev`) で `http://localhost:5173/` を開き、URL を貼って「試験を追加」
4. 必要なユニットを開いて要約が生成されることを確認
5. 完了後、`local.settings.json` をローカル開発用に戻す

> **重要**: ローカル実行時は管理者の Entra ID 認証はスキップされ、`LOCAL_ADMIN_BYPASS=true` で動作します。
> 本番 Cosmos への書き込みは `az login` で得たユーザーの権限が使われます (Cosmos Built-in Data Contributor が必要)。

---

## トラブルシューティング

### Functions のログ確認 (Portal)

1. Function App **`mslearn-func`** を開く
2. 左メニュー **「ログ ストリーム」** → リアルタイムログ
3. 詳細クエリは左メニュー **「Application Insights」** → **「ライブ メトリック」** または **「ログ (KQL)」**

### SWA の認証が動かない

- `staticwebapp.config.json` の `<tenant-id>` が置換されているか
- Entra アプリのリダイレクト URI が正しい SWA hostname を指しているか (Step 4-4)
- SWA の **「構成」** で `AAD_CLIENT_ID` / `AAD_CLIENT_SECRET` の値が一致しているか
  - SWA → 左メニュー **「構成」** → **「アプリケーション設定」** タブで確認

### Cosmos アクセスが 401/403

- Cosmos DB アカウント **`cosmos-training-murokawa`** → 左メニュー **「データ エクスプローラー」** 上の **「ロール割り当て」** で、`mslearn-func` のシステム割り当て MI に **「Cosmos DB Built-in Data Contributor」** が割り当てられているか確認
  - Bicep が自動で割り当てるため、通常は不要
- `disableLocalAuth: true` のため、キーベース認証は使えない

### GitHub Actions デプロイが 401

- マネージド ID `ms-learning-deploy` → **「フェデレーション資格情報」** で `subject` が一致しているか (`refs/heads/main` vs `pull_request`)
- UAMI に RG Contributor が付与されているか (Step 3-2)

### CLI 補助 (どうしても GUI で見つからない場合)

```bash
# サブスクリプション/テナント ID
az account show --query "{sub:id, tenant:tenantId}" -o jsonv

# SWA デプロイトークン
az staticwebapp secrets list --name mslearn-swa --resource-group rg-microsoft-training --query properties.apiKey -o tsv

# Functions ログ tail
az webapp log tail --name mslearn-func --resource-group rg-microsoft-training
```

---

## コスト見積 (低トラフィック想定 / 月額)

| リソース | プラン | 概算 |
|---|---|---|
| Static Web Apps | Standard | $9 |
| Functions | Consumption (Y1) | ~$0 (実行時のみ) |
| Cosmos DB | Serverless | ~$1-5 (RU 従量) |
| Storage | Standard LRS | ~$0.5 |
| Application Insights | 5GB/月以内 | $0 |
| **合計** | | **~$10-15/月** |

> Foundry / Azure OpenAI は別途従量課金 (gpt-4o 入力/出力トークン × 利用回数)
