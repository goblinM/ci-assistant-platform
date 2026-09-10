from fastapi.testclient import TestClient

from ci_assistant.main import create_app
from ci_assistant.core.metrics import observe_agent_steps
from ci_assistant.schemas.agent import AgentStep


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
    assert "ci_assistant_agent_tool_decisions_total" in response.text
    assert "ci_assistant_agent_self_checks_total" in response.text
    assert "ci_assistant_agent_evidence_gaps_total" in response.text


def test_agent_step_metrics_use_bounded_labels() -> None:
    """验证未知工具不会进入 Prometheus 标签，并记录自检和证据缺口。"""
    observe_agent_steps(
        [
            AgentStep(
                round=1,
                action="tool_request",
                tool_name="model-invented-tool",
                evidence_gap="Need more evidence",
                error_code="TOOL_POLICY_DENIED",
            ),
            AgentStep(
                round=2,
                action="self_check",
                error_code="SELF_CHECK_LOW_CONFIDENCE",
            ),
        ]
    )
    response = TestClient(create_app()).get("/metrics")
    assert 'outcome="policy_denied",tool="unknown"' in response.text
    assert 'trigger="low_confidence"' in response.text
