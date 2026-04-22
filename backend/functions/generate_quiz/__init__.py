import json
import logging
import datetime
import uuid
import azure.functions as func
from shared.cosmos_client import get_container
from shared.openai_client import get_openai_client, get_deployment

logger = logging.getLogger(__name__)

QUIZ_SYSTEM_PROMPT = """
あなたはAZ-500試験の問題作成の専門家です。
与えられた学習コンテンツに基づいて、試験に出やすい4択クイズを3問作成してください。

必ず以下のJSON形式で出力してください（コードブロックなし）:
[
  {
    "question": "問題文",
    "choices": [
      {"key": "A", "text": "選択肢A"},
      {"key": "B", "text": "選択肢B"},
      {"key": "C", "text": "選択肢C"},
      {"key": "D", "text": "選択肢D"}
    ],
    "correct_key": "A",
    "explanation": "解説文（なぜその答えが正しいか、他の選択肢がなぜ誤りかを説明）"
  }
]

問題のレベル:
- AZ-500の実際の試験と同等の難易度
- 概念の理解を問う問題と実装の判断を問う問題を混在させる
"""


async def main(req: func.HttpRequest) -> func.HttpResponse:
    unit_id: str = req.route_params.get("unit_id", "")
    if not unit_id:
        return func.HttpResponse("unit_idが必要です", status_code=400)

    quizzes_container = get_container("quizzes")
    units_container = get_container("units")

    # 既存クイズを確認
    existing = list(quizzes_container.query_items(
        query="SELECT * FROM c WHERE c.unit_id = @uid",
        parameters=[{"name": "@uid", "value": unit_id}],
        enable_cross_partition_query=True,
    ))
    if existing:
        return func.HttpResponse(
            json.dumps(existing, ensure_ascii=False),
            mimetype="application/json",
        )

    # ユニットのコンテンツを取得
    units = list(units_container.query_items(
        query="SELECT * FROM c WHERE c.id = @id",
        parameters=[{"name": "@id", "value": unit_id}],
        enable_cross_partition_query=True,
    ))
    if not units:
        return func.HttpResponse("ユニットが見つかりません", status_code=404)
    unit = units[0]

    content = unit.get("summary_ja") or unit.get("raw_content", "")
    if not content:
        return func.HttpResponse("コンテンツがありません。先にスクレイピングを実行してください", status_code=404)

    client = get_openai_client()
    response = client.chat.completions.create(
        model=get_deployment(),
        messages=[
            {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
            {"role": "user", "content": content[:5000]},
        ],
        temperature=0.7,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )

    raw_json = response.choices[0].message.content
    try:
        questions = json.loads(raw_json)
        if isinstance(questions, dict):
            questions = questions.get("quizzes") or list(questions.values())[0]
    except json.JSONDecodeError:
        return func.HttpResponse("クイズ生成に失敗しました", status_code=500)

    now = datetime.datetime.utcnow().isoformat() + "Z"
    saved = []
    for q in questions:
        q["id"] = f"quiz-{unit_id}-{uuid.uuid4().hex[:8]}"
        q["unit_id"] = unit_id
        q["module_id"] = unit.get("module_id", "")
        q["generated_at"] = now
        quizzes_container.create_item(q)
        saved.append(q)

    return func.HttpResponse(
        json.dumps(saved, ensure_ascii=False),
        mimetype="application/json",
        status_code=201,
    )
