import json
import logging
import datetime
import os
import uuid
import azure.functions as func
from shared.cosmos_client import get_container
from shared.foundry_agent import get_agent_url, invoke_agent
from shared.auth import require_admin


def _scrape_disabled() -> bool:
    """本番環境では Playwright が動かないため、サーバー側スクレイピングを無効化する。"""
    return os.environ.get("DISABLE_SCRAPE", "").lower() in ("1", "true", "yes")

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# GET /api/exams  試験（コレクション）一覧
# ------------------------------------------------------------------ #
@app.route(route="exams", methods=["GET"])
async def list_exams(req: func.HttpRequest) -> func.HttpResponse:
    container = get_container("learning_paths")
    items = list(container.query_items(
        "SELECT c.exam_id, c.exam_name FROM c",
        enable_cross_partition_query=True,
    ))
    seen: dict = {}
    for item in items:
        eid = item.get("exam_id") or "uncategorized"
        ename = item.get("exam_name") or "未分類"
        if eid not in seen:
            seen[eid] = {"exam_id": eid, "exam_name": ename, "path_count": 0}
        seen[eid]["path_count"] += 1
    return func.HttpResponse(json.dumps(list(seen.values()), ensure_ascii=False), mimetype="application/json")


# ------------------------------------------------------------------ #
# GET /api/learning-paths  保存済みラーニングパス一覧（exam_idでフィルタ可）
# ------------------------------------------------------------------ #
@app.route(route="learning-paths", methods=["GET"])
async def list_learning_paths(req: func.HttpRequest) -> func.HttpResponse:
    exam_id = req.params.get("exam_id", "").strip()
    container = get_container("learning_paths")
    if exam_id:
        items = list(container.query_items(
            "SELECT c.id, c.title, c.url, c.modules, c.exam_id, c.exam_name FROM c WHERE c.exam_id = @eid",
            parameters=[{"name": "@eid", "value": exam_id}],
            enable_cross_partition_query=True,
        ))
    else:
        items = list(container.query_items(
            "SELECT c.id, c.title, c.url, c.modules, c.exam_id, c.exam_name FROM c",
            enable_cross_partition_query=True,
        ))
    return func.HttpResponse(json.dumps(items, ensure_ascii=False), mimetype="application/json")


# ------------------------------------------------------------------ #
# PATCH /api/learning-paths/{path_id}  試験タグを更新
# ------------------------------------------------------------------ #
@app.route(route="learning-paths/{path_id}", methods=["PATCH"])
async def update_learning_path(req: func.HttpRequest) -> func.HttpResponse:
    if resp := require_admin(req):
        return resp
    path_id: str = req.route_params.get("path_id", "")
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("リクエストボディが不正です", status_code=400)

    container = get_container("learning_paths")
    items = list(container.query_items(
        "SELECT * FROM c WHERE c.id = @id",
        parameters=[{"name": "@id", "value": path_id}],
        enable_cross_partition_query=True,
    ))
    if not items:
        return func.HttpResponse("ラーニングパスが見つかりません", status_code=404)

    item = items[0]
    if "exam_id" in body:
        item["exam_id"] = body["exam_id"]
    if "exam_name" in body:
        item["exam_name"] = body["exam_name"]
    container.upsert_item(item)
    return func.HttpResponse(json.dumps({"status": "ok"}, ensure_ascii=False), mimetype="application/json")


# ------------------------------------------------------------------ #
# GET /api/units/{module_id}  モジュール内のユニット一覧
# ------------------------------------------------------------------ #
@app.route(route="units/{module_id}", methods=["GET"])
async def list_units(req: func.HttpRequest) -> func.HttpResponse:
    module_id: str = req.route_params.get("module_id", "")
    container = get_container("units")
    items = list(container.query_items(
        query='SELECT c.id, c.title, c.url, c["order"], c.is_scraped, c.summary_ja FROM c WHERE c.module_id = @mid',
        parameters=[{"name": "@mid", "value": module_id}],
        enable_cross_partition_query=True,
    ))
    items.sort(key=lambda x: x.get("order", 0))
    return func.HttpResponse(json.dumps(items, ensure_ascii=False), mimetype="application/json")


# ------------------------------------------------------------------ #
# POST /api/scrape  URLを受け取りスクレイピングを開始
# ------------------------------------------------------------------ #
@app.route(route="scrape", methods=["POST"])
async def scrape_url(req: func.HttpRequest) -> func.HttpResponse:
    if _scrape_disabled():
        return func.HttpResponse(
            json.dumps({
                "error": "scrape_disabled",
                "message": "本番環境ではスクレイピング機能は無効化されています。管理者がローカル環境から実行してください。",
            }, ensure_ascii=False),
            mimetype="application/json",
            status_code=503,
        )
    if resp := require_admin(req):
        return resp
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("リクエストボディが不正です", status_code=400)

    url: str = body.get("url", "").strip()
    if not url or "learn.microsoft.com" not in url:
        return func.HttpResponse("有効なMicrosoft Learn URLを指定してください", status_code=400)

    # フロントから明示的に指定された場合はそれで上書き、なければスクレイパー側の自動判別を採用
    override_exam_id: str = body.get("exam_id", "").strip()
    override_exam_name: str = body.get("exam_name", "").strip()

    try:
        from scraping.ms_learn_scraper import scrape_from_url
        result = await scrape_from_url(url)
    except Exception as exc:
        logger.exception("スクレイピング失敗: %s", url)
        return func.HttpResponse(f"スクレイピングに失敗しました: {exc}", status_code=500)

    paths_data = result.get("paths", [])
    derived_exam_id = result.get("exam_id")
    derived_exam_name = result.get("exam_name")
    if not paths_data:
        return func.HttpResponse("スクレイピング結果が空です", status_code=500)

    effective_exam_id = override_exam_id or derived_exam_id
    effective_exam_name = override_exam_name or derived_exam_name

    container = get_container("learning_paths")
    units_container = get_container("units")
    saved_paths = []

    for path_data in paths_data:
        if effective_exam_id:
            path_data["exam_id"] = effective_exam_id
        if effective_exam_name:
            path_data["exam_name"] = effective_exam_name

        for module in path_data.get("modules", []):
            for unit in module.get("units", []):
                units_container.upsert_item(unit)
            module.pop("units", None)  # learning_paths には units を含めない

        container.upsert_item(path_data)
        saved_paths.append({
            "learning_path_id": path_data["id"],
            "title": path_data.get("title", ""),
        })

    return func.HttpResponse(
        json.dumps({
            "status": "ok",
            "paths": saved_paths,
            "exam_id": effective_exam_id,
            "exam_name": effective_exam_name,
        }, ensure_ascii=False),
        mimetype="application/json",
        status_code=202,
    )


# ------------------------------------------------------------------ #
# GET /api/content/{unit_id}  要約を取得（なければ生成）
# ------------------------------------------------------------------ #
@app.route(route="content/{unit_id}", methods=["GET"])
async def get_content(req: func.HttpRequest) -> func.HttpResponse:
    unit_id: str = req.route_params.get("unit_id", "")
    if not unit_id:
        return func.HttpResponse("unit_idが必要です", status_code=400)

    force = req.params.get("force", "").lower() in ("1", "true", "yes")

    container = get_container("units")
    items = list(container.query_items(
        query="SELECT * FROM c WHERE c.id = @id",
        parameters=[{"name": "@id", "value": unit_id}],
        enable_cross_partition_query=True,
    ))
    if not items:
        return func.HttpResponse("ユニットが見つかりません", status_code=404)
    unit = items[0]

    if unit.get("summary_ja") and not force:
        return func.HttpResponse(json.dumps(unit, ensure_ascii=False), mimetype="application/json")

    # 再要約 (force=true) のみ管理者限定。初回生成は一般ユーザーにも許可する
    # （管理者がすべてのラーニングパスを事前生成する負担を避けるため）
    if force and (resp := require_admin(req)):
        return resp

    raw = unit.get("raw_content", "")
    # 遅延スクレイピング：目次のみ取得時は raw_content が空なのでここで本文取得
    # ユニット本文は HTTP + BeautifulSoup で取得するため Playwright 不要 → 本番でも動作
    if not raw:
        unit_url = unit.get("url", "")
        if not unit_url:
            return func.HttpResponse("ユニットURLが不明です", status_code=500)
        try:
            from scraping.ms_learn_scraper import scrape_single_unit_http
            raw = await scrape_single_unit_http(unit_url)
        except Exception as exc:
            logger.exception("本文スクレイピング失敗: %s", unit_url)
            return func.HttpResponse(f"本文取得に失敗しました: {exc}", status_code=500)
        if not raw:
            return func.HttpResponse("本文が空でした", status_code=500)
        unit["raw_content"] = raw
        unit["scraped_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        unit["is_scraped"] = True

    try:
        summary_text = await invoke_agent(
            agent_url=get_agent_url("summary"),
            user_content=raw[:6000],
        )
    except Exception as exc:
        logger.exception("summary-agent 呼び出し失敗: unit_id=%s", unit_id)
        return func.HttpResponse(f"要約生成に失敗しました: {exc}", status_code=500)

    unit["summary_ja"] = summary_text
    unit["summary_generated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    container.upsert_item(unit)

    return func.HttpResponse(json.dumps(unit, ensure_ascii=False), mimetype="application/json")


# ------------------------------------------------------------------ #
# POST /api/quiz/{unit_id}  クイズを生成（キャッシュあり再利用）
# ------------------------------------------------------------------ #
@app.route(route="quiz/{unit_id}", methods=["POST"])
async def generate_quiz(req: func.HttpRequest) -> func.HttpResponse:
    unit_id: str = req.route_params.get("unit_id", "")
    if not unit_id:
        return func.HttpResponse("unit_idが必要です", status_code=400)

    quizzes_container = get_container("quizzes")
    existing = list(quizzes_container.query_items(
        query="SELECT * FROM c WHERE c.unit_id = @uid",
        parameters=[{"name": "@uid", "value": unit_id}],
        enable_cross_partition_query=True,
    ))
    if existing:
        return func.HttpResponse(json.dumps(existing, ensure_ascii=False), mimetype="application/json")

    # 初回クイズ生成は一般ユーザーにも許可する
    # （再生成のエンドポイントは未提供。今後追加する場合は force パラメータで管理者限定にする）

    units = list(get_container("units").query_items(
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

    try:
        quiz_text = await invoke_agent(
            agent_url=get_agent_url("quiz"),
            user_content=content[:5000],
        )
    except Exception as exc:
        logger.exception("quiz-agent 呼び出し失敗: unit_id=%s", unit_id)
        return func.HttpResponse(f"クイズ生成に失敗しました: {exc}", status_code=500)

    try:
        data = json.loads(quiz_text)
        questions = data.get("quizzes") or list(data.values())[0]
    except (json.JSONDecodeError, IndexError, AttributeError):
        logger.error("quiz-agent の応答がJSONとしてパースできません: %s", quiz_text[:500])
        return func.HttpResponse("クイズ生成に失敗しました（応答がJSON形式ではありません）", status_code=500)

    now = datetime.datetime.utcnow().isoformat() + "Z"
    saved = []
    for q in questions:
        q["id"] = f"quiz-{unit_id}-{uuid.uuid4().hex[:8]}"
        q["unit_id"] = unit_id
        q["module_id"] = unit.get("module_id", "")
        q["generated_at"] = now
        quizzes_container.create_item(q)
        saved.append(q)

    return func.HttpResponse(json.dumps(saved, ensure_ascii=False), mimetype="application/json", status_code=201)


# ------------------------------------------------------------------ #
# GET /POST /api/progress/{user_id}  進捗管理
# ------------------------------------------------------------------ #
@app.route(route="progress/{user_id}", methods=["GET", "POST"])
async def get_progress(req: func.HttpRequest) -> func.HttpResponse:
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
                "id": progress_id, "user_id": user_id,
                "learning_path_id": learning_path_id,
                "completed_units": [], "quiz_results": [],
                "total_score": 0,
                "last_accessed": datetime.datetime.utcnow().isoformat() + "Z",
            }
        return func.HttpResponse(json.dumps(item, ensure_ascii=False), mimetype="application/json")

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
            "id": progress_id, "user_id": user_id,
            "learning_path_id": learning_path_id,
            "completed_units": [], "quiz_results": [], "total_score": 0,
        }

    unit_id = body.get("unit_id")
    if unit_id and unit_id not in item["completed_units"]:
        item["completed_units"].append(unit_id)

    quiz_result = body.get("quiz_result")
    if quiz_result:
        quiz_result["answered_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        item["quiz_results"].append(quiz_result)
        correct_count = sum(1 for r in item["quiz_results"] if r.get("is_correct"))
        item["total_score"] = int(correct_count / len(item["quiz_results"]) * 100)

    item["last_accessed"] = datetime.datetime.utcnow().isoformat() + "Z"
    container.upsert_item(item)
    return func.HttpResponse(json.dumps(item, ensure_ascii=False), mimetype="application/json")
