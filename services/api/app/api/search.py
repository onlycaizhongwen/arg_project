from typing import Literal

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from app.core.request_context import (
    RequestContext,
    get_request_context,
    resolve_permission_context,
    resolve_tenant_id,
)
from app.services.search_service import search_chunks

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    tenant_id: str = "default"
    knowledge_base_ids: list[str] = Field(default_factory=lambda: ["kb-default"])
    permission_context: list[str] = Field(default_factory=lambda: ["public"])
    search_mode: Literal["semantic", "keyword", "hybrid"] = "hybrid"
    top_k: int = 10
    recall_size: int = 200
    pre_rank_size: int = 50
    dedup_enabled: bool = True
    diversity_enabled: bool = True
    max_chunks_per_document: int = 2
    rerank_enabled: bool = False
    rerank_size: int = 50


@router.post("/search")
def search(
    request: SearchRequest,
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return search_chunks(
        query=request.query,
        tenant_id=resolve_tenant_id(request.tenant_id, context),
        knowledge_base_ids=request.knowledge_base_ids,
        permission_context=resolve_permission_context(request.permission_context, context),
        search_mode=request.search_mode,
        recall_size=request.recall_size,
        pre_rank_size=request.pre_rank_size,
        top_k=request.top_k,
        dedup_enabled=request.dedup_enabled,
        diversity_enabled=request.diversity_enabled,
        max_chunks_per_document=request.max_chunks_per_document,
        rerank_enabled=request.rerank_enabled,
        rerank_size=request.rerank_size,
    )
