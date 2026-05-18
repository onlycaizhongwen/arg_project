import json
import time

from fastapi import Request
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api import diagnostics, document_batches, documents, ingestion, jobs, metrics, runtime_config, search
from app.core.config import settings
from app.core.errors import (
    AppError,
    app_error_handler,
    auth_context_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.core.api_metrics import record_api_request
from app.core.request_context import AuthContextError, ensure_trace_id


app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(AuthContextError, auth_context_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.middleware("http")
async def trace_request(request: Request, call_next):
    trace_id = ensure_trace_id(request.headers.get("X-Trace-Id"))
    started_at = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        status_code = response.status_code if response is not None else 500
        record_api_request(method=request.method, path=request.url.path, status_code=status_code)
        print(
            json.dumps(
                {
                    "event": "api_request",
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "elapsed_ms": elapsed_ms,
                },
                ensure_ascii=True,
            ),
            flush=True,
        )
        if response is not None:
            response.headers["X-Trace-Id"] = trace_id


@app.on_event("startup")
def validate_settings() -> None:
    settings.validate()


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


app.include_router(ingestion.router, prefix="/api/v1/ingestions", tags=["ingestion"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(document_batches.router, prefix="/api/v1/document-batches", tags=["document-batches"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(search.router, prefix="/api/v1/rag", tags=["rag"])
app.include_router(diagnostics.router, prefix="/api/v1/diagnostics", tags=["diagnostics"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["metrics"])
app.include_router(runtime_config.router, prefix="/api/v1/runtime-config", tags=["runtime-config"])
