import json
import logging
import azure.functions as func
from shared.cosmos_client import get_container
from scraping.ms_learn_scraper import scrape_learning_path

logger = logging.getLogger(__name__)


async def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("リクエストボディが不正です", status_code=400)

    url: str = body.get("url", "").strip()
    if not url or "learn.microsoft.com" not in url:
        return func.HttpResponse("有効なMicrosoft Learn URLを指定してください", status_code=400)

    try:
        path_data = await scrape_learning_path(url)
    except Exception as exc:
        logger.exception("スクレイピング失敗: %s", url)
        return func.HttpResponse(f"スクレイピングに失敗しました: {exc}", status_code=500)

    container = get_container("learning_paths")
    container.upsert_item(path_data)

    units_container = get_container("units")
    for module in path_data.get("modules", []):
        for unit in module.get("units", []):
            units_container.upsert_item(unit)

    return func.HttpResponse(
        json.dumps({"status": "ok", "learning_path_id": path_data["id"]}, ensure_ascii=False),
        mimetype="application/json",
        status_code=202,
    )
