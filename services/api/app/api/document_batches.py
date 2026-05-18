from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends

from app.core.request_context import (
    RequestContext,
    get_request_context,
    resolve_actor_id,
    resolve_request_source,
    resolve_tenant_id,
)
from app.services.document_batch_service import (
    cancel_document_batch,
    create_rebuild_batch,
    get_document_batch,
    list_document_batch_items,
    retry_failed_batch_items,
)

router = APIRouter()


class RebuildBatchRequest(BaseModel):
    tenant_id: str = "default"
    knowledge_base_id: str | None = None
    source_id: str | None = None
    document_ids: list[str] | None = None
    actor_id: str = "system"
    request_source: str = "api"
    limit: int = Field(default=100, ge=1, le=500)


@router.post("/rebuild")
def create_rebuild_batch_endpoint(
    request: RebuildBatchRequest,
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return create_rebuild_batch(
        tenant_id=resolve_tenant_id(request.tenant_id, context),
        knowledge_base_id=request.knowledge_base_id,
        source_id=request.source_id,
        document_ids=request.document_ids,
        actor_id=resolve_actor_id(request.actor_id, context),
        request_source=resolve_request_source(request.request_source, context),
        limit=request.limit,
        trace_id=context.trace_id,
    )


@router.get("/{batch_id}")
def get_document_batch_endpoint(
    batch_id: str,
    tenant_id: str = "default",
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return get_document_batch(batch_id=batch_id, tenant_id=resolve_tenant_id(tenant_id, context))


@router.post("/{batch_id}/retry-failed")
def retry_failed_batch_items_endpoint(
    batch_id: str,
    tenant_id: str = "default",
    actor_id: str = "system",
    request_source: str = "api",
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return retry_failed_batch_items(
        batch_id=batch_id,
        tenant_id=resolve_tenant_id(tenant_id, context),
        actor_id=resolve_actor_id(actor_id, context),
        request_source=resolve_request_source(request_source, context),
        trace_id=context.trace_id,
    )


@router.post("/{batch_id}/cancel")
def cancel_document_batch_endpoint(
    batch_id: str,
    tenant_id: str = "default",
    actor_id: str = "system",
    request_source: str = "api",
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return cancel_document_batch(
        batch_id=batch_id,
        tenant_id=resolve_tenant_id(tenant_id, context),
        actor_id=resolve_actor_id(actor_id, context),
        request_source=resolve_request_source(request_source, context),
    )


@router.get("/{batch_id}/items")
def list_document_batch_items_endpoint(
    batch_id: str,
    tenant_id: str = "default",
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return list_document_batch_items(
        batch_id=batch_id,
        tenant_id=resolve_tenant_id(tenant_id, context),
        status=status,
        limit=limit,
        offset=offset,
    )
