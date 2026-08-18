import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from ci_assistant.domain.ci import ProviderCapability
from ci_assistant.domain.tools import ToolSpec
from ci_assistant.diagnosis.agent_runtime import (
    AgentRuntimeLimits,
    BoundedAgentRuntime,
    resolve_diagnosis_mode,
)
from ci_assistant.diagnosis.orchestrator import DiagnosisOrchestrator
from ci_assistant.schemas.agent import AgentDecision, AgentRunState, AgentStep, AgentStopReason
from ci_assistant.schemas.result import DiagnosisResult
from ci_assistant.tools import ProviderToolExecutor


def _result() -> DiagnosisResult:
    """构造 Agent Runtime 测试使用的稳定最终诊断。"""
    return DiagnosisResult(
        error_type="test_failed",
        summary="Tests failed",
        reason="The job observation contains a failed assertion.",
        suggestions=["Inspect the first failed assertion."],
        confidence="high",
    )


class SequenceGateway:
    """按固定顺序返回 Agent 决策，并提供 Workflow 回退结果。"""

    def __init__(self, *decisions: AgentDecision | Exception) -> None:
        self.decisions = list(decisions)
        self.prompts = []

    async def decide(self, prompt, tools):
        """返回下一条测试决策或抛出预设异常。"""
        self.prompts.append(prompt)
        del tools
        value = self.decisions.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def diagnose(self, prompt):
        """提供 Agent 停止后的确定性 Workflow 回退结果。"""
        del prompt
        return _result()


def _executor(result=None):
    executor = MagicMock()
    executor.candidates.return_value = [
        SimpleNamespace(name="get_job_context", description="Read job context"),
        SimpleNamespace(name="get_run_context", description="Read run context"),
    ]
    executor.execute = AsyncMock(
        return_value=result if result is not None else {"job": {"status": "failed"}}
    )
    return executor


def _run(gateway, *, limits=None, executor=None):
    runtime = BoundedAgentRuntime(
        gateway,
        executor or _executor(),
        limits or AgentRuntimeLimits(),
    )
    return asyncio.run(
        runtime.run(
            log="job failed",
            references=[],
            provider=MagicMock(),
            tool_arguments={
                "get_job_context": {"project_ref": "group/project", "job_id": "7"},
                "get_run_context": {"project_ref": "group/project", "run_id": "9"},
            },
            use_tools=True,
        )
    )


def test_agent_completes_with_structured_result() -> None:
    """验证 Agent 最终回答会以 completed 状态结束且不调用工具。"""
    output = _run(SequenceGateway(AgentDecision(action="final_answer", final_result=_result())))
    assert output.result == _result()
    assert output.state.stop_reason == AgentStopReason.COMPLETED
    assert output.state.tool_calls == 0


def test_agent_mode_requires_request_and_platform_feature_flag() -> None:
    """验证 Agent 模式必须同时满足请求选择和平台显式启用。"""
    assert resolve_diagnosis_mode("agent", agent_enabled=False) == "workflow"
    assert resolve_diagnosis_mode("workflow", agent_enabled=True) == "workflow"
    assert resolve_diagnosis_mode("agent", agent_enabled=True) == "agent"


def test_agent_blocks_unknown_tool_by_policy() -> None:
    """验证模型请求候选集外工具时由运行时拒绝并停止。"""
    output = _run(SequenceGateway(AgentDecision(action="tool_request", tool_name="rerun_ci")))
    assert output.result is None
    assert output.state.stop_reason == AgentStopReason.POLICY_DENIED


def test_agent_blocks_repeated_tool_call() -> None:
    """验证相同工具和服务端参数的重复调用会被指纹阻断。"""
    decision = AgentDecision(action="tool_request", tool_name="get_job_context")
    output = _run(SequenceGateway(decision, decision))
    assert output.state.stop_reason == AgentStopReason.REPEATED_CALL
    assert output.state.tool_calls == 1


def test_agent_enforces_tool_and_round_budgets() -> None:
    """验证工具预算和最大轮数都会形成稳定停止原因。"""
    decision = AgentDecision(action="tool_request", tool_name="get_job_context")
    tool_budget = _run(
        SequenceGateway(decision),
        limits=AgentRuntimeLimits(max_tool_calls=0),
    )
    max_rounds = _run(
        SequenceGateway(decision),
        limits=AgentRuntimeLimits(max_rounds=1),
    )
    assert tool_budget.state.stop_reason == AgentStopReason.TOOL_BUDGET_EXHAUSTED
    assert max_rounds.state.stop_reason == AgentStopReason.MAX_ROUNDS


def test_agent_enforces_context_budget_and_model_errors() -> None:
    """验证累计上下文超限和模型决策异常均安全停止。"""
    context = _run(
        SequenceGateway(AgentDecision(action="final_answer", final_result=_result())),
        limits=AgentRuntimeLimits(total_prompt_max_chars=10),
    )
    model_error = _run(SequenceGateway(ValueError("invalid decision")))
    assert context.state.stop_reason == AgentStopReason.CONTEXT_BUDGET_EXHAUSTED
    assert model_error.state.stop_reason == AgentStopReason.MODEL_ERROR


def test_agent_stops_on_empty_observation() -> None:
    """验证空工具结果不会继续消耗轮次，而是触发稳定回退。"""
    output = _run(
        SequenceGateway(AgentDecision(action="tool_request", tool_name="get_job_context")),
        executor=_executor({}),
    )
    assert output.state.stop_reason == AgentStopReason.MODEL_ERROR
    assert output.state.steps[-1].error_code == "EMPTY_OBSERVATION"


def test_agent_bounds_individual_tool_execution_time() -> None:
    """验证单次工具超时被转换为受限错误 Observation，且不会泄漏异常正文。"""
    executor = _executor()

    async def slow_execute(*args, **kwargs):
        """模拟超过单工具预算的 Provider 调用。"""
        del args, kwargs
        await asyncio.sleep(0.05)
        return {"status": "late"}

    executor.execute = slow_execute
    output = _run(
        SequenceGateway(
            AgentDecision(action="tool_request", tool_name="get_job_context"),
            AgentDecision(action="final_answer", final_result=_result()),
        ),
        executor=executor,
        limits=AgentRuntimeLimits(tool_timeout_seconds=0.001),
    )
    assert output.state.steps[0].error_code == "TOOL_EXECUTION_FAILED"
    assert output.state.steps[0].observation["status"] == "error"
    assert output.state.steps[0].observation["error_type"] == "TimeoutError"
    assert "content" not in output.state.steps[0].observation


def test_agent_masks_observation_secrets_before_trace() -> None:
    """验证工具 Observation 进入步骤轨迹前会脱敏且按预算截断。"""
    gateway = SequenceGateway(
        AgentDecision(action="tool_request", tool_name="get_job_context"),
        AgentDecision(action="final_answer", final_result=_result()),
    )
    output = _run(
        gateway,
        executor=_executor({"TOKEN": "secret-value", "status": "failed"}),
    )
    assert "secret-value" not in gateway.prompts[1]
    assert "***MASKED***" in gateway.prompts[1]
    assert "content" not in output.state.steps[0].observation
    assert len(output.state.steps[0].observation["content_hash"]) == 64


def test_orchestrator_times_out_agent_and_falls_back_to_workflow() -> None:
    """验证 Agent 总超时后回退现有 Workflow 并记录 timeout 停止原因。"""
    gateway = MagicMock()

    async def slow_decide(prompt, tools):
        """模拟超过 Agent 总预算的模型决策。"""
        del prompt, tools
        await asyncio.sleep(0.05)
        return AgentDecision(action="final_answer", final_result=_result())

    gateway.decide = slow_decide
    gateway.diagnose = AsyncMock(return_value=_result())
    output = asyncio.run(
        DiagnosisOrchestrator(gateway).diagnose(
            "tests failed",
            mode="agent",
            use_rag=False,
            use_tools=False,
            agent_timeout_seconds=0.001,
        )
    )
    assert output.result.fallback_used is True
    assert output.trace["agent"]["stop_reason"] == "timeout"


def test_agent_resumes_after_completed_read_only_step() -> None:
    """验证续跑会恢复预算和 Observation，且不会重复已完成工具调用。"""
    gateway = SequenceGateway(AgentDecision(action="final_answer", final_result=_result()))
    executor = _executor()
    state = AgentRunState(
        goal="Diagnose",
        rounds=1,
        tool_calls=1,
        steps=[
            AgentStep(
                round=1,
                action="tool_request",
                tool_name="get_job_context",
                tool_fingerprint="saved-fingerprint",
            )
        ],
    )
    runtime = BoundedAgentRuntime(gateway, executor, AgentRuntimeLimits())
    output = asyncio.run(
        runtime.run(
            log="job failed",
            references=[],
            provider=MagicMock(),
            tool_arguments={
                "get_job_context": {"project_ref": "group/project", "job_id": "7"}
            },
            use_tools=True,
            initial_state=state,
            resume_observations=[{"tool_name": "get_job_context", "result": {"status": "ok"}}],
        )
    )
    assert output.state.rounds == 2
    assert output.state.tool_calls == 1
    executor.execute.assert_not_awaited()
    assert "get_job_context" in gateway.prompts[0]


def test_executor_never_runs_ask_or_write_tools() -> None:
    """验证 ask 和 write 元数据不能进入 Agent 可执行候选集。"""
    async def tool(provider, **arguments):
        """提供不应被调用的测试工具实现。"""
        del provider, arguments
        return {"status": "unexpected"}

    provider = MagicMock()
    provider.capabilities = {ProviderCapability.RUN_READ}
    executor = ProviderToolExecutor(
        [
            ToolSpec(
                name="draft_comment",
                description="Draft comment",
                func=tool,
                capability=ProviderCapability.RUN_READ,
                effect="write",
                read_only=False,
                policy="ask",
            )
        ]
    )
    assert executor.candidates(provider) == []
    try:
        asyncio.run(executor.execute("draft_comment", provider, {}))
    except PermissionError:
        pass
    else:
        raise AssertionError("ask/write tool must never execute")
