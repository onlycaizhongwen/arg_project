from pathlib import Path

from minio import Minio

from app.core.config import settings


def download_document(object_key: str, target_dir: Path, filename: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / (filename or "uploaded-file")
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    client.fget_object(settings.minio_bucket, object_key, str(target_path))
    return target_path
