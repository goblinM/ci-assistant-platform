from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestIDMiddleware(BaseHTTPMiddleware):
    """复用调用方请求 ID 或生成新 ID，并在请求与响应之间保持一致。"""

    async def dispatch(self, request: Request, call_next):
        """把请求 ID 写入请求状态，并通过响应头返回给调用方。"""
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
