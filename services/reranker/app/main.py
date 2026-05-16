from __future__ import annotations

import os
from functools import lru_cache

from fastapi import FastAPI
from pydantic import BaseModel, Field
from sentence_transformers import CrossEncoder


class RerankDocument(BaseModel):
    id: str
    text: str
    pre_rank_score: float = 0.0


class RerankRequest(BaseModel):
    model: str | None = None
    query: str
    documents: list[RerankDocument] = Field(default_factory=list)


class RerankItem(BaseModel):
    id: str
    score: float


app = FastAPI(title="rag-bge-reranker", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "rag-bge-reranker", "model": _model_name()}


@app.post("/rerank")
def rerank(request: RerankRequest) -> dict[str, object]:
    if not request.documents:
        return {"model": _model_name(request.model), "results": []}

    model = _load_model(_model_name(request.model))
    pairs = [(request.query, document.text) for document in request.documents]
    scores = model.predict(pairs)
    results = [
        RerankItem(id=document.id, score=float(score))
        for document, score in zip(request.documents, scores, strict=True)
    ]
    results.sort(key=lambda item: item.score, reverse=True)
    return {
        "model": _model_name(request.model),
        "results": [item.model_dump() for item in results],
    }


def _model_name(request_model: str | None = None) -> str:
    return request_model or os.getenv("RERANK_MODEL", "BAAI/bge-reranker-base")


@lru_cache(maxsize=1)
def _load_model(model_name: str) -> CrossEncoder:
    return CrossEncoder(model_name)
