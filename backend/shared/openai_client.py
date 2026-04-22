import os
from openai import AzureOpenAI, OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

_client: AzureOpenAI | OpenAI | None = None


def get_openai_client() -> AzureOpenAI | OpenAI:
    """
    エンドポイント形式に応じてクライアントを返す。

    - Azure AI Foundry プロジェクトエンドポイント (.services.ai.azure.com/api/projects/...):
        azure-ai-projects SDK 経由で OpenAI クライアントを取得。
        認証・URLの組み立てを SDK に委譲するため、設定が最もシンプル。

    - 従来の Azure OpenAI エンドポイント (.openai.azure.com):
        AzureOpenAI クライアントを Managed Identity トークンで初期化。
    """
    global _client
    if _client is None:
        endpoint = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")

        if "/api/projects/" in endpoint:
            from azure.ai.projects import AIProjectClient
            project = AIProjectClient(
                endpoint=endpoint,
                credential=DefaultAzureCredential(),
            )
            _client = project.get_openai_client()
        else:
            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
            _client = AzureOpenAI(
                azure_endpoint=endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2024-08-01-preview",
            )
    return _client


def get_deployment() -> str:
    return os.environ["AZURE_OPENAI_DEPLOYMENT"]
