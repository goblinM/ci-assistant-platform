import asyncio

from fastapi import Request
from fastapi.testclient import TestClient

from ci_assistant.core.errors import ErrorCode, PlatformError
from ci_assistant.main import create_app


async def healthy() -> None:
    """提供 ``healthy`` 场景所需的测试替身。"""
    return None


async def unhealthy() -> None:
    """提供 ``unhealthy`` 场景所需的测试替身。"""
    raise ConnectionError("offline")


def test_live_and_ready_health_endpoints() -> None:
    """验证 ``test_live_and_ready_health_endpoints`` 所描述的预期行为。"""
    client = TestClient(create_app(readiness_checks={"database": healthy, "redis": healthy}))

    live = client.get("/health/live", headers={"X-Request-ID": "req_test"})
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.headers["X-Request-ID"] == "req_test"
    assert live.json()["data"] == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json()["data"]["checks"] == {"database": "ok", "redis": "ok"}


def test_ready_returns_503_when_dependency_fails() -> None:
    """验证 ``test_ready_returns_503_when_dependency_fails`` 所描述的预期行为。"""
    client = TestClient(create_app(readiness_checks={"database": healthy, "redis": unhealthy}))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["data"]["status"] == "not_ready"
    assert response.json()["data"]["checks"]["redis"] == "failed"


def test_platform_errors_use_stable_envelope() -> None:
    """验证 ``test_platform_errors_use_stable_envelope`` 所描述的预期行为。"""
    app = create_app()

    @app.get("/failure")
    async def failure(request: Request):
        """提供 ``failure`` 场景所需的测试替身。"""
        raise PlatformError(
            ErrorCode.RESOURCE_NOT_FOUND,
            "Missing resource",
            status_code=404,
        )

    response = TestClient(app).get("/failure")

    assert response.status_code == 404
    assert response.json()["data"] is None
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert response.json()["request_id"].startswith("req_")

