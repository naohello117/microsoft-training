"""
Azure AI Foundry のエージェント（OpenAI Responses API 形式）を呼び出すユーティリティ。

Foundry Portal で作成したエージェントは `/applications/<agent-name>/protocols/openai/responses`
というエンドポイントで OpenAI Responses API 互換の呼び出しを受け付ける。
instructions / model / temperature / response_format はエージェント側で管理される。

エージェント仕様は docs/foundry-agents.md を参照。
"""

import os
import time
import logging
from typing import Optional

import aiohttp
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AccessToken

logger = logging.getLogger(__name__)

_TOKEN_SCOPE = "https://ai.azure.com/.default"
_TOKEN_REFRESH_BUFFER_SEC = 300

_credential: Optional[DefaultAzureCredential] = None
_cached_token: Optional[AccessToken] = None


def _get_token() -> str:
    """Foundry 1DP 用アクセストークンを取得（有効期限切れ前に自動更新）。"""
    global _credential, _cached_token
    if _credential is None:
        _credential = DefaultAzureCredential()
    if _cached_token is None or (_cached_token.expires_on - time.time()) < _TOKEN_REFRESH_BUFFER_SEC:
        _cached_token = _credential.get_token(_TOKEN_SCOPE)
    return _cached_token.token


def get_agent_url(kind: str) -> str:
    """kind: 'summary' | 'quiz' に対応するエージェントURLを環境変数から取得。"""
    env_key = {
        "summary": "FOUNDRY_AGENT_URL_SUMMARY",
        "quiz": "FOUNDRY_AGENT_URL_QUIZ",
    }.get(kind)
    if env_key is None:
        raise ValueError(f"未対応のエージェント種別: {kind}")
    value = os.environ.get(env_key, "").strip()
    if not value:
        raise RuntimeError(
            f"環境変数 {env_key} が未設定です。"
            f"Foundry Portal で {kind} エージェントを作成し、応答APIエンドポイントURLを設定してください。"
            f"（詳細: docs/foundry-agents.md）"
        )
    return value


def _extract_text(data: dict) -> str:
    """Responses API レスポンスから本文テキストを抽出する。

    レスポンス形状は以下のいずれかを想定:
    1. {"output_text": "..."} (OpenAI SDK が合成する便宜フィールド)
    2. {"output": [{"type": "message", "content": [{"type": "output_text", "text": "..."}]}]}
    """
    if isinstance(data.get("output_text"), str) and data["output_text"]:
        return data["output_text"]

    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            ctype = content.get("type")
            if ctype in ("output_text", "text"):
                text = content.get("text")
                if isinstance(text, str):
                    return text
                if isinstance(text, dict) and isinstance(text.get("value"), str):
                    return text["value"]
    raise RuntimeError(f"Responses API の応答からテキストが抽出できませんでした: keys={list(data)}")


async def invoke_agent(agent_url: str, user_content: str, timeout_sec: int = 120) -> str:
    """Foundry Responses API エンドポイントを呼び出して応答テキストを返す。

    Parameters
    ----------
    agent_url : str
        `/applications/<agent>/protocols/openai/responses?api-version=...` 形式の完全URL。
    user_content : str
        エージェントに渡すユーザー入力。
    timeout_sec : int
        HTTP タイムアウト秒数。

    Returns
    -------
    str
        エージェントからの応答テキスト。
    """
    headers = {
        "Authorization": f"Bearer {_get_token()}",
        "Content-Type": "application/json",
    }
    payload = {"input": user_content}

    timeout = aiohttp.ClientTimeout(total=timeout_sec)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(agent_url, headers=headers, json=payload) as resp:
            body_text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(
                    f"エージェント呼び出しが失敗しました: status={resp.status}, body={body_text[:800]}"
                )
            try:
                data = await resp.json(content_type=None)
            except Exception as exc:
                raise RuntimeError(
                    f"エージェント応答のJSONパースに失敗: {exc}, body={body_text[:500]}"
                )

    return _extract_text(data)
