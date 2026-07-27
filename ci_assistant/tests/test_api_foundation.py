import asyncio

from fastapi import Request
from fastapi.testclient import TestClient

from ci_assistant.core.errors import ErrorCode, PlatformError
from ci_assistant.main import create_app


async def healthy() -> None:
    return None


async def unhealthy() -> None:
    raise ConnectionError("offline")


def test_live_and_ready_health_endpoints() -> None:
    client = TestClient(create_app(readiness_checks={"database": healthy, "redis": healthy}))

    live = client.get("/health/live", headers={"X-Request-ID": "req_test"})
    ready = client.get("/health/ready")

    assert live.status_code == 200
    assert live.headers["X-Request-ID"] == "req_test"
    assert live.json()["data"] == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json()["data"]["checks"] == {"database": "ok", "redis": "ok"}


def test_ready_returns_503_when_dependency_fails() -> None:
    client = TestClient(create_app(readiness_checks={"database": healthy, "redis": unhealthy}))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["data"]["status"] == "not_ready"
    assert response.json()["data"]["checks"]["redis"] == "failed"


def test_platform_errors_use_stable_envelope() -> None:
    app = create_app()

    @app.get("/failure")
    async def failure(request: Request):
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

