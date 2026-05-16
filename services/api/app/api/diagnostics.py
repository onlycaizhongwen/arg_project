from fastapi import APIRouter

from app.services.diagnostics_service import get_diagnostics_overview

router = APIRouter()


@router.get("/overview")
def diagnostics_overview(
    tenant_id: str = "default",
    window_minutes: int = 60,
    stale_lock_minutes: int = 30,
) -> dict[str, object]:
    return get_diagnostics_overview(
        tenant_id=tenant_id,
        window_minutes=window_minutes,
        stale_lock_minutes=stale_lock_minutes,
    )
