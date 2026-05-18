from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import uuid4

from minio import Minio

from app.core.config import settings
from app.db.session import build_psycopg_url
from app.infra.mq import publish_cleaning_job
from app.infra.object_store import build_object_key

import psycopg


@dataclass(frozen=True)
class IngestionResult:
    job_id: str
    document_id: str
    document_version_id: str
    source_id: str
    knowledge_base_id: str
    permission_tags: list[str]
    filename: str
    status: str


def ingest_file(
    *,
    tenant_id: str,
    source_id: str,
    knowledge_base_id: str,
    permission_tags: list[str],
    filename: str,
    content_type: str | None,
    payload: bytes,
    trace_id: str | None = None,
) -> IngestionResult:
    document_id = str(uuid4())
    version_id = str(uuid4())
    job_id = str(uuid4())
    checksum = hashlib.sha256(payload).hexdigest()
    object_key = build_object_key(document_id, version_id, filename)

    _put_object(object_key, payload, content_type)
    _create_ingestion_records(
        tenant_id=tenant_id,
        source_id=source_id,
        knowledge_base_id=knowledge_base_id,
        permission_tags=permission_tags,
        document_id=document_id,
        version_id=version_id,
        job_id=job_id,
        filename=filename,
        content_type=content_type,
        object_key=object_key,
        checksum=checksum,
    )
    publish_cleaning_job(
        {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "knowledge_base_id": knowledge_base_id,
            "permission_tags": permission_tags,
            "document_id": document_id,
            "document_version_id": version_id,
            "object_key": object_key,
            "filename": filename,
            "operation": "INDEX_DOCUMENT",
            "trace_id": trace_id,
        }
    )
    return IngestionResult(
        job_id=job_id,
        document_id=document_id,
        document_version_id=version_id,
        source_id=source_id,
        knowledge_base_id=knowledge_base_id,
        permission_tags=permission_tags,
        filename=filename,
        status="PENDING",
    )


def _put_object(object_key: str, payload: bytes, content_type: str | None) -> None:
    from io import BytesIO

    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
    client.put_object(
        settings.minio_bucket,
        object_key,
        BytesIO(payload),
        length=len(payload),
        content_type=content_type or "application/octet-stream",
    )


def _create_ingestion_records(
    *,
    tenant_id: str,
    source_id: str,
    knowledge_base_id: str,
    permission_tags: list[str],
    document_id: str,
    version_id: str,
    job_id: str,
    filename: str,
    content_type: str | None,
    object_key: str,
    checksum: str,
) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO document (
                    id, tenant_id, knowledge_base_id, permission_tags, data_source_id, title, source_uri, content_type, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'UPLOADED')
                """,
                (
                    document_id,
                    tenant_id,
                    knowledge_base_id,
                    permission_tags,
                    source_id,
                    filename,
                    object_key,
                    content_type,
                ),
            )
            cursor.execute(
                """
                INSERT INTO document_version (
                    id, document_id, version_no, object_key, checksum, status
                )
                VALUES (%s, %s, 1, %s, %s, 'UPLOADED')
                """,
                (version_id, document_id, object_key, checksum),
            )
            cursor.execute(
                """
                INSERT INTO cleaning_job (id, document_version_id, tenant_id, status)
                VALUES (%s, %s, %s, 'PENDING')
                """,
                (job_id, version_id, tenant_id),
            )
