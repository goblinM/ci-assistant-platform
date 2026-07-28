from __future__ import annotations

import hmac
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ci_assistant.core.config import PlatformSettings
from ci_assistant.core.errors import ErrorCode, PlatformError


_PUBLIC_PREFIXES = (
    "/health/",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/webhooks/",
)


class TenantAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """处理 ``dispatch`` 对应的请求或事件。"""
        if request.url.path.startswith(_PUBLIC_PREFIXES):
            return await call_next(request)
        settings: PlatformSettings | None = getattr(request.app.state, "settings", None)
        if settings is None:
            return await call_next(request)
        keys = settings.security.api_keys()
        if not keys and settings.app.environment != "production":
            return await call_next(request)

        supplied = request.headers.get("Authorization", "")
        supplied = supplied.removeprefix("Bearer ").strip()
        tenant = next(
            (
                mapped_tenant
                for key, mapped_tenant in keys.items()
                if hmac.compare_digest(key, supplied)
            ),
            None,
        )
        if tenant is None:
            return JSONResponse(
                status_code=401,
                content={
                    "request_id": getattr(request.state, "request_id", "req_unknown"),
                    "data": None,
                    "error": {
                        "code": ErrorCode.AUTH_FAILED.value,
                        "message": "Invalid or missing API key",
                        "details": None,
                    },
                },
            )
        request.state.is_admin = tenant == "*"
        request.state.tenant_id = None if tenant == "*" else UUID(tenant)
        return await call_next(request)


def enforce_tenant(request: Request, tenant_id: UUID) -> None:
    """执行 ``enforce_tenant`` 对应的领域操作。"""
    authorized = getattr(request.state, "tenant_id", None)
    is_admin = getattr(request.state, "is_admin", False)
    if authorized is not None and authorized != tenant_id and not is_admin:
        raise PlatformError(
            ErrorCode.PERMISSION_DENIED,
            "Tenant scope does not match the authenticated API key",
            status_code=403,
        )


def enforce_admin(request: Request) -> None:
    """执行 ``enforce_admin`` 对应的领域操作。"""
    if hasattr(request.state, "is_admin") and not request.state.is_admin:
        raise PlatformError(
            ErrorCode.PERMISSION_DENIED,
            "Platform administrator permission is required",
            status_code=403,
        )
