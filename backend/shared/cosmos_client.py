import os
from azure.cosmos import CosmosClient, PartitionKey
from azure.identity import DefaultAzureCredential

_client: CosmosClient | None = None
_db = None


def get_cosmos_client() -> CosmosClient:
    global _client
    if _client is None:
        endpoint = os.environ["COSMOS_DB_ENDPOINT"]
        # Managed Identity を優先し、ローカルではAzure CLIにフォールバック
        credential = DefaultAzureCredential()
        _client = CosmosClient(endpoint, credential=credential)
    return _client


def get_database():
    global _db
    if _db is None:
        db_name = os.environ["COSMOS_DB_DATABASE"]
        _db = get_cosmos_client().get_database_client(db_name)
    return _db


def get_container(name: str):
    return get_database().get_container_client(name)
