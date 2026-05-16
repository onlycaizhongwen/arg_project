from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import uuid4

from app.core.config import settings
from app.db.session import build_psycopg_url
from app.embeddings.embedding_client import build_embedding_client
from app.infra.vector_store import build_qdrant_client
from app.rerank.rerank_client import RerankInput, build_rerank_client

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from qdrant_client.http import models


RRF_K = 60
KEYWORD_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "does",
    "for",
    "from",
    "how",
    "is",
    "of",
    "or",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "why",
    "with",
}


@dataclass
class Candidate:
    chunk_id: str
    semantic_score: float | None = None
    keyword_score: float | None = None
    semantic_rank: int | None = None
    keyword_rank: int | None = None
    recall_sources: set[str] = field(default_factory=set)
    pre_rank_score: float = 0.0


def search_chunks(
    *,
    query: str,
    tenant_id: str,
    knowledge_base_ids: list[str],
    permission_context: list[str],
    search_mode: str,
    recall_size: int,
    pre_rank_size: int,
    top_k: int,
    dedup_enabled: bool,
    diversity_enabled: bool,
    max_chunks_per_document: int,
    rerank_enabled: bool,
    rerank_size: int,
) -> dict[str, object]:
    semantic_candidates: list[Candidate] = []
    keyword_candidates: list[Candidate] = []

    if search_mode in {"semantic", "hybrid"}:
        semantic_candidates = _semantic_recall(
            query=query,
            tenant_id=tenant_id,
            knowledge_base_ids=knowledge_base_ids,
            permission_context=permission_context,
            limit=recall_size,
        )
    if search_mode in {"keyword", "hybrid"}:
        keyword_candidates = _keyword_recall(
            query=query,
            tenant_id=tenant_id,
            knowledge_base_ids=knowledge_base_ids,
            permission_context=permission_context,
            limit=recall_size,
        )

    merged_candidates = _merge_candidates(
        semantic_candidates=semantic_candidates,
        keyword_candidates=keyword_candidates,
        search_mode=search_mode,
    )
    trimmed_candidates = merged_candidates[:pre_rank_size]
    candidate_chunk_ids = [candidate.chunk_id for candidate in trimmed_candidates]
    chunks_by_id = _load_chunks(
        candidate_chunk_ids,
        tenant_id=tenant_id,
        knowledge_base_ids=knowledge_base_ids,
        permission_context=permission_context,
    )
    dedup_candidates = (
        _deduplicate_candidates(trimmed_candidates, chunks_by_id)
        if dedup_enabled
        else trimmed_candidates
    )
    limited_candidates = _limit_candidates_per_document(
        dedup_candidates,
        chunks_by_id,
        max_chunks_per_document=max_chunks_per_document,
    )
    business_candidates = (
        _diversify_candidates(limited_candidates, chunks_by_id, limit=top_k)
        if diversity_enabled
        else limited_candidates
    )
    rerank_degraded = False
    rerank_scores: dict[str, float] = {}
    ranked_candidates = business_candidates
    if rerank_enabled and settings.rerank_provider != "disabled":
        try:
            ranked_candidates, rerank_scores = _rerank_candidates(
                query=query,
                candidates=business_candidates,
                chunks_by_id=chunks_by_id,
                rerank_size=rerank_size,
            )
        except Exception:
            rerank_degraded = True
            _record_search_diagnostic_event(
                tenant_id=tenant_id,
                event_type="RERANK_DEGRADED",
                metadata={
                    "search_mode": search_mode,
                    "rerank_provider": settings.rerank_provider,
                    "rerank_model": settings.rerank_model,
                    "candidate_count": len(business_candidates),
                },
            )
            ranked_candidates = business_candidates
    selected_candidates = ranked_candidates[:top_k]

    items: list[dict[str, object]] = []
    for candidate in selected_candidates:
        row = chunks_by_id.get(candidate.chunk_id)
        if row is None:
            continue
        items.append(
            {
                "chunk_id": candidate.chunk_id,
                "score": candidate.pre_rank_score,
                "recall_sources": sorted(candidate.recall_sources),
                "semantic_score": candidate.semantic_score,
                "keyword_score": candidate.keyword_score,
                "pre_rank_score": candidate.pre_rank_score,
                "rerank_score": rerank_scores.get(candidate.chunk_id),
                "content": row["content"],
                "document_id": str(row["document_id"]),
                "document_version_id": str(row["document_version_id"]),
                "knowledge_base_id": row["knowledge_base_id"],
                "permission_tags": row["permission_tags"],
                "chunk_index": row["chunk_index"],
                "metadata": row["metadata"],
            }
        )
    return {
        "query": query,
        "items": items,
        "search_plan": {
            "search_mode": search_mode,
            "recall_size": recall_size,
            "pre_rank_size": pre_rank_size,
            "top_k": top_k,
            "dedup_enabled": dedup_enabled,
            "diversity_enabled": diversity_enabled,
            "max_chunks_per_document": max_chunks_per_document,
            "permission_context": permission_context,
            "semantic_recall_count": len(semantic_candidates),
            "keyword_recall_count": len(keyword_candidates),
            "merged_count": len(merged_candidates),
            "business_filtered_count": len(business_candidates),
            "dedup_removed_count": max(0, len(trimmed_candidates) - len(dedup_candidates)),
            "document_limit_removed_count": max(0, len(dedup_candidates) - len(limited_candidates)),
            "rerank_size": rerank_size,
            "rerank_provider": settings.rerank_provider,
            "rerank_enabled": rerank_enabled,
            "rerank_degraded": rerank_degraded,
        },
    }


def _semantic_recall(
    *,
    query: str,
    tenant_id: str,
    knowledge_base_ids: list[str],
    permission_context: list[str],
    limit: int,
) -> list[Candidate]:
    query_vector = build_embedding_client().embed_query(query)
    points = _search_qdrant(
        query_vector=query_vector,
        tenant_id=tenant_id,
        knowledge_base_ids=knowledge_base_ids,
        permission_context=permission_context,
        limit=limit,
    )
    candidates: list[Candidate] = []
    for rank, point in enumerate(points, start=1):
        candidates.append(
            Candidate(
                chunk_id=str(point.id),
                semantic_score=point.score,
                semantic_rank=rank,
                recall_sources={"semantic"},
            )
        )
    return candidates


def _keyword_recall(
    *,
    query: str,
    tenant_id: str,
    knowledge_base_ids: list[str],
    permission_context: list[str],
    limit: int,
) -> list[Candidate]:
    tsquery = _build_keyword_tsquery(query)
    if not tsquery:
        return []
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    tc.id,
                    ts_rank_cd(to_tsvector('simple', content), to_tsquery('simple', %s)) AS keyword_score
                FROM text_chunk
                AS tc
                JOIN document_version AS dv ON dv.id = tc.document_version_id
                JOIN document AS d ON d.id = dv.document_id
                WHERE tc.tenant_id = %s
                  AND tc.knowledge_base_id = ANY(%s)
                  AND tc.permission_tags && %s::text[]
                  AND d.status = 'INDEXED'
                  AND dv.status = 'INDEXED'
                  AND to_tsvector('simple', content) @@ to_tsquery('simple', %s)
                ORDER BY keyword_score DESC, tc.created_at DESC
                LIMIT %s
                """,
                (tsquery, tenant_id, knowledge_base_ids, permission_context, tsquery, limit),
            )
            rows = cursor.fetchall()
    candidates: list[Candidate] = []
    for rank, row in enumerate(rows, start=1):
        candidates.append(
            Candidate(
                chunk_id=str(row["id"]),
                keyword_score=float(row["keyword_score"]),
                keyword_rank=rank,
                recall_sources={"keyword"},
            )
        )
    return candidates


def _build_keyword_tsquery(query: str) -> str:
    terms = []
    for term in re.findall(r"[A-Za-z0-9_]+", query.lower()):
        if len(term) < 2 or term in KEYWORD_STOP_WORDS:
            continue
        terms.append(term)
    deduped_terms = list(dict.fromkeys(terms))
    return " | ".join(deduped_terms[:12])


def _merge_candidates(
    *,
    semantic_candidates: list[Candidate],
    keyword_candidates: list[Candidate],
    search_mode: str,
) -> list[Candidate]:
    merged: dict[str, Candidate] = {}
    for candidate in semantic_candidates:
        merged[candidate.chunk_id] = candidate
    for keyword_candidate in keyword_candidates:
        existing = merged.get(keyword_candidate.chunk_id)
        if existing is None:
            merged[keyword_candidate.chunk_id] = keyword_candidate
            continue
        existing.keyword_score = keyword_candidate.keyword_score
        existing.keyword_rank = keyword_candidate.keyword_rank
        existing.recall_sources.update(keyword_candidate.recall_sources)

    for candidate in merged.values():
        if search_mode == "semantic":
            candidate.pre_rank_score = float(candidate.semantic_score or 0.0)
        elif search_mode == "keyword":
            candidate.pre_rank_score = float(candidate.keyword_score or 0.0)
        else:
            semantic_rrf = (
                1.0 / (RRF_K + candidate.semantic_rank)
                if candidate.semantic_rank is not None
                else 0.0
            )
            keyword_rrf = (
                1.0 / (RRF_K + candidate.keyword_rank)
                if candidate.keyword_rank is not None
                else 0.0
            )
            candidate.pre_rank_score = semantic_rrf + keyword_rrf

    return sorted(
        merged.values(),
        key=lambda item: (item.pre_rank_score, item.semantic_score or 0.0, item.keyword_score or 0.0),
        reverse=True,
    )


def _deduplicate_candidates(
    candidates: list[Candidate],
    chunks_by_id: dict[str, dict[str, object]],
) -> list[Candidate]:
    seen_content_keys: set[str] = set()
    deduplicated: list[Candidate] = []
    for candidate in candidates:
        row = chunks_by_id.get(candidate.chunk_id)
        if row is None:
            continue
        content_key = _normalize_content_key(str(row["content"]))
        if content_key in seen_content_keys:
            continue
        seen_content_keys.add(content_key)
        deduplicated.append(candidate)
    return deduplicated


def _limit_candidates_per_document(
    candidates: list[Candidate],
    chunks_by_id: dict[str, dict[str, object]],
    *,
    max_chunks_per_document: int,
) -> list[Candidate]:
    if max_chunks_per_document <= 0:
        return candidates
    counts_by_document_version: dict[str, int] = {}
    limited: list[Candidate] = []
    for candidate in candidates:
        row = chunks_by_id.get(candidate.chunk_id)
        if row is None:
            continue
        document_version_id = str(row["document_version_id"])
        current_count = counts_by_document_version.get(document_version_id, 0)
        if current_count >= max_chunks_per_document:
            continue
        counts_by_document_version[document_version_id] = current_count + 1
        limited.append(candidate)
    return limited


def _diversify_candidates(
    candidates: list[Candidate],
    chunks_by_id: dict[str, dict[str, object]],
    *,
    limit: int,
) -> list[Candidate]:
    remaining = list(candidates)
    selected: list[Candidate] = []
    while remaining and len(selected) < limit:
        best_candidate = max(
            remaining,
            key=lambda candidate: _mmr_score(candidate, selected, chunks_by_id),
        )
        selected.append(best_candidate)
        remaining.remove(best_candidate)
    selected_ids = {candidate.chunk_id for candidate in selected}
    return selected + [candidate for candidate in candidates if candidate.chunk_id not in selected_ids]


def _mmr_score(
    candidate: Candidate,
    selected: list[Candidate],
    chunks_by_id: dict[str, dict[str, object]],
    lambda_value: float = 0.7,
) -> float:
    relevance = candidate.pre_rank_score
    if not selected:
        return relevance
    candidate_tokens = _content_tokens(chunks_by_id.get(candidate.chunk_id, {}).get("content", ""))
    max_similarity = 0.0
    for selected_candidate in selected:
        selected_tokens = _content_tokens(
            chunks_by_id.get(selected_candidate.chunk_id, {}).get("content", "")
        )
        max_similarity = max(max_similarity, _jaccard_similarity(candidate_tokens, selected_tokens))
    return lambda_value * relevance - (1.0 - lambda_value) * max_similarity


def _normalize_content_key(content: str) -> str:
    return re.sub(r"\s+", " ", content.lower()).strip()


def _content_tokens(content: object) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9_]+", str(content).lower()))


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _rerank_candidates(
    *,
    query: str,
    candidates: list[Candidate],
    chunks_by_id: dict[str, dict[str, object]],
    rerank_size: int,
) -> tuple[list[Candidate], dict[str, float]]:
    rerank_candidates = candidates[: max(0, rerank_size)]
    passthrough_candidates = candidates[len(rerank_candidates) :]
    inputs = [
        RerankInput(
            chunk_id=candidate.chunk_id,
            content=str(chunks_by_id.get(candidate.chunk_id, {}).get("content", "")),
            pre_rank_score=candidate.pre_rank_score,
        )
        for candidate in rerank_candidates
    ]
    results = build_rerank_client().rerank(query=query, items=inputs)
    scores_by_id = {result.chunk_id: result.score for result in results}
    candidates_by_id = {candidate.chunk_id: candidate for candidate in rerank_candidates}
    ranked_candidates = [
        candidates_by_id[result.chunk_id]
        for result in results
        if result.chunk_id in candidates_by_id
    ]
    ranked_ids = {candidate.chunk_id for candidate in ranked_candidates}
    ranked_candidates.extend(
        candidate for candidate in rerank_candidates if candidate.chunk_id not in ranked_ids
    )
    ranked_candidates.extend(passthrough_candidates)
    return ranked_candidates, scores_by_id


def _search_qdrant(
    *,
    query_vector: list[float],
    tenant_id: str,
    knowledge_base_ids: list[str],
    permission_context: list[str],
    limit: int,
) -> list[object]:
    client = build_qdrant_client()
    must_conditions: list[models.FieldCondition] = [
        models.FieldCondition(
            key="tenant_id",
            match=models.MatchValue(value=tenant_id),
        )
    ]
    if knowledge_base_ids:
        must_conditions.append(
            models.FieldCondition(
                key="knowledge_base_id",
                match=models.MatchAny(any=knowledge_base_ids),
            )
        )
    if permission_context:
        must_conditions.append(
            models.FieldCondition(
                key="permission_tags",
                match=models.MatchAny(any=permission_context),
            )
        )
    response = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        query_filter=models.Filter(must=must_conditions),
        limit=limit,
        with_payload=True,
    )
    return list(response.points)


def _load_chunks(
    chunk_ids: list[str],
    *,
    tenant_id: str,
    knowledge_base_ids: list[str],
    permission_context: list[str],
) -> dict[str, dict[str, object]]:
    if not chunk_ids:
        return {}
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    tc.id,
                    tc.document_version_id,
                    dv.document_id,
                    d.knowledge_base_id,
                    tc.permission_tags,
                    tc.chunk_index,
                    tc.content,
                    tc.metadata
                FROM text_chunk
                AS tc
                JOIN document_version AS dv ON dv.id = tc.document_version_id
                JOIN document AS d ON d.id = dv.document_id
                WHERE tc.id = ANY(%s)
                  AND tc.tenant_id = %s
                  AND tc.knowledge_base_id = ANY(%s)
                  AND tc.permission_tags && %s::text[]
                  AND d.status = 'INDEXED'
                  AND dv.status = 'INDEXED'
                """,
                (chunk_ids, tenant_id, knowledge_base_ids, permission_context),
            )
            rows = cursor.fetchall()
    return {str(row["id"]): dict(row) for row in rows}


def _record_search_diagnostic_event(
    *,
    tenant_id: str,
    event_type: str,
    metadata: dict[str, object],
) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO search_diagnostic_event (id, tenant_id, event_type, metadata)
                VALUES (%s, %s, %s, %s)
                """,
                (str(uuid4()), tenant_id, event_type, Jsonb(metadata)),
            )
