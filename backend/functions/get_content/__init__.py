import json
import logging
import azure.functions as func
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from shared.cosmos_client import get_container
from shared.openai_client import get_openai_client, get_deployment

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """
あなたはMicrosoft Azureの認定試験（AZ-500）に精通したシニアセキュリティエンジニアです。
与えられた英語または機械翻訳された日本語のテキストを、
日本のエンジニアが読んで自然に理解できる技術日本語で要約してください。

要約のルール:
- 箇条書きで要点を5〜8項目にまとめる
- 専門用語は英語表記を括弧内に残す（例: 条件付きアクセス (Conditional Access)）
- 試験に出やすいポイントには「★試験ポイント」と明記する
- 文字数は400〜600字程度
"""


async def main(req: func.HttpRequest) -> func.HttpResponse:
    unit_id: str = req.route_params.get("unit_id", "")
    if not unit_id:
        return func.HttpResponse("unit_idが必要です", status_code=400)

    container = get_container("units")

    try:
        # パーティションキーなしで ID 検索（クロスパーティションクエリ）
        items = list(container.query_items(
            query="SELECT * FROM c WHERE c.id = @id",
            parameters=[{"name": "@id", "value": unit_id}],
            enable_cross_partition_query=True,
        ))
        if not items:
            return func.HttpResponse("ユニットが見つかりません", status_code=404)
        unit = items[0]
    except CosmosResourceNotFoundError:
        return func.HttpResponse("ユニットが見つかりません", status_code=404)

    # キャッシュ済み要約があれば即返却
    if unit.get("summary_ja"):
        return func.HttpResponse(
            json.dumps(unit, ensure_ascii=False),
            mimetype="application/json",
        )

    raw = unit.get("raw_content", "")
    if not raw:
        return func.HttpResponse("コンテンツがまだスクレイピングされていません", status_code=404)

    # Azure OpenAI で要約生成
    client = get_openai_client()
    response = client.chat.completions.create(
        model=get_deployment(),
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": raw[:6000]},  # トークン制限のため先頭6000字
        ],
        temperature=0.3,
        max_tokens=1000,
    )
    summary = response.choices[0].message.content

    unit["summary_ja"] = summary
    unit["summary_generated_at"] = func.HttpRequest.__module__  # ISO timestamp
    import datetime
    unit["summary_generated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    container.upsert_item(unit)

    return func.HttpResponse(
        json.dumps(unit, ensure_ascii=False),
        mimetype="application/json",
    )
