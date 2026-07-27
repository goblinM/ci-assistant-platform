import asyncio

from ci_assistant.llm.gateway import RuleBasedDiagnosisGateway


def test_rule_gateway_supports_offline_dependency_diagnosis() -> None:
    result = asyncio.run(
        RuleBasedDiagnosisGateway().diagnose(
            "ModuleNotFoundError: No module named 'requests'"
        )
    )
    assert result.error_type == "dependency_missing"
    assert result.confidence == "high"

