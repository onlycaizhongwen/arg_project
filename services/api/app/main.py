from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api import diagnostics, documents, ingestion, jobs, search
from app.core.config import settings
from app.core.errors import (
    AppError,
    app_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)


app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.on_event("startup")
def validate_settings() -> None:
    settings.validate()


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


app.include_router(ingestion.router, prefix="/api/v1/ingestions", tags=["ingestion"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(search.router, prefix="/api/v1/rag", tags=["rag"])
app.include_router(diagnostics.router, prefix="/api/v1/diagnostics", tags=["diagnostics"])
