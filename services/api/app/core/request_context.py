from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4

from fastapi import Header

from app.core.config import settings


_trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


class AuthContextError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str | None = None
    actor_id: str | None = None
    request_source: str | None = None
    permission_context: list[str] | None = None
    trace_id: str | None = None


def get_request_context(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
    x_request_source: str | None = Header(default=None, alias="X-Request-Source"),
    x_permission_tags: str | None = Header(default=None, alias="X-Permission-Tags"),
    x_trace_id: str | None = Header(default=None, alias="X-Trace-Id"),
) -> RequestContext:
    use_headers = settings.auth_trusted_header_enabled
    trace_id = _clean_header(x_trace_id) or current_trace_id()
    tenant_id = _clean_header(x_tenant_id) if use_headers else None
    actor_id = _clean_header(x_actor_id) if use_headers else None
    request_source = _clean_header(x_request_source) if use_headers else None
    permission_context = _parse_header_list(x_permission_tags) if use_headers else None

    if _strict_auth_enabled():
        missing = []
        if settings.auth_require_tenant and not tenant_id:
            missing.append("X-Tenant-Id")
        if settings.auth_require_actor and not actor_id:
            missing.append("X-Actor-Id")
        if missing:
            raise AuthContextError(
                code="AUTH_CONTEXT_MISSING",
                message=f"Missing required authentication context: {', '.join(missing)}",
                status_code=401,
            )

    return RequestContext(
        tenant_id=tenant_id,
        actor_id=actor_id,
        request_source=request_source or _default_request_source(),
        permission_context=permission_context,
        trace_id=trace_id,
    )


def resolve_tenant_id(value: str, context: RequestContext) -> str:
    return context.tenant_id or value


def resolve_actor_id(value: str, context: RequestContext) -> str:
    return context.actor_id or value


def resolve_request_source(value: str, context: RequestContext) -> str:
    return context.request_source or value


def resolve_permission_context(value: list[str], context: RequestContext) -> list[str]:
    if context.permission_context:
        return context.permission_context
    if _strict_auth_enabled() and settings.auth_empty_permission_policy == "deny":
        raise AuthContextError(
            code="AUTH_CONTEXT_FORBIDDEN",
            message="Permission context is required",
            status_code=403,
        )
    return value or settings.auth_default_permission_tag_list


def ensure_trace_id(value: str | None = None) -> str:
    trace_id = _clean_header(value) or str(uuid4())
    _trace_id_var.set(trace_id)
    return trace_id


def current_trace_id() -> str | None:
    return _trace_id_var.get()


def _clean_header(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_header_list(value: str | None) -> list[str] | None:
    cleaned = _clean_header(value)
    if cleaned is None:
        return None
    items = [item.strip() for item in cleaned.split(",") if item.strip()]
    return items or None


def _strict_auth_enabled() -> bool:
    return settings.auth_context_mode in {"gateway", "iam"}


def _default_request_source() -> str | None:
    if settings.auth_context_mode in {"gateway", "iam"}:
        return settings.auth_default_request_source
    return None
