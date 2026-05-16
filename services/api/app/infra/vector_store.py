from app.core.config import settings
from qdrant_client import QdrantClient


def vector_collection_name() -> str:
    return settings.qdrant_collection


def build_qdrant_client() -> QdrantClient:
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
