# Cosmos DB データモデル設計

## コンテナ構成

### 1. `learning_paths` コンテナ
パーティションキー: `/id`

```json
{
  "id": "az-500",
  "title": "AZ-500: Microsoft Azure Security Technologies",
  "url": "https://learn.microsoft.com/ja-jp/training/paths/...",
  "modules": [
    {
      "id": "module-001",
      "title": "Azure でのID管理",
      "url": "https://...",
      "order": 1,
      "unit_count": 8
    }
  ],
  "created_at": "2026-04-18T00:00:00Z",
  "updated_at": "2026-04-18T00:00:00Z"
}
```

### 2. `units` コンテナ
パーティションキー: `/module_id`

```json
{
  "id": "unit-001-01",
  "module_id": "module-001",
  "learning_path_id": "az-500",
  "title": "Azure Active Directoryの概要",
  "url": "https://...",
  "order": 1,
  "raw_content": "...",
  "summary_ja": "Azure ADはクラウドベースのID管理サービスで...",
  "summary_generated_at": "2026-04-18T00:00:00Z",
  "is_scraped": true,
  "scraped_at": "2026-04-18T00:00:00Z"
}
```

### 3. `quizzes` コンテナ
パーティションキー: `/unit_id`

```json
{
  "id": "quiz-001-01-001",
  "unit_id": "unit-001-01",
  "module_id": "module-001",
  "question": "Azure ADにおいて、MFAを強制するために使用するポリシーは？",
  "choices": [
    { "key": "A", "text": "条件付きアクセスポリシー" },
    { "key": "B", "text": "NSGルール" },
    { "key": "C", "text": "Azureポリシー" },
    { "key": "D", "text": "RBACロール" }
  ],
  "correct_key": "A",
  "explanation": "条件付きアクセスポリシーはAzure ADの機能で、...",
  "generated_at": "2026-04-18T00:00:00Z"
}
```

### 4. `user_progress` コンテナ
パーティションキー: `/user_id`

```json
{
  "id": "progress-user001-az-500",
  "user_id": "user001",
  "learning_path_id": "az-500",
  "completed_units": ["unit-001-01", "unit-001-02"],
  "quiz_results": [
    {
      "quiz_id": "quiz-001-01-001",
      "unit_id": "unit-001-01",
      "answered_key": "A",
      "is_correct": true,
      "answered_at": "2026-04-18T00:00:00Z"
    }
  ],
  "total_score": 85,
  "last_accessed": "2026-04-18T00:00:00Z"
}
```

## インデックス設計

- `units`: `module_id` + `order` の複合インデックス（順序通りの取得用）
- `quizzes`: `unit_id` のインデックス（ユニット別クイズ取得用）
- `user_progress`: `user_id` + `learning_path_id` の複合インデックス

## TTL 設定

- `units.raw_content`: スクレイピング後30日でTTL（再スクレイプ用）
- `user_progress`: なし（永続保存）
