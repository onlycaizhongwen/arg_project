from __future__ import annotations

from datetime import UTC, datetime

import pika
import psycopg
from psycopg.rows import dict_row

from app.core.config import settings
from app.db.session import build_psycopg_url


def get_diagnostics_overview(
    *,
    tenant_id: str = "default",
    window_minutes: int = 60,
    stale_lock_minutes: int = 30,
) -> dict[str, object]:
    window_minutes = max(1, window_minutes)
    stale_lock_minutes = max(1, stale_lock_minutes)
    job_metrics = _load_job_metrics(tenant_id=tenant_id, window_minutes=window_minutes)
    lock_metrics = _load_lock_metrics(tenant_id=tenant_id, stale_lock_minutes=stale_lock_minutes)
    rerank_metrics = _load_rerank_metrics(tenant_id=tenant_id, window_minutes=window_minutes)
    queue_metrics = _load_queue_metrics()
    signals = _build_signals(
        job_metrics=job_metrics,
        lock_metrics=lock_metrics,
        rerank_metrics=rerank_metrics,
        queue_metrics=queue_metrics,
    )
    return {
        "status": _overall_status(signals),
        "generated_at": datetime.now(UTC).isoformat(),
        "tenant_id": tenant_id,
        "window_minutes": window_minutes,
        "stale_lock_minutes": stale_lock_minutes,
        "job_metrics": job_metrics,
        "queue_metrics": queue_metrics,
        "lock_metrics": lock_metrics,
        "rerank_metrics": rerank_metrics,
        "signals": signals,
    }


def _load_job_metrics(*, tenant_id: str, window_minutes: int) -> dict[str, object]:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, count(*) AS count
                FROM cleaning_job
                WHERE tenant_id = %s
                GROUP BY status
                """,
                (tenant_id,),
            )
            by_status = {row["status"]: int(row["count"]) for row in cursor.fetchall()}
            cursor.execute(
                """
                SELECT
                    count(*) AS total_count,
                    count(*) FILTER (WHERE status = 'FAILED') AS failed_count
                FROM cleaning_job
                WHERE tenant_id = %s
                  AND created_at >= now() - (%s::text || ' minutes')::interval
                """,
                (tenant_id, window_minutes),
            )
            recent = cursor.fetchone()
    total_recent = int(recent["total_count"] or 0)
    failed_recent = int(recent["failed_count"] or 0)
    failure_rate = failed_recent / total_recent if total_recent else 0.0
    return {
        "by_status": by_status,
        "pending_count": by_status.get("PENDING", 0),
        "running_count": by_status.get("RUNNING", 0),
        "retrying_count": by_status.get("RETRYING", 0),
        "failed_count": by_status.get("FAILED", 0),
        "total_recent_count": total_recent,
        "failed_recent_count": failed_recent,
        "failure_rate": round(failure_rate, 4),
    }


def _load_lock_metrics(*, tenant_id: str, stale_lock_minutes: int) -> dict[str, object]:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    operation_status,
                    operation_lock_id,
                    operation_started_at,
                    title
                FROM document
                WHERE tenant_id = %s
                  AND operation_status IS NOT NULL
                ORDER BY operation_started_at ASC
                LIMIT 20
                """,
                (tenant_id,),
            )
            active_rows = cursor.fetchall()
            cursor.execute(
                """
                SELECT
                    id,
                    operation_status,
                    operation_lock_id,
                    operation_started_at,
                    title
                FROM document
                WHERE tenant_id = %s
                  AND operation_status IS NOT NULL
                  AND operation_started_at < now() - (%s::text || ' minutes')::interval
                ORDER BY operation_started_at ASC
                LIMIT 20
                """,
                (tenant_id, stale_lock_minutes),
            )
            stale_rows = cursor.fetchall()
    return {
        "active_count": len(active_rows),
        "stale_count": len(stale_rows),
        "active_items": [_format_lock_row(row) for row in active_rows],
        "stale_items": [_format_lock_row(row) for row in stale_rows],
    }


def _load_rerank_metrics(*, tenant_id: str, window_minutes: int) -> dict[str, object]:
    with psycopg.connect(build_psycopg_url(), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*) AS degraded_count
                FROM search_diagnostic_event
                WHERE tenant_id = %s
                  AND event_type = 'RERANK_DEGRADED'
                  AND created_at >= now() - (%s::text || ' minutes')::interval
                """,
                (tenant_id, window_minutes),
            )
            row = cursor.fetchone()
    return {
        "provider": settings.rerank_provider,
        "model": settings.rerank_model,
        "enabled_by_config": settings.rerank_provider != "disabled",
        "degraded_recent_count": int(row["degraded_count"] or 0),
    }


def _load_queue_metrics() -> dict[str, object]:
    try:
        credentials = pika.PlainCredentials(settings.rabbitmq_user, settings.rabbitmq_password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=settings.rabbitmq_host,
                port=settings.rabbitmq_port,
                credentials=credentials,
                blocked_connection_timeout=3,
                socket_timeout=3,
            )
        )
        try:
            channel = connection.channel()
            result = channel.queue_declare(queue=settings.rabbitmq_queue, durable=True, passive=True)
            return {
                "available": True,
                "queue": settings.rabbitmq_queue,
                "ready_count": int(result.method.message_count),
                "consumer_count": int(result.method.consumer_count),
                "error": None,
            }
        finally:
            connection.close()
    except Exception as exc:
        return {
            "available": False,
            "queue": settings.rabbitmq_queue,
            "ready_count": None,
            "consumer_count": None,
            "error": str(exc),
        }


def _build_signals(
    *,
    job_metrics: dict[str, object],
    lock_metrics: dict[str, object],
    rerank_metrics: dict[str, object],
    queue_metrics: dict[str, object],
) -> list[dict[str, object]]:
    signals: list[dict[str, object]] = []
    if not queue_metrics["available"]:
        signals.append(_signal("QUEUE_UNAVAILABLE", "critical", "RabbitMQ queue status cannot be read"))
    elif int(queue_metrics["consumer_count"] or 0) == 0:
        signals.append(_signal("QUEUE_NO_CONSUMER", "critical", "No Worker consumer is attached"))
    if int(queue_metrics["ready_count"] or 0) > 0:
        signals.append(_signal("JOB_BACKLOG", "warning", "Cleaning queue has waiting messages"))
    if float(job_metrics["failure_rate"]) > 0:
        signals.append(_signal("JOB_FAILURES_RECENT", "warning", "Recent cleaning jobs include failures"))
    if int(lock_metrics["stale_count"]) > 0:
        signals.append(_signal("DOCUMENT_LOCK_STALE", "critical", "Document operation locks exceeded threshold"))
    if int(rerank_metrics["degraded_recent_count"]) > 0:
        signals.append(_signal("RERANK_DEGRADED", "warning", "Recent searches degraded without rerank"))
    return signals


def _signal(code: str, severity: str, message: str) -> dict[str, object]:
    return {"code": code, "severity": severity, "message": message}


def _overall_status(signals: list[dict[str, object]]) -> str:
    severities = {signal["severity"] for signal in signals}
    if "critical" in severities:
        return "critical"
    if "warning" in severities:
        return "warning"
    return "ok"


def _format_lock_row(row: dict[str, object]) -> dict[str, object]:
    operation_started_at = row["operation_started_at"]
    return {
        "document_id": str(row["id"]),
        "title": row["title"],
        "operation_status": row["operation_status"],
        "operation_lock_id": str(row["operation_lock_id"]) if row["operation_lock_id"] else None,
        "operation_started_at": (
            operation_started_at.isoformat()
            if operation_started_at is not None and hasattr(operation_started_at, "isoformat")
            else None
        ),
    }
