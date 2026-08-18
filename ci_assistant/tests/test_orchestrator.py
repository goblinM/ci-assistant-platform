import asyncio
from unittest.mock import AsyncMock

from ci_assistant.diagnosis.orchestrator import DiagnosisOrchestrator
from ci_assistant.schemas.agent import AgentDecision
from ci_assistant.schemas.result import DiagnosisResult


def test_orchestrator_masks_secrets_and_validates_result() -> None:
    """验证 ``test_orchestrator_masks_secrets_and_validates_result`` 所描述的预期行为。"""
    gateway = AsyncMock()
    gateway.diagnose.return_value = DiagnosisResult(
        error_type="dependency_missing",
        summary="requests is missing",
        reason="Module import failed",
        suggestions=["Declare and install requests"],
        confidence="high",
    )
    orchestrator = DiagnosisOrchestrator(gateway)

    output = asyncio.run(
        orchestrator.diagnose(
            "TOKEN=secret-value\nModuleNotFoundError: requests",
            use_rag=False,
            use_tools=False,
        )
    )

    prompt = gateway.diagnose.await_args.args[0]
    assert "secret-value" not in prompt
    assert output.result.error_type == "dependency_missing"
    assert output.trace["clean_log_chars"] > 0


def test_orchestrator_degrades_when_model_fails() -> None:
    """验证 ``test_orchestrator_degrades_when_model_fails`` 所描述的预期行为。"""
    gateway = AsyncMock()
    gateway.diagnose.side_effect = TimeoutError()

    output = asyncio.run(
        DiagnosisOrchestrator(gateway).diagnose(
            "fatal: timeout",
            use_rag=False,
            use_tools=False,
        )
    )

    assert output.result.fallback_used is True
    assert output.result.confidence == "low"


def test_orchestrator_degrades_when_retrieval_fails() -> None:
    """验证 ``test_orchestrator_degrades_when_retrieval_fails`` 所描述的预期行为。"""
    gateway = AsyncMock()
    gateway.diagnose.return_value = DiagnosisResult(
        error_type="unknown",
        summary="diagnosed without retrieval",
        reason="retrieval is optional",
        suggestions=["Inspect the log"],
        confidence="low",
    )
    retriever = AsyncMock(side_effect=OSError("index unavailable"))

    output = asyncio.run(
        DiagnosisOrchestrator(gateway, retriever=retriever).diagnose(
            "ModuleNotFoundError: requests",
            use_tools=False,
        )
    )

    assert output.result.references == []
    assert output.trace["rag_error"] == "OSError"


def test_orchestrator_returns_agent_result_without_workflow_fallback() -> None:
    """验证 Agent 完成时直接返回结构化结果并记录 completed Trace。"""
    gateway = AsyncMock()
    gateway.decide.return_value = AgentDecision(
        action="final_answer",
        final_result=DiagnosisResult(
            error_type="test_failed",
            summary="Agent diagnosis",
            reason="Observed a failed assertion.",
            suggestions=["Inspect the assertion."],
            confidence="high",
        ),
    )
    output = asyncio.run(
        DiagnosisOrchestrator(gateway).diagnose(
            "AssertionError: expected true",
            mode="agent",
            use_rag=False,
            use_tools=False,
        )
    )
    assert output.result.summary == "Agent diagnosis"
    assert output.result.fallback_used is False
    assert output.trace["agent"]["stop_reason"] == "completed"
    gateway.diagnose.assert_not_awaited()
