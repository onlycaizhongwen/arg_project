from fastapi import APIRouter

from app.core.errors import AppError
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
) -> dict[str, object]:
    return retry_failed_job(
        job_id=job_id,
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_source=request_source,
    )
