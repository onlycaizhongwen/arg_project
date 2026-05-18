from __future__ import annotations

from fastapi import APIRouter, Response

from app.core.api_metrics import get_api_request_metrics
from app.services.diagnostics_service import get_diagnostics_overview

router = APIRouter()


@router.get("")
def metrics(
    tenant_id: str = "default",
    window_minutes: int = 60,
    stale_lock_minutes: int = 30,
) -> Response:
    overview = get_diagnostics_overview(
        tenant_id=tenant_id,
        window_minutes=window_minutes,
        stale_lock_minutes=stale_lock_minutes,
    )
    return Response(
        content=_render_prometheus_metrics(overview),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


def _render_prometheus_metrics(overview: dict[str, object]) -> str:
    tenant_id = str(overview["tenant_id"])
    job_metrics = overview["job_metrics"]
    queue_metrics = overview["queue_metrics"]
    lock_metrics = overview["lock_metrics"]
    rerank_metrics = overview["rerank_metrics"]

    if not isinstance(job_metrics, dict):
        raise TypeError("job_metrics must be a dictionary")
    if not isinstance(queue_metrics, dict):
        raise TypeError("queue_metrics must be a dictionary")
    if not isinstance(lock_metrics, dict):
        raise TypeError("lock_metrics must be a dictionary")
    if not isinstance(rerank_metrics, dict):
        raise TypeError("rerank_metrics must be a dictionary")

    lines: list[str] = [
        "# HELP rag_cleaning_job_status_count Cleaning job count by status.",
        "# TYPE rag_cleaning_job_status_count gauge",
    ]
    by_status = job_metrics.get("by_status", {})
    if isinstance(by_status, dict):
        status_counts = {
            "PENDING": 0,
            "RUNNING": 0,
            "RETRYING": 0,
            "COMPLETED": 0,
            "FAILED": 0,
            **by_status,
        }
        for status, count in sorted(status_counts.items()):
            lines.append(
                _metric_line(
                    "rag_cleaning_job_status_count",
                    int(count or 0),
                    tenant_id=tenant_id,
                    status=str(status),
                )
            )

    lines.extend(
        [
            "# HELP rag_cleaning_job_recent_total Recent cleaning job count.",
            "# TYPE rag_cleaning_job_recent_total gauge",
            _metric_line(
                "rag_cleaning_job_recent_total",
                int(job_metrics.get("total_recent_count") or 0),
                tenant_id=tenant_id,
            ),
            "# HELP rag_cleaning_job_recent_failed Recent failed cleaning job count.",
            "# TYPE rag_cleaning_job_recent_failed gauge",
            _metric_line(
                "rag_cleaning_job_recent_failed",
                int(job_metrics.get("failed_recent_count") or 0),
                tenant_id=tenant_id,
            ),
            "# HELP rag_cleaning_job_failure_rate Recent cleaning job failure rate.",
            "# TYPE rag_cleaning_job_failure_rate gauge",
            _metric_line(
                "rag_cleaning_job_failure_rate",
                float(job_metrics.get("failure_rate") or 0),
                tenant_id=tenant_id,
            ),
            "# HELP rag_cleaning_queue_available Whether RabbitMQ queue status can be read.",
            "# TYPE rag_cleaning_queue_available gauge",
            _metric_line("rag_cleaning_queue_available", 1 if queue_metrics.get("available") else 0),
            "# HELP rag_cleaning_queue_ready_count Ready message count in cleaning queue.",
            "# TYPE rag_cleaning_queue_ready_count gauge",
            _metric_line("rag_cleaning_queue_ready_count", _number_or_zero(queue_metrics.get("ready_count"))),
            "# HELP rag_cleaning_queue_consumer_count Consumer count on cleaning queue.",
            "# TYPE rag_cleaning_queue_consumer_count gauge",
            _metric_line("rag_cleaning_queue_consumer_count", _number_or_zero(queue_metrics.get("consumer_count"))),
            "# HELP rag_cleaning_document_lock_active_count Active document operation lock count.",
            "# TYPE rag_cleaning_document_lock_active_count gauge",
            _metric_line(
                "rag_cleaning_document_lock_active_count",
                int(lock_metrics.get("active_count") or 0),
                tenant_id=tenant_id,
            ),
            "# HELP rag_cleaning_document_lock_stale_count Stale document operation lock count.",
            "# TYPE rag_cleaning_document_lock_stale_count gauge",
            _metric_line(
                "rag_cleaning_document_lock_stale_count",
                int(lock_metrics.get("stale_count") or 0),
                tenant_id=tenant_id,
            ),
            "# HELP rag_cleaning_rerank_degraded_recent_count Recent search requests degraded without rerank.",
            "# TYPE rag_cleaning_rerank_degraded_recent_count gauge",
            _metric_line(
                "rag_cleaning_rerank_degraded_recent_count",
                int(rerank_metrics.get("degraded_recent_count") or 0),
                tenant_id=tenant_id,
                provider=str(rerank_metrics.get("provider") or ""),
                model=str(rerank_metrics.get("model") or ""),
            ),
            "# HELP rag_api_request_total API request count by method, path, and status code.",
            "# TYPE rag_api_request_total counter",
            "# HELP rag_api_request_error_total API 5xx request count by method, path, and status code.",
            "# TYPE rag_api_request_error_total counter",
        ]
    )
    for item in get_api_request_metrics():
        method = str(item["method"])
        path = str(item["path"])
        status_code = str(item["status_code"])
        count = int(item["count"] or 0)
        lines.append(
            _metric_line(
                "rag_api_request_total",
                count,
                method=method,
                path=path,
                status_code=status_code,
            )
        )
        if int(status_code) >= 500:
            lines.append(
                _metric_line(
                    "rag_api_request_error_total",
                    count,
                    method=method,
                    path=path,
                    status_code=status_code,
                )
            )
    return "\n".join(lines) + "\n"


def _metric_line(name: str, value: int | float, **labels: str) -> str:
    if labels:
        label_text = ",".join(f'{key}="{_escape_label_value(label_value)}"' for key, label_value in labels.items())
        return f"{name}{{{label_text}}} {value}"
    return f"{name} {value}"


def _escape_label_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _number_or_zero(value: object) -> int:
    return int(value or 0)
