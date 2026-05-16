from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings


class EmbeddingClient(ABC):
    def __init__(self, model: str, dimension: int) -> None:
        self.model = model
        self.dimension = dimension

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError


class MockEmbeddingClient(EmbeddingClient):
    def embed_query(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        for index in range(self.dimension):
            byte = digest[index % len(digest)]
            values.append((byte / 255.0) * 2.0 - 1.0)
        return values


class DashScopeEmbeddingClient(EmbeddingClient):
    def embed_query(self, text: str) -> list[float]:
        if not settings.dashscope_api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required for dashscope embedding provider.")
        endpoint = (
            settings.embedding_base_url
            or "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
        )
        response = httpx.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {settings.dashscope_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": {"texts": [text]},
                "parameters": {
                    "dimension": self.dimension,
                    "output_type": settings.embedding_output_type,
                    "text_type": "query",
                },
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["output"]["embeddings"][0]["embedding"]


class LocalBgeEmbeddingClient(EmbeddingClient):
    def embed_query(self, text: str) -> list[float]:
        if not settings.embedding_base_url:
            raise RuntimeError("EMBEDDING_BASE_URL is required for local_bge embedding provider.")
        endpoint = settings.embedding_base_url.rstrip("/")
        if not endpoint.endswith("/embeddings"):
            endpoint = f"{endpoint}/v1/embeddings"
        response = httpx.post(
            endpoint,
            json={"model": self.model, "input": [text]},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if "data" in payload:
            return payload["data"][0]["embedding"]
        if "embeddings" in payload:
            return payload["embeddings"][0]
        raise RuntimeError("Local BGE embedding response does not contain embeddings.")


def build_embedding_client() -> EmbeddingClient:
    provider = settings.embedding_provider.lower()
    if provider == "mock":
        return MockEmbeddingClient(settings.embedding_model, settings.embedding_dimension)
    if provider == "dashscope":
        return DashScopeEmbeddingClient(settings.embedding_model, settings.embedding_dimension)
    if provider == "local_bge":
        return LocalBgeEmbeddingClient(settings.embedding_model, settings.embedding_dimension)
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")
