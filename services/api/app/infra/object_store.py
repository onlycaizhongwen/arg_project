from app.core.config import settings


def document_bucket_name() -> str:
    return settings.minio_bucket


def build_object_key(document_id: str, version_id: str, filename: str) -> str:
    safe_name = filename.replace("\\", "_").replace("/", "_") or "uploaded-file"
    return f"documents/{document_id}/versions/{version_id}/{safe_name}"
