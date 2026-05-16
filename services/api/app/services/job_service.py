from __future__ import annotations

from uuid import uuid4

from app.core.errors import AppError
from app.db.session import build_psycopg_url
from app.infra.mq import publish_cleaning_job

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def get_job(job_id: str) -> dict[str, object] | None:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    document_version_id,
                    tenant_id,
                    status,
                    retry_count,
                    retry_of_job_id,
                    error_message,
                    started_at,
                    finished_at,
                    created_at,
                    updated_at
                FROM cleaning_job
                WHERE id = %s
                """,
                (job_id,),
            )
            row = cursor.fetchone()
    if row is None:
        return None
    return {
        "job_id": str(row["id"]),
        "document_version_id": str(row["document_version_id"]),
        "tenant_id": row["tenant_id"],
        "status": row["status"],
        "retry_count": row["retry_count"],
        "retry_of_job_id": str(row["retry_of_job_id"]) if row["retry_of_job_id"] is not None else None,
        "error_message": row["error_message"],
        "started_at": _iso(row["started_at"]),
        "finished_at": _iso(row["finished_at"]),
        "created_at": _iso(row["created_at"]),
        "updated_at": _iso(row["updated_at"]),
    }


def retry_failed_job(
    *,
    job_id: str,
    tenant_id: str = "default",
    actor_id: str = "system",
    request_source: str = "api",
) -> dict[str, object]:
    job = _load_retry_source_job(job_id=job_id, tenant_id=tenant_id)
    if job is None:
        raise AppError("JOB_NOT_FOUND", "Job not found", status_code=404)
    if job["job_status"] != "FAILED":
        raise AppError("JOB_NOT_FAILED", "Only FAILED jobs can be retried", status_code=409)
    if job["document_status"] == "DELETED":
        raise AppError("DOCUMENT_DELETED", "Document is deleted", status_code=409)

    retry_job_id = str(uuid4())
    _acquire_retry_lock(
        document_id=str(job["document_id"]),
        tenant_id=tenant_id,
        lock_id=retry_job_id,
        actor_id=actor_id,
        request_source=request_source,
    )
    try:
        _create_retry_job(
            retry_job_id=retry_job_id,
            retry_of_job_id=job_id,
            document_version_id=str(job["document_version_id"]),
            tenant_id=tenant_id,
        )
        _insert_audit_event(
            tenant_id=tenant_id,
            document_id=str(job["document_id"]),
            document_version_id=str(job["document_version_id"]),
            job_id=retry_job_id,
            operation="JOB_RETRY_REQUESTED",
            actor_id=actor_id,
            request_source=request_source,
            metadata={
                "retry_of_job_id": job_id,
                "source_error_message": job["error_message"],
                "operation_lock_id": retry_job_id,
            },
        )
        publish_cleaning_job(
            {
                "job_id": retry_job_id,
                "tenant_id": tenant_id,
                "knowledge_base_id": job["knowledge_base_id"],
                "permission_tags": job["permission_tags"],
                "document_id": str(job["document_id"]),
                "document_version_id": str(job["document_version_id"]),
                "object_key": job["object_key"],
                "filename": job["title"] or "uploaded-file",
                "rebuild": True,
                "operation": "RETRY_JOB",
            }
        )
    except Exception:
        _release_retry_lock(document_id=str(job["document_id"]), tenant_id=tenant_id, lock_id=retry_job_id)
        raise

    return {
        "job_id": retry_job_id,
        "retry_of_job_id": job_id,
        "document_id": str(job["document_id"]),
        "document_version_id": str(job["document_version_id"]),
        "tenant_id": tenant_id,
        "status": "PENDING",
        "operation": "RETRY_JOB",
    }


def _load_retry_source_job(*, job_id: str, tenant_id: str) -> dict[str, object] | None:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    cj.id AS job_id,
                    cj.status AS job_status,
                    cj.error_message,
                    dv.id AS document_version_id,
                    dv.object_key,
                    d.id AS document_id,
                    d.status AS document_status,
                    d.title,
                    d.knowledge_base_id,
                    d.permission_tags
                FROM cleaning_job AS cj
                JOIN document_version AS dv ON dv.id = cj.document_version_id
                JOIN document AS d ON d.id = dv.document_id
                WHERE cj.id = %s
                  AND cj.tenant_id = %s
                  AND d.tenant_id = %s
                """,
                (job_id, tenant_id, tenant_id),
            )
            row = cursor.fetchone()
    return dict(row) if row else None


def _acquire_retry_lock(
    *,
    document_id: str,
    tenant_id: str,
    lock_id: str,
    actor_id: str,
    request_source: str,
) -> None:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE document
                SET
                    operation_status = 'RETRY_JOB',
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
                        Jsonb({"operation_status": "RETRY_JOB", "operation_lock_id": lock_id}),
                    ),
                )
                return
    state = _load_document_state(document_id=document_id, tenant_id=tenant_id)
    if state is None:
        raise AppError("DOCUMENT_NOT_FOUND", "Document not found", status_code=404)
    if state["status"] == "DELETED":
        raise AppError("DOCUMENT_DELETED", "Document is deleted", status_code=409)
    _insert_audit_event(
        tenant_id=tenant_id,
        document_id=document_id,
        document_version_id=None,
        job_id=None,
        operation="DOCUMENT_OPERATION_REJECTED",
        actor_id=actor_id,
        request_source=request_source,
        metadata={
            "attempted_operation": "RETRY_JOB",
            "current_operation_status": state["operation_status"],
            "current_operation_lock_id": (
                str(state["operation_lock_id"]) if state["operation_lock_id"] is not None else None
            ),
        },
    )
    raise AppError("DOCUMENT_OPERATION_IN_PROGRESS", "Document operation is in progress", status_code=409)


def _load_document_state(*, document_id: str, tenant_id: str) -> dict[str, object] | None:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, operation_status, operation_lock_id
                FROM document
                WHERE id = %s AND tenant_id = %s
                """,
                (document_id, tenant_id),
            )
            row = cursor.fetchone()
    return dict(row) if row else None


def _create_retry_job(
    *,
    retry_job_id: str,
    retry_of_job_id: str,
    document_version_id: str,
    tenant_id: str,
) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cleaning_job (
                    id, document_version_id, tenant_id, status, retry_of_job_id
                )
                VALUES (%s, %s, %s, 'PENDING', %s)
                """,
                (retry_job_id, document_version_id, tenant_id, retry_of_job_id),
            )


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


def _release_retry_lock(*, document_id: str, tenant_id: str, lock_id: str) -> None:
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


def _iso(value: object) -> str | None:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else None
