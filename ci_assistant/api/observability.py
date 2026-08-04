from __future__ import annotations

import time

from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from ci_assistant.core.metrics import HTTP_DURATION, HTTP_REQUESTS


router = APIRouter(tags=["observability"])


class MetricsMiddleware(BaseHTTPMiddleware):
    """按稳定路由模板记录 HTTP 请求数量、状态码和处理耗时。"""

    async def dispatch(self, request, call_next):
        """执行请求后记录 Prometheus 指标，避免使用含具体资源 ID 的原始路径。"""
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        HTTP_DURATION.labels(request.method, path).observe(time.perf_counter() - started)
        return response


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """返回 Prometheus 文本格式的当前进程指标快照。"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
