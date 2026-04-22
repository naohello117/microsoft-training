# Azure AI Foundry エージェント設計仕様

本アプリは Foundry Portal で作成した **2つのエージェント** を OpenAI **Responses API** 経由で参照する方式で動作します。
プロンプトの文言・モデル・温度などの変更はアプリ再デプロイ不要で Foundry 側だけで反映可能です。

---

## 前提

- Foundry プロジェクト: `foundry-training-murokawa` / `proj-default`
- 呼び出しプロトコル: **OpenAI Responses API**
  （`/applications/<agent-name>/protocols/openai/responses?api-version=2025-11-15-preview`）
- 認証: Azure Functions のマネージド ID → トークンスコープ `https://ai.azure.com/.default`
- 必要ロール: Foundry プロジェクトの **Azure AI Developer**
- 使用モデル: `gpt-4o`（Foundry 側の deployment 名と一致させる）

---

## エージェント1: summary-agent

Microsoft Learn のユニット本文を、日本のエンジニアが読みやすい技術日本語要約に変換するエージェント。

### 基本設定

| 項目 | 値 |
|------|------|
| **Name** | `summary-agent` |
| **Model** | `gpt-4o` |
| **Temperature** | `0.3` |
| **Top P** | `1.0`（デフォルト） |
| **Response format** | `Text`（プレーンテキスト / Markdown） |
| **Tools** | なし |

### Instructions

```
あなたは Microsoft Azure の認定試験（AZ-500 / SC-300 / SC-100 など）に精通したシニアセキュリティエンジニアです。
ユーザーから与えられる英語または機械翻訳された日本語のテキストを、
日本のエンジニアが読んで自然に理解できる技術日本語で要約してください。

# 出力ルール
- Markdown で出力する（見出し `##` / 箇条書き `-` / 太字 `**` を活用）
- 要点は箇条書きで 5〜8 項目にまとめる
- 専門用語は日本語訳の直後に英語表記を括弧内に残す（例: 条件付きアクセス (Conditional Access)）
- 試験に出やすいポイントには行頭に「★試験ポイント」と明記する
- 全体の文字数は 400〜600 字程度
- 前置き（「以下に要約します」など）・後書き（「以上が要約です」など）は書かない
- コードブロック（```）での囲みは不要

# リンクの扱い
- 入力テキストには `[表示文字](URL)` 形式の Markdown リンクが含まれる場合がある
- 要約内で関連する用語に言及する際は、入力に存在する **そのままの URL** を使って Markdown リンク `[text](url)` を残すこと
- 入力に存在しない URL を **創作してはならない**（架空のドキュメントURLを書かない）
- リンクは要点の理解を助ける箇所だけに付与し、本文中の全リンクを羅列しない
```

---

## エージェント2: quiz-agent

ユニットの学習内容から4択の習熟度チェッククイズ（3問）を生成するエージェント。

### 基本設定

| 項目 | 値 |
|------|------|
| **Name** | `quiz-agent` |
| **Model** | `gpt-4o` |
| **Temperature** | `0.7` |
| **Top P** | `1.0`（デフォルト） |
| **Response format** | `JSON Schema`（下記スキーマを登録） |
| **Tools** | なし |

### Instructions

```
あなたは Microsoft Azure 認定試験（AZ-500 / SC-300 / SC-100 など）の問題作成を専門とするエキスパートです。
ユーザーから与えられる学習コンテンツに基づいて、試験に出やすい 4 択クイズを 3 問作成してください。

# 出力ルール
- 出力は指定された JSON Schema に完全一致させる
- 問題文は日本語、選択肢も日本語。ただし製品名・サービス名は英語表記を維持する
- 難易度は実試験レベル（単純な用語暗記ではなく、シナリオ判断を問う問題を含める）
- 解説は「なぜこの選択肢が正しいのか」「他の選択肢がなぜ誤りか」を 2〜3 文で明記する
- correct_key は "A" / "B" / "C" / "D" のいずれか1つ
```

### JSON Schema（Foundry Portal の「Response format = JSON Schema」欄に貼り付け）

```json
{
  "name": "quiz_response",
  "strict": true,
  "schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["quizzes"],
    "properties": {
      "quizzes": {
        "type": "array",
        "minItems": 3,
        "maxItems": 3,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["question", "choices", "correct_key", "explanation"],
          "properties": {
            "question": { "type": "string" },
            "choices": {
              "type": "array",
              "minItems": 4,
              "maxItems": 4,
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["key", "text"],
                "properties": {
                  "key": { "type": "string", "enum": ["A", "B", "C", "D"] },
                  "text": { "type": "string" }
                }
              }
            },
            "correct_key": { "type": "string", "enum": ["A", "B", "C", "D"] },
            "explanation": { "type": "string" }
          }
        }
      }
    }
  }
}
```

---

## アプリ側の設定

Foundry Portal のエージェント詳細画面 → **応答APIエンドポイント**（`/protocols/openai/responses`）のURLをコピーし、
Azure Functions のアプリ設定（または `local.settings.json`）に登録します。

```json
{
  "FOUNDRY_AGENT_URL_SUMMARY": "https://foundry-training-murokawa.services.ai.azure.com/api/projects/proj-default/applications/summary-agent/protocols/openai/responses?api-version=2025-11-15-preview",
  "FOUNDRY_AGENT_URL_QUIZ":    "https://foundry-training-murokawa.services.ai.azure.com/api/projects/proj-default/applications/quiz-agent/protocols/openai/responses?api-version=2025-11-15-preview"
}
```

アプリは `aiohttp` でこのURLに以下のHTTPリクエストを送ります。

```
POST <FOUNDRY_AGENT_URL_SUMMARY>
Authorization: Bearer <managed identity token, scope = https://ai.azure.com/.default>
Content-Type: application/json

{ "input": "<scraped unit text>" }
```

応答は Responses API フォーマット（`output_text` または `output[].content[].text`）でパースされます。

---

## 動作検証手順（Foundry Portal 上）

1. Foundry Portal → Agents → 対象エージェントを開く
2. Instructions / Model / Temperature / Response format を本仕様書通りに設定
3. 右ペインの **Playground** でサンプル本文を貼り付けて応答を確認
4. Playground の応答が要件通りになっているか目視確認
   - summary-agent: Markdown、箇条書き 5〜8 項目、400〜600 字
   - quiz-agent: JSON Schema に合致（3問 × 4択、各問に explanation）
5. 問題なければ「応答APIエンドポイント」URLをコピーしてアプリに登録

---

## 運用上の注意

- **エージェントの instructions 更新はアプリ再デプロイ不要**で即時反映されます。
- **エージェント名を変更すると URL も変わる**ため、環境変数の更新が必要です。
  通常は名前固定で instructions のみ更新する運用が推奨です。
- **Rate limit**: Foundry プロジェクトに紐づく `gpt-4o` deployment の TPM / RPM に依存します。
  大量ユニットを同時に要約生成すると制限に掛かる可能性があるため、
  フロント側で逐次リクエストするか、バックエンドにリトライを入れてください。
- **ステートレス運用**: Responses API の `input` に毎回本文全文を渡すため、会話履歴は保持されません。
  「このクイズを難しくして」等の対話対応をしたい場合は、
  `previous_response_id` を Cosmos DB に保存する拡張を検討してください。
