from __future__ import annotations

from fastapi import APIRouter, Request

from ci_assistant.core.errors import ErrorCode, PlatformError
from ci_assistant.api.auth import enforce_admin


router = APIRouter(prefix="/api/v1/connections", tags=["connections"])


@router.get("")
async def list_connections(request: Request):
    """列出 ``list_connections`` 对应的数据。"""
    enforce_admin(request)
    providers = request.app.state.provider_manager.list()
    return {
        "request_id": request.state.request_id,
        "data": [
            {
                "id": provider.connection_id,
                "provider": provider.provider_type,
                "capabilities": sorted(item.value for item in provider.capabilities),
            }
            for provider in providers
        ],
        "error": None,
    }


@router.post("/{connection_id}/test")
async def test_connection(connection_id: str, request: Request):
    """检查 ``test_connection`` 对应的服务状态。"""
    enforce_admin(request)
    try:
        provider = request.app.state.provider_manager.get(connection_id)
    except KeyError as exc:
        raise PlatformError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "CI connection not configured",
            status_code=404,
        ) from exc
    return {
        "request_id": request.state.request_id,
        "data": await provider.test_connection(),
        "error": None,
    }
