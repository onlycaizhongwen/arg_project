from typing import Literal

from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.core.config import settings
from app.core.errors import AppError

router = APIRouter()


class RerankRuntimeConfigRequest(BaseModel):
    provider: Literal["disabled", "mock", "external"]
    model: str = Field(default="mock-reranker", min_length=1)
    base_url: str = ""
    timeout_seconds: float = Field(default=5, gt=0)


class RerankRuntimeConfigResponse(BaseModel):
    provider: str
    model: str
    base_url: str
    timeout_seconds: float


@router.get("/rerank", response_model=RerankRuntimeConfigResponse)
def get_rerank_config() -> RerankRuntimeConfigResponse:
    return _current_rerank_config()


@router.put("/rerank", response_model=RerankRuntimeConfigResponse)
def update_rerank_config(request: RerankRuntimeConfigRequest) -> RerankRuntimeConfigResponse:
    if request.provider == "external" and not request.base_url.strip():
        raise AppError("RERANK_BASE_URL_REQUIRED", "RERANK_BASE_URL is required for external rerank", status_code=400)

    settings.rerank_provider = request.provider
    settings.rerank_model = request.model.strip()
    settings.rerank_base_url = request.base_url.strip()
    settings.rerank_timeout_seconds = request.timeout_seconds
    settings.validate()
    return _current_rerank_config()


def _current_rerank_config() -> RerankRuntimeConfigResponse:
    return RerankRuntimeConfigResponse(
        provider=settings.rerank_provider,
        model=settings.rerank_model,
        base_url=settings.rerank_base_url,
        timeout_seconds=settings.rerank_timeout_seconds,
    )
