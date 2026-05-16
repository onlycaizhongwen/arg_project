from fastapi import APIRouter, File, UploadFile

from app.core.errors import AppError
from app.services.ingestion_service import ingest_file

router = APIRouter()


@router.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    source_id: str = "default-file-source",
    tenant_id: str = "default",
    knowledge_base_id: str = "kb-default",
    permission_tags: str = "public",
) -> dict[str, object]:
    payload = await file.read()
    if not payload:
        raise AppError("EMPTY_FILE", "Uploaded file is empty", status_code=400)
    result = ingest_file(
        tenant_id=tenant_id,
        source_id=source_id,
        knowledge_base_id=knowledge_base_id,
        permission_tags=_parse_permission_tags(permission_tags),
        filename=file.filename or "uploaded-file",
        content_type=file.content_type,
        payload=payload,
    )
    return result.__dict__


def _parse_permission_tags(raw_value: str) -> list[str]:
    tags = [tag.strip() for tag in raw_value.split(",") if tag.strip()]
    return tags or ["public"]
