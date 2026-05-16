from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.core.config import settings


def collection_name() -> str:
    return settings.qdrant_collection


def build_qdrant_client() -> QdrantClient:
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)


def ensure_collection(client: QdrantClient) -> None:
    try:
        client.get_collection(settings.qdrant_collection)
    except Exception:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=models.VectorParams(
                size=settings.embedding_dimension,
                distance=models.Distance.COSINE,
            ),
        )


def upsert_vectors(
    *,
    vectors: list[list[float]],
    chunk_ids: list[str],
    payloads: list[dict[str, object]],
) -> None:
    if not vectors:
        return
    client = build_qdrant_client()
    ensure_collection(client)
    points = [
        models.PointStruct(id=chunk_id, vector=vector, payload=payload)
        for chunk_id, vector, payload in zip(chunk_ids, vectors, payloads, strict=True)
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=points)
