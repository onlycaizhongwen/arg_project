from __future__ import annotations

import hashlib
from io import BytesIO
from uuid import uuid4

from minio import Minio

from app.core.config import settings
from app.core.errors import AppError
from app.db.session import build_psycopg_url
from app.infra.mq import publish_cleaning_job
from app.infra.object_store import build_object_key
from app.infra.vector_store import build_qdrant_client

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from qdrant_client.http import models


def create_document_version(
    *,
    document_id: str,
    tenant_id: str,
    filename: str,
    content_type: str | None,
    payload: bytes,
    actor_id: str = "system",
    request_source: str = "api",
    trace_id: str | None = None,
) -> dict[str, object]:
    version_id = str(uuid4())
    job_id = str(uuid4())
    document = _acquire_document_operation_lock(
        document_id=document_id,
        tenant_id=tenant_id,
        operation_status="UPDATE_VERSION",
        lock_id=job_id,
        actor_id=actor_id,
        request_source=request_source,
    )
    version_no = int(document["next_version_no"])
    checksum = hashlib.sha256(payload).hexdigest()
    object_key = build_object_key(document_id, version_id, filename)

    try:
        _put_object(object_key, payload, content_type)
        _create_version_records(
            tenant_id=tenant_id,
            document_id=document_id,
            version_id=version_id,
            version_no=version_no,
            job_id=job_id,
            object_key=object_key,
            checksum=checksum,
        )
        _insert_audit_event(
            tenant_id=tenant_id,
            document_id=document_id,
            document_version_id=version_id,
            job_id=job_id,
            operation="DOCUMENT_VERSION_CREATED",
            actor_id=actor_id,
            request_source=request_source,
            metadata={
                "version_no": version_no,
                "filename": filename,
                "content_type": content_type,
                "checksum": checksum,
                "operation_lock_id": job_id,
            },
        )
        publish_cleaning_job(
            {
                "job_id": job_id,
                "tenant_id": tenant_id,
                "knowledge_base_id": document["knowledge_base_id"],
                "permission_tags": document["permission_tags"],
                "document_id": document_id,
                "document_version_id": version_id,
                "object_key": object_key,
                "filename": filename,
                "operation": "UPDATE_VERSION",
                "trace_id": trace_id,
            }
        )
    except Exception:
        _release_document_operation_lock(document_id=document_id, tenant_id=tenant_id, lock_id=job_id)
        raise
    return {
        "job_id": job_id,
        "document_id": document_id,
        "document_version_id": version_id,
        "version_no": version_no,
        "knowledge_base_id": document["knowledge_base_id"],
        "permission_tags": document["permission_tags"],
        "filename": filename,
        "status": "PENDING",
    }


def delete_document(
    *,
    document_id: str,
    tenant_id: str,
    actor_id: str = "system",
    request_source: str = "api",
) -> dict[str, object]:
    lock_id = str(uuid4())
    lock_acquired = _acquire_delete_operation_lock(
        document_id=document_id,
        tenant_id=tenant_id,
        lock_id=lock_id,
        actor_id=actor_id,
        request_source=request_source,
    )
    chunk_ids = _load_document_chunk_ids(document_id=document_id, tenant_id=tenant_id)
    if chunk_ids is None:
        if lock_acquired:
            _release_document_operation_lock(document_id=document_id, tenant_id=tenant_id, lock_id=lock_id)
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", status_code=404)

    try:
        deleted_vector_count = _delete_qdrant_points(chunk_ids)
        _mark_document_deleted(document_id=document_id, tenant_id=tenant_id, lock_id=lock_id if lock_acquired else None)
    except Exception:
        if lock_acquired:
            _release_document_operation_lock(document_id=document_id, tenant_id=tenant_id, lock_id=lock_id)
        raise
    _insert_audit_event(
        tenant_id=tenant_id,
        document_id=document_id,
        document_version_id=None,
        job_id=None,
        operation="DOCUMENT_DELETED",
        actor_id=actor_id,
        request_source=request_source,
            metadata={
                "chunk_count": len(chunk_ids),
                "deleted_vector_count": deleted_vector_count,
            },
        )
    _insert_audit_event(
        tenant_id=tenant_id,
        document_id=document_id,
        document_version_id=None,
        job_id=None,
        operation="DOCUMENT_DELETE_SUCCEEDED",
        actor_id=actor_id,
        request_source=request_source,
        metadata={
            "chunk_count": len(chunk_ids),
            "deleted_vector_count": deleted_vector_count,
        },
    )
    return {
        "document_id": document_id,
        "tenant_id": tenant_id,
        "status": "DELETED",
        "chunk_count": len(chunk_ids),
        "deleted_vector_count": deleted_vector_count,
    }


def rebuild_document_index(
    *,
    document_id: str,
    tenant_id: str,
    actor_id: str = "system",
    request_source: str = "api",
    trace_id: str | None = None,
) -> dict[str, object]:
    job_id = str(uuid4())
    _acquire_document_operation_lock(
        document_id=document_id,
        tenant_id=tenant_id,
        operation_status="REBUILD_INDEX",
        lock_id=job_id,
        actor_id=actor_id,
        request_source=request_source,
    )
    document = _load_indexed_document_version(document_id=document_id, tenant_id=tenant_id)
    if document is None:
        _release_document_operation_lock(document_id=document_id, tenant_id=tenant_id, lock_id=job_id)
        raise AppError("DOCUMENT_VERSION_NOT_INDEXED", "Indexed document version not found", status_code=409)

    try:
        _create_rebuild_job(job_id=job_id, tenant_id=tenant_id, version_id=str(document["version_id"]))
        _insert_audit_event(
            tenant_id=tenant_id,
            document_id=document_id,
            document_version_id=str(document["version_id"]),
            job_id=job_id,
            operation="DOCUMENT_INDEX_REBUILD_REQUESTED",
            actor_id=actor_id,
            request_source=request_source,
            metadata={
                "version_no": document["version_no"],
                "object_key": document["object_key"],
                "operation_lock_id": job_id,
            },
        )
        publish_cleaning_job(
            {
                "job_id": job_id,
                "tenant_id": tenant_id,
                "knowledge_base_id": document["knowledge_base_id"],
                "permission_tags": document["permission_tags"],
                "document_id": document_id,
                "document_version_id": str(document["version_id"]),
                "object_key": document["object_key"],
            "filename": document["title"] or "uploaded-file",
            "rebuild": True,
            "operation": "REBUILD_INDEX",
            "trace_id": trace_id,
        }
    )
    except Exception:
        _release_document_operation_lock(document_id=document_id, tenant_id=tenant_id, lock_id=job_id)
        raise
    return {
        "job_id": job_id,
        "document_id": document_id,
        "document_version_id": str(document["version_id"]),
        "version_no": document["version_no"],
        "knowledge_base_id": document["knowledge_base_id"],
        "permission_tags": document["permission_tags"],
        "status": "PENDING",
        "operation": "REBUILD_INDEX",
    }


def release_document_operation_lock(
    *,
    document_id: str,
    tenant_id: str,
    stale_lock_minutes: int = 30,
    actor_id: str = "system",
    request_source: str = "api",
) -> dict[str, object]:
    stale_lock_minutes = max(1, stale_lock_minutes)
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    tenant_id,
                    status,
                    operation_status,
                    operation_lock_id,
                    operation_started_at
                FROM document
                WHERE id = %s
                  AND tenant_id = %s
                FOR UPDATE
                """,
                (document_id, tenant_id),
            )
            document = cursor.fetchone()
            if document is None:
                raise AppError("DOCUMENT_NOT_FOUND", "Document not found", status_code=404)
            if document["status"] == "DELETED":
                raise AppError("DOCUMENT_DELETED", "Document is deleted", status_code=409)
            if document["operation_status"] is None or document["operation_lock_id"] is None:
                raise AppError("DOCUMENT_OPERATION_LOCK_NOT_FOUND", "Document operation lock not found", status_code=404)

            cursor.execute(
                """
                SELECT now() - operation_started_at AS lock_age
                FROM document
                WHERE id = %s
                  AND tenant_id = %s
                  AND operation_started_at < now() - (%s::text || ' minutes')::interval
                """,
                (document_id, tenant_id, stale_lock_minutes),
            )
            stale_row = cursor.fetchone()
            if stale_row is None:
                raise AppError("DOCUMENT_OPERATION_LOCK_NOT_STALE", "Document operation lock is not stale", status_code=409)

            lock_id = str(document["operation_lock_id"])
            cursor.execute(
                """
                SELECT id, status
                FROM cleaning_job
                WHERE id = %s
                  AND status IN ('PENDING', 'RUNNING', 'RETRYING')
                LIMIT 1
                """,
                (lock_id,),
            )
            active_job = cursor.fetchone()
            if active_job is not None:
                raise AppError("DOCUMENT_OPERATION_LOCK_JOB_ACTIVE", "Document operation lock job is still active", status_code=409)

            previous_status = document["operation_status"]
            previous_started_at = document["operation_started_at"]
            cursor.execute(
                """
                UPDATE document
                SET
                    operation_status = NULL,
                    operation_lock_id = NULL,
                    operation_started_at = NULL,
                    updated_at = now()
                WHERE id = %s
                  AND tenant_id = %s
                  AND operation_lock_id = %s
                """,
                (document_id, tenant_id, lock_id),
            )
            cursor.execute(
                """
                INSERT INTO document_audit_event (
                    id,
                    tenant_id,
                    document_id,
                    job_id,
                    operation,
                    actor_id,
                    request_source,
                    metadata
                )
                VALUES (%s, %s, %s, %s, 'DOCUMENT_OPERATION_LOCK_RELEASED', %s, %s, %s)
                """,
                (
                    str(uuid4()),
                    tenant_id,
                    document_id,
                    lock_id,
                    actor_id,
                    request_source,
                    Jsonb(
                        {
                            "previous_operation_status": previous_status,
                            "previous_operation_lock_id": lock_id,
                            "previous_operation_started_at": (
                                previous_started_at.isoformat() if previous_started_at is not None else None
                            ),
                            "stale_lock_minutes": stale_lock_minutes,
                        }
                    ),
                ),
            )
    return {
        "document_id": document_id,
        "tenant_id": tenant_id,
        "released": True,
        "previous_operation_status": previous_status,
        "previous_operation_lock_id": lock_id,
        "stale_lock_minutes": stale_lock_minutes,
    }


def list_document_audit_events(
    *,
    document_id: str,
    tenant_id: str,
    limit: int,
    operation: str | None = None,
) -> dict[str, object]:
    bounded_limit = max(1, min(limit, 200))
    if not _document_exists(document_id=document_id, tenant_id=tenant_id):
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", status_code=404)
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            if operation:
                cursor.execute(
                    """
                    SELECT
                        id,
                        tenant_id,
                        document_id,
                        document_version_id,
                        job_id,
                        operation,
                        actor_id,
                        request_source,
                        metadata,
                        created_at
                    FROM document_audit_event
                    WHERE document_id = %s
                      AND tenant_id = %s
                      AND operation = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (document_id, tenant_id, operation, bounded_limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        id,
                        tenant_id,
                        document_id,
                        document_version_id,
                        job_id,
                        operation,
                        actor_id,
                        request_source,
                        metadata,
                        created_at
                    FROM document_audit_event
                    WHERE document_id = %s
                      AND tenant_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (document_id, tenant_id, bounded_limit),
                )
            rows = cursor.fetchall()
    return {
        "document_id": document_id,
        "tenant_id": tenant_id,
        "items": [_format_audit_event(row) for row in rows],
    }


def _insert_audit_event(
    *,
    tenant_id: str,
    document_id: str,
    document_version_id: str | None,
    job_id: str | None,
    operation: str,
    actor_id: str,
    request_source: str,
    metadata: dict[str, object],
) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO document_audit_event (
                    id,
                    tenant_id,
                    document_id,
                    document_version_id,
                    job_id,
                    operation,
                    actor_id,
                    request_source,
                    metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid4()),
                    tenant_id,
                    document_id,
                    document_version_id,
                    job_id,
                    operation,
                    actor_id,
                    request_source,
                    Jsonb(metadata),
                ),
            )


def _document_exists(*, document_id: str, tenant_id: str) -> bool:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM document
                WHERE id = %s
                  AND tenant_id = %s
                """,
                (document_id, tenant_id),
            )
            row = cursor.fetchone()
    return row is not None


def _acquire_document_operation_lock(
    *,
    document_id: str,
    tenant_id: str,
    operation_status: str,
    lock_id: str,
    actor_id: str,
    request_source: str,
) -> dict[str, object]:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE document
                SET
                    operation_status = %s,
                    operation_lock_id = %s,
                    operation_started_at = now(),
                    updated_at = now()
                WHERE id = %s
                  AND tenant_id = %s
                  AND status <> 'DELETED'
                  AND operation_status IS NULL
                RETURNING id, tenant_id, knowledge_base_id, permission_tags, status
                """,
                (operation_status, lock_id, document_id, tenant_id),
            )
            document = cursor.fetchone()
            if document is not None:
                cursor.execute(
                    """
                    SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version_no
                    FROM document_version
                    WHERE document_id = %s
                    """,
                    (document_id,),
                )
                next_version_no = cursor.fetchone()["next_version_no"]
                result = dict(document)
                result["next_version_no"] = next_version_no
                cursor.execute(
                    """
                    INSERT INTO document_audit_event (
                        id, tenant_id, document_id, operation, actor_id, request_source, metadata
                    )
                    VALUES (%s, %s, %s, 'DOCUMENT_OPERATION_LOCKED', %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        tenant_id,
                        document_id,
                        actor_id,
                        request_source,
                        Jsonb({"operation_status": operation_status, "operation_lock_id": lock_id}),
                    ),
                )
                return result
    _raise_document_lock_error(
        document_id=document_id,
        tenant_id=tenant_id,
        attempted_operation=operation_status,
        actor_id=actor_id,
        request_source=request_source,
    )


def _acquire_delete_operation_lock(
    *,
    document_id: str,
    tenant_id: str,
    lock_id: str,
    actor_id: str,
    request_source: str,
) -> bool:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE document
                SET
                    operation_status = 'DELETE_DOCUMENT',
                    operation_lock_id = %s,
                    operation_started_at = now(),
                    updated_at = now()
                WHERE id = %s
                  AND tenant_id = %s
                  AND status <> 'DELETED'
                  AND operation_status IS NULL
                RETURNING id
                """,
                (lock_id, document_id, tenant_id),
            )
            locked = cursor.fetchone()
            if locked is not None:
                cursor.execute(
                    """
                    INSERT INTO document_audit_event (
                        id, tenant_id, document_id, operation, actor_id, request_source, metadata
                    )
                    VALUES (%s, %s, %s, 'DOCUMENT_OPERATION_LOCKED', %s, %s, %s)
                    """,
                    (
                        str(uuid4()),
                        tenant_id,
                        document_id,
                        actor_id,
                        request_source,
                        Jsonb({"operation_status": "DELETE_DOCUMENT", "operation_lock_id": lock_id}),
                    ),
                )
                return True
    status = _load_document_operation_state(document_id=document_id, tenant_id=tenant_id)
    if status is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", status_code=404)
    if status["status"] == "DELETED":
        return False
    _raise_document_lock_error(
        document_id=document_id,
        tenant_id=tenant_id,
        attempted_operation="DELETE_DOCUMENT",
        actor_id=actor_id,
        request_source=request_source,
    )


def _raise_document_lock_error(
    *,
    document_id: str,
    tenant_id: str,
    attempted_operation: str,
    actor_id: str,
    request_source: str,
) -> None:
    state = _load_document_operation_state(document_id=document_id, tenant_id=tenant_id)
    if state is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", status_code=404)
    if state["status"] == "DELETED":
        raise AppError("DOCUMENT_DELETED", "Document is deleted", status_code=409)
    if state["operation_status"] is not None:
        _insert_audit_event(
            tenant_id=tenant_id,
            document_id=document_id,
            document_version_id=None,
            job_id=None,
            operation="DOCUMENT_OPERATION_REJECTED",
            actor_id=actor_id,
            request_source=request_source,
            metadata={
                "attempted_operation": attempted_operation,
                "current_operation_status": state["operation_status"],
                "current_operation_lock_id": str(state["operation_lock_id"]),
                "current_operation_started_at": (
                    state["operation_started_at"].isoformat()
                    if state["operation_started_at"] is not None
                    else None
                ),
            },
        )
        raise AppError("DOCUMENT_OPERATION_IN_PROGRESS", "Document operation is in progress", status_code=409)
    raise AppError("DOCUMENT_OPERATION_IN_PROGRESS", "Document operation is in progress", status_code=409)


def _load_document_operation_state(*, document_id: str, tenant_id: str) -> dict[str, object] | None:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, operation_status, operation_lock_id, operation_started_at
                FROM document
                WHERE id = %s AND tenant_id = %s
                """,
                (document_id, tenant_id),
            )
            row = cursor.fetchone()
    return dict(row) if row else None


def _release_document_operation_lock(*, document_id: str, tenant_id: str, lock_id: str) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE document
                SET
                    operation_status = NULL,
                    operation_lock_id = NULL,
                    operation_started_at = NULL,
                    updated_at = now()
                WHERE id = %s
                  AND tenant_id = %s
                  AND operation_lock_id = %s
                """,
                (document_id, tenant_id, lock_id),
            )


def _format_audit_event(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": str(row["id"]),
        "tenant_id": row["tenant_id"],
        "document_id": str(row["document_id"]),
        "document_version_id": (
            str(row["document_version_id"]) if row["document_version_id"] is not None else None
        ),
        "job_id": str(row["job_id"]) if row["job_id"] is not None else None,
        "operation": row["operation"],
        "actor_id": row["actor_id"],
        "request_source": row["request_source"],
        "metadata": row["metadata"],
        "created_at": row["created_at"].isoformat(),
    }


def _load_document_for_update(*, document_id: str, tenant_id: str) -> dict[str, object] | None:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    d.id,
                    d.tenant_id,
                    d.knowledge_base_id,
                    d.permission_tags,
                    d.status,
                    COALESCE(MAX(dv.version_no), 0) + 1 AS next_version_no
                FROM document AS d
                LEFT JOIN document_version AS dv ON dv.document_id = d.id
                WHERE d.id = %s AND d.tenant_id = %s
                GROUP BY d.id
                """,
                (document_id, tenant_id),
            )
            row = cursor.fetchone()
    return dict(row) if row else None


def _load_indexed_document_version(*, document_id: str, tenant_id: str) -> dict[str, object] | None:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    d.id,
                    d.tenant_id,
                    d.knowledge_base_id,
                    d.permission_tags,
                    d.title,
                    d.status,
                    dv.id AS version_id,
                    dv.version_no,
                    dv.object_key
                FROM document AS d
                JOIN document_version AS dv ON dv.document_id = d.id
                WHERE d.id = %s
                  AND d.tenant_id = %s
                  AND d.status <> 'DELETED'
                  AND dv.status = 'INDEXED'
                ORDER BY dv.version_no DESC
                LIMIT 1
                """,
                (document_id, tenant_id),
            )
            row = cursor.fetchone()
    return dict(row) if row else None


def _put_object(object_key: str, payload: bytes, content_type: str | None) -> None:
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


def _create_version_records(
    *,
    tenant_id: str,
    document_id: str,
    version_id: str,
    version_no: int,
    job_id: str,
    object_key: str,
    checksum: str,
) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO document_version (
                    id, document_id, version_no, object_key, checksum, status
                )
                VALUES (%s, %s, %s, %s, %s, 'UPLOADED')
                """,
                (version_id, document_id, version_no, object_key, checksum),
            )
            cursor.execute(
                """
                INSERT INTO cleaning_job (id, document_version_id, tenant_id, status)
                VALUES (%s, %s, %s, 'PENDING')
                """,
                (job_id, version_id, tenant_id),
            )


def _create_rebuild_job(*, job_id: str, tenant_id: str, version_id: str) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cleaning_job (id, document_version_id, tenant_id, status)
                VALUES (%s, %s, %s, 'PENDING')
                """,
                (job_id, version_id, tenant_id),
            )


def _load_document_chunk_ids(*, document_id: str, tenant_id: str) -> list[str] | None:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, status
                FROM document
                WHERE id = %s AND tenant_id = %s
                """,
                (document_id, tenant_id),
            )
            document = cursor.fetchone()
            if document is None:
                return None
            cursor.execute(
                """
                SELECT tc.id
                FROM text_chunk AS tc
                JOIN document_version AS dv ON dv.id = tc.document_version_id
                WHERE dv.document_id = %s
                  AND tc.tenant_id = %s
                """,
                (document_id, tenant_id),
            )
            rows = cursor.fetchall()
    return [str(row["id"]) for row in rows]


def _delete_qdrant_points(chunk_ids: list[str]) -> int:
    if not chunk_ids:
        return 0
    client = build_qdrant_client()
    client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=models.PointIdsList(points=chunk_ids),
        wait=True,
    )
    return len(chunk_ids)


def _mark_document_deleted(*, document_id: str, tenant_id: str, lock_id: str | None) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            if lock_id is None:
                cursor.execute(
                    """
                    UPDATE document
                    SET status = 'DELETED', deleted_at = now(), updated_at = now()
                    WHERE id = %s AND tenant_id = %s
                    """,
                    (document_id, tenant_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE document
                    SET
                        status = 'DELETED',
                        deleted_at = now(),
                        operation_status = NULL,
                        operation_lock_id = NULL,
                        operation_started_at = NULL,
                        updated_at = now()
                    WHERE id = %s
                      AND tenant_id = %s
                      AND operation_lock_id = %s
                    """,
                    (document_id, tenant_id, lock_id),
                )
            cursor.execute(
                """
                UPDATE document_version
                SET status = 'DELETED', deleted_at = now()
                WHERE document_id = %s
                """,
                (document_id,),
            )
            cursor.execute(
                """
                DELETE FROM vector_record
                WHERE chunk_id IN (
                    SELECT tc.id
                    FROM text_chunk AS tc
                    JOIN document_version AS dv ON dv.id = tc.document_version_id
                    WHERE dv.document_id = %s
                      AND tc.tenant_id = %s
                )
                """,
                (document_id, tenant_id),
            )
