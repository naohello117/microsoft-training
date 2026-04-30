"""
Azure Static Web Apps 標準認証から流れてくる `x-ms-client-principal` ヘッダーを
デコードし、管理者ロール (`admin`) の有無を判定するヘルパー。

ローカル開発では `LOCAL_ADMIN_BYPASS=true` を環境変数に指定すると、
ヘッダーが無くても管理者として扱う（本番では絶対に設定しないこと）。
"""

import base64
import json
import logging
import os
from typing import Any, Optional

import azure.functions as func

logger = logging.getLogger(__name__)

_ADMIN_ROLE = "admin"


def get_client_principal(req: func.HttpRequest) -> Optional[dict[str, Any]]:
    raw = req.headers.get("x-ms-client-principal")
    if not raw:
        return None
    try:
        decoded = base64.b64decode(raw).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        logger.warning("x-ms-client-principal のデコードに失敗")
        return None


def is_admin(req: func.HttpRequest) -> bool:
    # ローカル開発バイパス（local.settings.json で設定）
    if os.environ.get("LOCAL_ADMIN_BYPASS", "").lower() in ("1", "true", "yes"):
        return True
    principal = get_client_principal(req)
    if not principal:
        return False
    roles = principal.get("userRoles") or []
    return _ADMIN_ROLE in roles


def require_admin(req: func.HttpRequest) -> Optional[func.HttpResponse]:
    """管理者でなければ 403 を返す。呼び出し側で `if resp: return resp` でガードする。"""
    if is_admin(req):
        return None
    return func.HttpResponse(
        json.dumps({"error": "admin_required", "message": "この操作には管理者権限が必要です"}, ensure_ascii=False),
        mimetype="application/json",
        status_code=403,
    )
