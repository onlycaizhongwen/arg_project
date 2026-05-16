from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass(frozen=True)
class RerankInput:
    chunk_id: str
    content: str
    pre_rank_score: float


@dataclass(frozen=True)
class RerankResult:
    chunk_id: str
    score: float


class RerankClient:
    def rerank(self, *, query: str, items: list[RerankInput]) -> list[RerankResult]:
        raise NotImplementedError


class DisabledRerankClient(RerankClient):
    def rerank(self, *, query: str, items: list[RerankInput]) -> list[RerankResult]:
        del query
        return [RerankResult(chunk_id=item.chunk_id, score=item.pre_rank_score) for item in items]


class MockRerankClient(RerankClient):
    def rerank(self, *, query: str, items: list[RerankInput]) -> list[RerankResult]:
        query_terms = _tokenize(query)
        results: list[RerankResult] = []
        for item in items:
            content_terms = _tokenize(item.content)
            overlap = len(query_terms & content_terms)
            score = item.pre_rank_score + overlap * 0.01
            results.append(RerankResult(chunk_id=item.chunk_id, score=score))
        return sorted(results, key=lambda result: result.score, reverse=True)


class ExternalRerankClient(RerankClient):
    def rerank(self, *, query: str, items: list[RerankInput]) -> list[RerankResult]:
        endpoint = settings.rerank_base_url.rstrip("/")
        response = httpx.post(
            endpoint,
            json={
                "model": settings.rerank_model,
                "query": query,
                "documents": [
                    {
                        "id": item.chunk_id,
                        "text": item.content,
                        "pre_rank_score": item.pre_rank_score,
                    }
                    for item in items
                ],
            },
            timeout=settings.rerank_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        raw_results = payload.get("results", payload.get("data", []))
        results: list[RerankResult] = []
        for item in raw_results:
            chunk_id = str(item.get("id") or item.get("chunk_id"))
            score = float(item.get("score") or item.get("relevance_score") or 0.0)
            results.append(RerankResult(chunk_id=chunk_id, score=score))
        return sorted(results, key=lambda result: result.score, reverse=True)


def build_rerank_client() -> RerankClient:
    provider = settings.rerank_provider.lower()
    if provider == "disabled":
        return DisabledRerankClient()
    if provider == "mock":
        return MockRerankClient()
    if provider == "external":
        return ExternalRerankClient()
    raise ValueError(f"Unsupported rerank provider: {settings.rerank_provider}")


def _tokenize(text: str) -> set[str]:
    import re

    return set(re.findall(r"[A-Za-z0-9_]+", text.lower()))
