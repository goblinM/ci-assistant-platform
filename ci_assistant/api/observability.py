from __future__ import annotations

import time

from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ci_assistant.core.metrics import HTTP_DURATION, HTTP_REQUESTS


router = APIRouter(tags=["observability"])


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        """处理 ``dispatch`` 对应的请求或事件。"""
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        HTTP_DURATION.labels(request.method, path).observe(time.perf_counter() - started)
        return response


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """执行 ``metrics`` 对应的领域操作。"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

