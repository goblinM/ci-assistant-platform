from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from ci_assistant.core.errors import ErrorCode, PlatformError


logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


async def platform_error_handler(request: Request, exc: PlatformError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "request_id": _request_id(request),
            "data": None,
            "error": {
                "code": exc.code.value,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error", extra={"request_id": _request_id(request)})
    return JSONResponse(
        status_code=500,
        content={
            "request_id": _request_id(request),
            "data": None,
            "error": {
                "code": ErrorCode.INTERNAL_ERROR.value,
                "message": "Internal server error",
                "details": None,
            },
        },
    )

