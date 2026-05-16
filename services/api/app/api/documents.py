from fastapi import APIRouter, File, UploadFile

from app.core.errors import AppError
from app.services.document_service import (
    create_document_version,
    delete_document,
    list_document_audit_events,
    rebuild_document_index,
)

router = APIRouter()


@router.delete("/{document_id}")
def delete_document_endpoint(
    document_id: str,
    tenant_id: str = "default",
    actor_id: str = "system",
    request_source: str = "api",
) -> dict[str, object]:
    return delete_document(
        document_id=document_id,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_source=request_source,
    )


@router.post("/{document_id}/rebuild")
def rebuild_document_index_endpoint(
    document_id: str,
    tenant_id: str = "default",
    actor_id: str = "system",
    request_source: str = "api",
) -> dict[str, object]:
    return rebuild_document_index(
        document_id=document_id,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_source=request_source,
    )


@router.get("/{document_id}/audit")
def list_document_audit_events_endpoint(
    document_id: str,
    tenant_id: str = "default",
    limit: int = 50,
    operation: str | None = None,
) -> dict[str, object]:
    return list_document_audit_events(
        document_id=document_id,
        tenant_id=tenant_id,
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
) -> dict[str, object]:
    payload = await file.read()
    if not payload:
        raise AppError("EMPTY_FILE", "Uploaded file is empty", status_code=400)
    return create_document_version(
        document_id=document_id,
        tenant_id=tenant_id,
        filename=file.filename or "uploaded-file",
        content_type=file.content_type,
        payload=payload,
        actor_id=actor_id,
        request_source=request_source,
    )
