from fastapi import APIRouter, Depends, File, UploadFile

from app.core.errors import AppError
from app.core.request_context import (
    RequestContext,
    get_request_context,
    resolve_actor_id,
    resolve_request_source,
    resolve_tenant_id,
)
from app.services.document_service import (
    create_document_version,
    delete_document,
    list_document_audit_events,
    rebuild_document_index,
    release_document_operation_lock,
)

router = APIRouter()


@router.delete("/{document_id}")
def delete_document_endpoint(
    document_id: str,
    tenant_id: str = "default",
    actor_id: str = "system",
    request_source: str = "api",
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return delete_document(
        document_id=document_id,
        tenant_id=resolve_tenant_id(tenant_id, context),
        actor_id=resolve_actor_id(actor_id, context),
        request_source=resolve_request_source(request_source, context),
    )


@router.post("/{document_id}/rebuild")
def rebuild_document_index_endpoint(
    document_id: str,
    tenant_id: str = "default",
    actor_id: str = "system",
    request_source: str = "api",
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return rebuild_document_index(
        document_id=document_id,
        tenant_id=resolve_tenant_id(tenant_id, context),
        actor_id=resolve_actor_id(actor_id, context),
        request_source=resolve_request_source(request_source, context),
        trace_id=context.trace_id,
    )


@router.post("/{document_id}/locks/release")
def release_document_operation_lock_endpoint(
    document_id: str,
    tenant_id: str = "default",
    stale_lock_minutes: int = 30,
    actor_id: str = "system",
    request_source: str = "api",
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return release_document_operation_lock(
        document_id=document_id,
        tenant_id=resolve_tenant_id(tenant_id, context),
        stale_lock_minutes=stale_lock_minutes,
        actor_id=resolve_actor_id(actor_id, context),
        request_source=resolve_request_source(request_source, context),
    )


@router.get("/{document_id}/audit")
def list_document_audit_events_endpoint(
    document_id: str,
    tenant_id: str = "default",
    limit: int = 50,
    operation: str | None = None,
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return list_document_audit_events(
        document_id=document_id,
        tenant_id=resolve_tenant_id(tenant_id, context),
        limit=limit,
        operation=operation,
    )


@router.put("/{document_id}/versions")
async def create_document_version_endpoint(
    document_id: str,
    file: UploadFile = File(...),
    tenant_id: str = "default",
    actor_id: str = "system",
    request_source: str = "api",
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    payload = await file.read()
    if not payload:
        raise AppError("EMPTY_FILE", "Uploaded file is empty", status_code=400)
    return create_document_version(
        document_id=document_id,
        tenant_id=resolve_tenant_id(tenant_id, context),
        filename=file.filename or "uploaded-file",
        content_type=file.content_type,
        payload=payload,
        actor_id=resolve_actor_id(actor_id, context),
        request_source=resolve_request_source(request_source, context),
        trace_id=context.trace_id,
    )
