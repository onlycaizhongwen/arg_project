from fastapi import APIRouter, Depends

from app.core.errors import AppError
from app.core.request_context import (
    RequestContext,
    get_request_context,
    resolve_actor_id,
    resolve_request_source,
    resolve_tenant_id,
)
from app.services.job_service import get_job as get_job_record
from app.services.job_service import retry_failed_job

router = APIRouter()


@router.get("/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    result = get_job_record(job_id)
    if result is None:
        raise AppError("JOB_NOT_FOUND", "Job not found", status_code=404)
    return result


@router.post("/{job_id}/retry")
def retry_job(
    job_id: str,
    tenant_id: str = "default",
    actor_id: str = "system",
    request_source: str = "api",
    context: RequestContext = Depends(get_request_context),
) -> dict[str, object]:
    return retry_failed_job(
        job_id=job_id,
        tenant_id=resolve_tenant_id(tenant_id, context),
        actor_id=resolve_actor_id(actor_id, context),
        request_source=resolve_request_source(request_source, context),
        trace_id=context.trace_id,
    )
