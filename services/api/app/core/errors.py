from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.request_context import AuthContextError, current_trace_id


class AppError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    trace_id = current_trace_id()
    error: dict[str, str] = {"code": code, "message": message}
    if trace_id:
        error["trace_id"] = trace_id
    return JSONResponse(
        status_code=status_code,
        content={"error": error},
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    del request
    return error_response(exc.code, exc.message, exc.status_code)


async def auth_context_error_handler(request: Request, exc: AuthContextError) -> JSONResponse:
    del request
    return error_response(exc.code, exc.message, exc.status_code)


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    del request
    return error_response("VALIDATION_ERROR", str(exc), 422)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    del request
    return error_response("INTERNAL_ERROR", str(exc), 500)
