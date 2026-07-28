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

