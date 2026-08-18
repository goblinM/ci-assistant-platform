from fastapi.testclient import TestClient

from ci_assistant.main import create_app


def test_metrics_endpoint_exposes_request_counters() -> None:
    """验证 ``test_metrics_endpoint_exposes_request_counters`` 所描述的预期行为。"""
    client = TestClient(create_app())
    client.get("/health/live")

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "ci_assistant_http_requests_total" in response.text
    assert "ci_assistant_http_request_duration_seconds" in response.text
    assert "ci_assistant_agent_rounds" in response.text
    assert "ci_assistant_agent_tool_calls" in response.text
    assert "ci_assistant_agent_estimated_input_tokens" in response.text
