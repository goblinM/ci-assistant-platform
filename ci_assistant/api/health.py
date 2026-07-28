from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


ReadinessCheck = Callable[[], Awaitable[None]]
router = APIRouter(tags=["health"])


def _envelope(request: Request, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": request.state.request_id,
        "data": data,
        "error": None,
    }


@router.get("/health/live")
async def live(request: Request) -> dict[str, Any]:
    """检查 ``live`` 对应的就绪状态。"""
    return _envelope(request, {"status": "ok"})


@router.get("/health/ready")
async def ready(request: Request) -> JSONResponse:
    """检查 ``ready`` 对应的就绪状态。"""
    checks: Mapping[str, ReadinessCheck] = getattr(request.app.state, "readiness_checks", {})

    async def run_check(name: str, check: ReadinessCheck) -> tuple[str, str]:
        """检查 ``run_check`` 对应的就绪状态。"""
        try:
            await asyncio.wait_for(check(), timeout=2)
            return name, "ok"
        except Exception:
            return name, "failed"

    results = dict(await asyncio.gather(*(run_check(name, check) for name, check in checks.items())))
    is_ready = all(status == "ok" for status in results.values())
    content = _envelope(
        request,
        {"status": "ready" if is_ready else "not_ready", "checks": results},
    )
    return JSONResponse(status_code=200 if is_ready else 503, content=content)

