# プロジェクト概要
Microsoft LearnのAZ-500ラーニングパスをスクレイピングし、AI（Azure OpenAI）を活用して自然な日本語要約とクイズを生成する学習サポートアプリを開発します。
本プロジェクトは、学習効率の向上とともに、Azureのサーバーレスアーキテクチャの実装練習も兼ねています。

# 技術スタック（指定）
- **Frontend**: Azure Static Web Apps
- **Backend**: Azure Functions (Python または TypeScript)
- **Database**: Azure Cosmos DB (NoSQL API / 学習進捗・スクレイピング済みデータの保存用)
- **AI**: Foundry（Claude Opus / Sonnet）
- **Scraping**: Playwright (Azure Functions上、あるいはローカル実行を想定)

# 主要な機能要件
1. **URL解析＆目次スクレイピング**
   - 入力された資格情報URLからラーニングパスの構造を抽出。
   - Cosmos DBにモジュール・ユニットのメタデータ（タイトル、URL、順序）を格納。
2. **コンテンツ抽出と要約生成**
   - 各ユニットの本文をスクレイピング。
   - Azure OpenAIを用いて、機械翻訳特有の不自然な日本語を「プロのエンジニアが教える自然な日本語」に変換して要約。
   - Cosmos DBに要約テキストをキャッシュし、2回目以降のアクセスを高速化。
3. **習熟度チェッククイズ**
   - ユニット内容に基づいた多肢選択式クイズをAIが生成。
   - ユーザーの解答結果と進捗状況をCosmos DBで管理。
4. **UI (Foundry)**
   - Azure Functions APIと連携し、学習コンテンツとクイズを表示するダッシュボード。

# 開発の進め方（Step-by-Step）
以下のステップで実装案を提示してください。

### Step 1: データモデル設計 (Cosmos DB)
- ラーニングパス、モジュール、ユニット、およびユーザー進捗を管理するためのCosmos DBのコンテナ設計（パーティションキーの選定など）を提案してください。

### Step 2: バックエンドAPI (Azure Functions)
- HTTP Triggerを用いて、URLを受け取ってスクレイピングを開始する関数と、Cosmos DBからデータを取得する関数の雛形を作成してください。
- Azure OpenAI Serviceと連携するためのSDK利用コードを含めてください。

### Step 3: スクレイピングロジック
- Playwright等を使用し、Microsoft Learnの構造（`div.content`など）から純粋な学習テキストのみを抽出するロジックを実装してください。

### Step 4: フロントエンド連携 (Foundry)
- FoundryからAzure Functionsの各エンドポイントを呼び出し、取得したデータを表示するためのインターフェース構成を提案してください。

# 特記事項
- AZ-500の学習用アプリであるため、マネージドID（Managed Identity）を利用したリソース間認証など、セキュリティを意識した実装方法があれば併せて提案してください。