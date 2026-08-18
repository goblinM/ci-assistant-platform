import asyncio

from ci_assistant.llm.gateway import RuleBasedDiagnosisGateway


def test_rule_gateway_supports_offline_dependency_diagnosis() -> None:
    """验证 ``test_rule_gateway_supports_offline_dependency_diagnosis`` 所描述的预期行为。"""
    result = asyncio.run(
        RuleBasedDiagnosisGateway().diagnose(
            "ModuleNotFoundError: No module named 'requests'"
        )
    )
    assert result.error_type == "dependency_missing"
    assert result.confidence == "high"


def test_rule_gateway_provides_deterministic_agent_final_answer() -> None:
    """验证规则网关在 Agent 模式下直接返回符合契约的最终回答。"""
    decision = asyncio.run(
        RuleBasedDiagnosisGateway().decide(
            "tests failed with AssertionError",
            [{"name": "get_job_log", "description": "read log"}],
        )
    )
    assert decision.action == "final_answer"
    assert decision.final_result.error_type == "test_failed"
