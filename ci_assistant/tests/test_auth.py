from uuid import uuid4
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from ci_assistant.core.config import load_settings
from ci_assistant.main import create_app


def test_api_key_authentication_and_tenant_scope() -> None:
    tenant_id = uuid4()
    app = create_app()
    app.state.settings = load_settings(
        environ={"API_KEYS_JSON": f'{{"tenant-key": "{tenant_id}", "admin-key": "*"}}'}
    )
    app.state.provider_manager = MagicMock()
    app.state.provider_manager.list.return_value = []
    client = TestClient(app)

    unauthorized = client.get("/api/v1/connections")
    tenant_forbidden = client.get(
        "/api/v1/connections",
        headers={"Authorization": "Bearer tenant-key"},
    )
    admin = client.get(
        "/api/v1/connections",
        headers={"Authorization": "Bearer admin-key"},
    )

    assert unauthorized.status_code == 401
    assert unauthorized.json()["request_id"].startswith("req_")
    assert tenant_forbidden.status_code == 403
    assert admin.status_code == 200


def test_health_endpoint_does_not_require_api_key() -> None:
    app = create_app()
    app.state.settings = load_settings(
        environ={"API_KEYS_JSON": '{"key": "*"}'}
    )
    assert TestClient(app).get("/health/live").status_code == 200
