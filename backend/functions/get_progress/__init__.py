import json
import datetime
import azure.functions as func
from shared.cosmos_client import get_container


async def main(req: func.HttpRequest) -> func.HttpResponse:
    user_id: str = req.route_params.get("user_id", "")
    if not user_id:
        return func.HttpResponse("user_idが必要です", status_code=400)

    container = get_container("user_progress")

    if req.method == "GET":
        learning_path_id = req.params.get("learning_path_id", "az-500")
        progress_id = f"progress-{user_id}-{learning_path_id}"
        try:
            item = container.read_item(item=progress_id, partition_key=user_id)
        except Exception:
            item = {
                "id": progress_id,
                "user_id": user_id,
                "learning_path_id": learning_path_id,
                "completed_units": [],
                "quiz_results": [],
                "total_score": 0,
                "last_accessed": datetime.datetime.utcnow().isoformat() + "Z",
            }
        return func.HttpResponse(json.dumps(item, ensure_ascii=False), mimetype="application/json")

    # POST: クイズ回答を記録
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("リクエストボディが不正です", status_code=400)

    learning_path_id = body.get("learning_path_id", "az-500")
    progress_id = f"progress-{user_id}-{learning_path_id}"

    try:
        item = container.read_item(item=progress_id, partition_key=user_id)
    except Exception:
        item = {
            "id": progress_id,
            "user_id": user_id,
            "learning_path_id": learning_path_id,
            "completed_units": [],
            "quiz_results": [],
            "total_score": 0,
        }

    # ユニット完了を記録
    unit_id = body.get("unit_id")
    if unit_id and unit_id not in item["completed_units"]:
        item["completed_units"].append(unit_id)

    # クイズ結果を記録
    quiz_result = body.get("quiz_result")
    if quiz_result:
        quiz_result["answered_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        item["quiz_results"].append(quiz_result)
        correct_count = sum(1 for r in item["quiz_results"] if r.get("is_correct"))
        item["total_score"] = int(correct_count / len(item["quiz_results"]) * 100)

    item["last_accessed"] = datetime.datetime.utcnow().isoformat() + "Z"
    container.upsert_item(item)

    return func.HttpResponse(json.dumps(item, ensure_ascii=False), mimetype="application/json")
