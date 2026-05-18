from __future__ import annotations

from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.errors import AppError
from app.db.session import build_psycopg_url
from app.services.document_service import rebuild_document_index


def create_rebuild_batch(
    *,
    tenant_id: str,
    knowledge_base_id: str | None,
    source_id: str | None,
    document_ids: list[str] | None,
    actor_id: str,
    request_source: str,
    limit: int,
    trace_id: str | None = None,
) -> dict[str, object]:
    if not knowledge_base_id and not source_id and not document_ids:
        raise AppError(
            "BATCH_FILTER_REQUIRED",
            "At least one of knowledge_base_id, source_id, or document_ids is required",
            status_code=400,
        )

    bounded_limit = max(1, min(limit, 500))
    documents = _select_rebuild_candidates(
        tenant_id=tenant_id,
        knowledge_base_id=knowledge_base_id,
        source_id=source_id,
        document_ids=document_ids,
        limit=bounded_limit,
    )
    if not documents:
        raise AppError("BATCH_NO_DOCUMENTS", "No indexed documents matched the batch filter", status_code=404)

    batch_id = str(uuid4())
    filters = {
        "knowledge_base_id": knowledge_base_id,
        "source_id": source_id,
        "document_ids": document_ids,
        "limit": bounded_limit,
    }
    _create_batch_record(
        batch_id=batch_id,
        tenant_id=tenant_id,
        operation="REBUILD_INDEX",
        filters=filters,
        total_count=len(documents),
        actor_id=actor_id,
        request_source=request_source,
    )

    for document in documents:
        item_id = str(uuid4())
        document_id = str(document["document_id"])
        version_id = str(document["document_version_id"])
        _create_batch_item(
            item_id=item_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            document_id=document_id,
            document_version_id=version_id,
        )
        try:
            rebuild = rebuild_document_index(
                document_id=document_id,
                tenant_id=tenant_id,
                actor_id=actor_id,
                request_source=request_source,
                trace_id=trace_id,
            )
            _mark_item_running(
                item_id=item_id,
                job_id=str(rebuild["job_id"]),
                document_version_id=str(rebuild["document_version_id"]),
            )
            _insert_batch_audit_event(
                tenant_id=tenant_id,
                document_id=document_id,
                document_version_id=str(rebuild["document_version_id"]),
                job_id=str(rebuild["job_id"]),
                batch_id=batch_id,
                operation="BATCH_REBUILD_ITEM_SUBMITTED",
                actor_id=actor_id,
                request_source=request_source,
            )
        except AppError as exc:
            status = "SKIPPED" if exc.code in _SKIPPABLE_ERROR_CODES else "FAILED"
            _mark_item_terminal(
                item_id=item_id,
                status=status,
                error_code=exc.code,
                error_message=exc.message,
            )
        except Exception as exc:
            _mark_item_terminal(
                item_id=item_id,
                status="FAILED",
                error_code="INTERNAL_ERROR",
                error_message=str(exc),
            )

    return get_document_batch(batch_id=batch_id, tenant_id=tenant_id)


def get_document_batch(*, batch_id: str, tenant_id: str) -> dict[str, object]:
    batch = _load_batch(batch_id=batch_id, tenant_id=tenant_id)
    if batch is None:
        raise AppError("BATCH_NOT_FOUND", "Document batch not found", status_code=404)
    items = _load_batch_items(batch_id=batch_id, tenant_id=tenant_id, limit=1000, offset=0)
    summary = _summarize_items(items)
    status = _derive_batch_status(summary)
    _update_batch_summary(batch_id=batch_id, tenant_id=tenant_id, status=status, summary=summary)
    return {
        "batch_id": str(batch["id"]),
        "tenant_id": batch["tenant_id"],
        "operation": batch["operation"],
        "status": status,
        "filters": batch["filters"],
        "summary": summary,
        "actor_id": batch["actor_id"],
        "request_source": batch["request_source"],
        "created_at": batch["created_at"].isoformat(),
        "updated_at": batch["updated_at"].isoformat(),
    }


def retry_failed_batch_items(
    *,
    batch_id: str,
    tenant_id: str,
    actor_id: str,
    request_source: str,
    trace_id: str | None = None,
) -> dict[str, object]:
    batch = _load_batch(batch_id=batch_id, tenant_id=tenant_id)
    if batch is None:
        raise AppError("BATCH_NOT_FOUND", "Document batch not found", status_code=404)
    if batch["operation"] != "REBUILD_INDEX":
        raise AppError("BATCH_OPERATION_UNSUPPORTED", "Batch operation is not supported for retry", status_code=409)

    failed_items = _load_retryable_failed_items(batch_id=batch_id, tenant_id=tenant_id)
    if not failed_items:
        raise AppError("BATCH_NO_FAILED_ITEMS", "No failed batch items can be retried", status_code=404)

    retried_count = 0
    for item in failed_items:
        item_id = str(item["id"])
        document_id = str(item["document_id"])
        try:
            rebuild = rebuild_document_index(
                document_id=document_id,
                tenant_id=tenant_id,
                actor_id=actor_id,
                request_source=request_source,
                trace_id=trace_id,
            )
            _mark_item_running(
                item_id=item_id,
                job_id=str(rebuild["job_id"]),
                document_version_id=str(rebuild["document_version_id"]),
            )
            _clear_item_error(item_id=item_id)
            _insert_batch_audit_event(
                tenant_id=tenant_id,
                document_id=document_id,
                document_version_id=str(rebuild["document_version_id"]),
                job_id=str(rebuild["job_id"]),
                batch_id=batch_id,
                operation="BATCH_REBUILD_ITEM_RETRIED",
                actor_id=actor_id,
                request_source=request_source,
            )
            retried_count += 1
        except AppError as exc:
            status = "SKIPPED" if exc.code in _SKIPPABLE_ERROR_CODES else "FAILED"
            _mark_item_terminal(
                item_id=item_id,
                status=status,
                error_code=exc.code,
                error_message=exc.message,
            )
        except Exception as exc:
            _mark_item_terminal(
                item_id=item_id,
                status="FAILED",
                error_code="INTERNAL_ERROR",
                error_message=str(exc),
            )

    result = get_document_batch(batch_id=batch_id, tenant_id=tenant_id)
    result["retried_count"] = retried_count
    return result


def cancel_document_batch(
    *,
    batch_id: str,
    tenant_id: str,
    actor_id: str,
    request_source: str,
) -> dict[str, object]:
    batch = _load_batch(batch_id=batch_id, tenant_id=tenant_id)
    if batch is None:
        raise AppError("BATCH_NOT_FOUND", "Document batch not found", status_code=404)
    canceled_items = _cancel_pending_items(batch_id=batch_id, tenant_id=tenant_id)
    _mark_batch_canceled(
        batch_id=batch_id,
        tenant_id=tenant_id,
        canceled_items=canceled_items,
        actor_id=actor_id,
        request_source=request_source,
    )
    result = get_document_batch(batch_id=batch_id, tenant_id=tenant_id)
    result["canceled_items"] = canceled_items
    return result


def list_document_batch_items(
    *,
    batch_id: str,
    tenant_id: str,
    status: str | None,
    limit: int,
    offset: int,
) -> dict[str, object]:
    if _load_batch(batch_id=batch_id, tenant_id=tenant_id) is None:
        raise AppError("BATCH_NOT_FOUND", "Document batch not found", status_code=404)
    bounded_limit = max(1, min(limit, 200))
    bounded_offset = max(0, offset)
    rows = _load_batch_items(
        batch_id=batch_id,
        tenant_id=tenant_id,
        status=status,
        limit=bounded_limit,
        offset=bounded_offset,
    )
    total_count = _count_batch_items(batch_id=batch_id, tenant_id=tenant_id, status=status)
    return {
        "batch_id": batch_id,
        "tenant_id": tenant_id,
        "status": status,
        "total_count": total_count,
        "limit": bounded_limit,
        "offset": bounded_offset,
        "items": [_format_item(row) for row in rows],
    }


_SKIPPABLE_ERROR_CODES = {
    "DOCUMENT_OPERATION_IN_PROGRESS",
    "DOCUMENT_DELETED",
    "DOCUMENT_VERSION_NOT_INDEXED",
}


def _select_rebuild_candidates(
    *,
    tenant_id: str,
    knowledge_base_id: str | None,
    source_id: str | None,
    document_ids: list[str] | None,
    limit: int,
) -> list[dict[str, object]]:
    conditions = ["d.tenant_id = %s", "d.status <> 'DELETED'", "dv.status = 'INDEXED'"]
    params: list[object] = [tenant_id]
    if knowledge_base_id:
        conditions.append("d.knowledge_base_id = %s")
        params.append(knowledge_base_id)
    if source_id:
        conditions.append("d.data_source_id = %s")
        params.append(source_id)
    if document_ids:
        conditions.append("d.id = ANY(%s::uuid[])")
        params.append(document_ids)
    params.append(limit)
    query = f"""
        SELECT DISTINCT ON (d.id)
            d.id AS document_id,
            dv.id AS document_version_id,
            dv.version_no
        FROM document AS d
        JOIN document_version AS dv ON dv.document_id = d.id
        WHERE {' AND '.join(conditions)}
        ORDER BY d.id, dv.version_no DESC
        LIMIT %s
    """
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


def _create_batch_record(
    *,
    batch_id: str,
    tenant_id: str,
    operation: str,
    filters: dict[str, object],
    total_count: int,
    actor_id: str,
    request_source: str,
) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO document_operation_batch (
                    id,
                    tenant_id,
                    operation,
                    status,
                    filters,
                    total_count,
                    actor_id,
                    request_source
                )
                VALUES (%s, %s, %s, 'RUNNING', %s, %s, %s, %s)
                """,
                (
                    batch_id,
                    tenant_id,
                    operation,
                    Jsonb(filters),
                    total_count,
                    actor_id,
                    request_source,
                ),
            )


def _create_batch_item(
    *,
    item_id: str,
    batch_id: str,
    tenant_id: str,
    document_id: str,
    document_version_id: str,
) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO document_operation_batch_item (
                    id,
                    batch_id,
                    tenant_id,
                    document_id,
                    document_version_id,
                    status
                )
                VALUES (%s, %s, %s, %s, %s, 'PENDING')
                """,
                (item_id, batch_id, tenant_id, document_id, document_version_id),
            )


def _mark_item_running(*, item_id: str, job_id: str, document_version_id: str) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE document_operation_batch_item
                SET
                    document_version_id = %s,
                    job_id = %s,
                    status = 'RUNNING',
                    updated_at = now()
                WHERE id = %s
                """,
                (document_version_id, job_id, item_id),
            )


def _mark_item_terminal(
    *,
    item_id: str,
    status: str,
    error_code: str,
    error_message: str,
) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE document_operation_batch_item
                SET
                    status = %s,
                    error_code = %s,
                    error_message = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (status, error_code, error_message, item_id),
            )


def _load_batch(*, batch_id: str, tenant_id: str) -> dict[str, object] | None:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    tenant_id,
                    operation,
                    status,
                    filters,
                    actor_id,
                    request_source,
                    created_at,
                    updated_at
                FROM document_operation_batch
                WHERE id = %s
                  AND tenant_id = %s
                """,
                (batch_id, tenant_id),
            )
            row = cursor.fetchone()
    return dict(row) if row else None


def _load_batch_items(
    *,
    batch_id: str,
    tenant_id: str,
    status: str | None = None,
    limit: int,
    offset: int,
) -> list[dict[str, object]]:
    status_filter = ""
    params: list[object] = [batch_id, tenant_id]
    if status:
        status_filter = "AND i.status = %s"
        params.append(status)
    params.extend([limit, offset])
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    i.id,
                    i.batch_id,
                    i.tenant_id,
                    i.document_id,
                    i.document_version_id,
                    i.job_id,
                    i.status,
                    i.error_code,
                    i.error_message,
                    i.created_at,
                    i.updated_at,
                    j.status AS job_status
                FROM document_operation_batch_item AS i
                LEFT JOIN cleaning_job AS j ON j.id = i.job_id
                WHERE i.batch_id = %s
                  AND i.tenant_id = %s
                  {status_filter}
                ORDER BY i.created_at ASC
                LIMIT %s OFFSET %s
                """,
                params,
            )
            return [dict(row) for row in cursor.fetchall()]


def _count_batch_items(*, batch_id: str, tenant_id: str, status: str | None = None) -> int:
    status_filter = ""
    params: list[object] = [batch_id, tenant_id]
    if status:
        status_filter = "AND status = %s"
        params.append(status)
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT count(*) AS count
                FROM document_operation_batch_item
                WHERE batch_id = %s
                  AND tenant_id = %s
                  {status_filter}
                """,
                params,
            )
            row = cursor.fetchone()
    return int(row["count"] or 0)


def _load_retryable_failed_items(*, batch_id: str, tenant_id: str) -> list[dict[str, object]]:
    rows = _load_batch_items(batch_id=batch_id, tenant_id=tenant_id, limit=1000, offset=0)
    return [row for row in rows if _derive_item_status(row) == "FAILED"]


def _clear_item_error(*, item_id: str) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE document_operation_batch_item
                SET error_code = NULL,
                    error_message = NULL,
                    updated_at = now()
                WHERE id = %s
                """,
                (item_id,),
            )


def _cancel_pending_items(*, batch_id: str, tenant_id: str) -> int:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE document_operation_batch_item
                SET status = 'CANCELED',
                    error_code = 'BATCH_CANCELED',
                    error_message = 'Batch was canceled before item submission',
                    updated_at = now()
                WHERE batch_id = %s
                  AND tenant_id = %s
                  AND status = 'PENDING'
                RETURNING id
                """,
                (batch_id, tenant_id),
            )
            rows = cursor.fetchall()
    return len(rows)


def _mark_batch_canceled(
    *,
    batch_id: str,
    tenant_id: str,
    canceled_items: int,
    actor_id: str,
    request_source: str,
) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE document_operation_batch
                SET status = 'CANCELED',
                    updated_at = now()
                WHERE id = %s
                  AND tenant_id = %s
                """,
                (batch_id, tenant_id),
            )
            cursor.execute(
                """
                INSERT INTO document_audit_event (
                    id,
                    tenant_id,
                    document_id,
                    operation,
                    actor_id,
                    request_source,
                    metadata
                )
                SELECT
                    %s,
                    tenant_id,
                    document_id,
                    'BATCH_CANCELED',
                    %s,
                    %s,
                    %s
                FROM document_operation_batch_item
                WHERE batch_id = %s
                  AND tenant_id = %s
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (
                    str(uuid4()),
                    actor_id,
                    request_source,
                    Jsonb({"batch_id": batch_id, "canceled_items": canceled_items}),
                    batch_id,
                    tenant_id,
                ),
            )


def _insert_batch_audit_event(
    *,
    tenant_id: str,
    document_id: str,
    document_version_id: str,
    job_id: str,
    batch_id: str,
    operation: str,
    actor_id: str,
    request_source: str,
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
                    Jsonb({"batch_id": batch_id, "batch_operation": "REBUILD_INDEX"}),
                ),
            )


def _format_item(row: dict[str, object]) -> dict[str, object]:
    return {
        "item_id": str(row["id"]),
        "batch_id": str(row["batch_id"]),
        "tenant_id": row["tenant_id"],
        "document_id": str(row["document_id"]),
        "document_version_id": (
            str(row["document_version_id"]) if row["document_version_id"] is not None else None
        ),
        "job_id": str(row["job_id"]) if row["job_id"] is not None else None,
        "status": _derive_item_status(row),
        "stored_status": row["status"],
        "job_status": row["job_status"],
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def _derive_item_status(row: dict[str, object]) -> str:
    if row["status"] != "RUNNING":
        return str(row["status"])
    job_status = row["job_status"]
    if job_status == "SUCCEEDED":
        return "SUCCEEDED"
    if job_status == "FAILED":
        return "FAILED"
    return "RUNNING"


def _summarize_items(rows: list[dict[str, object]]) -> dict[str, int]:
    summary = {
        "total_count": len(rows),
        "pending_count": 0,
        "running_count": 0,
        "succeeded_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "canceled_count": 0,
    }
    for row in rows:
        status = _derive_item_status(row)
        if status == "PENDING":
            summary["pending_count"] += 1
        elif status == "RUNNING":
            summary["running_count"] += 1
        elif status == "SUCCEEDED":
            summary["succeeded_count"] += 1
        elif status == "SKIPPED":
            summary["skipped_count"] += 1
        elif status == "FAILED":
            summary["failed_count"] += 1
        elif status == "CANCELED":
            summary["canceled_count"] += 1
    return summary


def _derive_batch_status(summary: dict[str, int]) -> str:
    if summary["running_count"] or summary["pending_count"]:
        return "RUNNING"
    if summary["canceled_count"] and not summary["failed_count"]:
        return "CANCELED" if summary["canceled_count"] == summary["total_count"] else "PARTIAL_SUCCEEDED"
    if summary["total_count"] == summary["succeeded_count"]:
        return "SUCCEEDED"
    if summary["succeeded_count"] > 0:
        return "PARTIAL_SUCCEEDED"
    if summary["skipped_count"] == summary["total_count"]:
        return "FAILED"
    return "FAILED"


def _update_batch_summary(
    *,
    batch_id: str,
    tenant_id: str,
    status: str,
    summary: dict[str, int],
) -> None:
    with psycopg.connect(build_psycopg_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE document_operation_batch
                SET
                    status = %s,
                    submitted_count = %s,
                    succeeded_count = %s,
                    failed_count = %s,
                    skipped_count = %s,
                    updated_at = now()
                WHERE id = %s
                  AND tenant_id = %s
                """,
                (
                    status,
                    summary["running_count"] + summary["succeeded_count"] + summary["failed_count"],
                    summary["succeeded_count"],
                    summary["failed_count"],
                    summary["skipped_count"] + summary["canceled_count"],
                    batch_id,
                    tenant_id,
                ),
            )
