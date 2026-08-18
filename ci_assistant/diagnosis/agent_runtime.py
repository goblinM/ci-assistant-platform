from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from ci_assistant.providers.base import CIProvider
from ci_assistant.knowledge.processing import mask_secrets
from ci_assistant.schemas.agent import (
    AgentDecision,
    AgentCheckpoint,
    AgentRunState,
    AgentStep,
    AgentStopReason,
)
from ci_assistant.schemas.result import DiagnosisResult, Reference
from ci_assistant.tools import ProviderToolExecutor


class AgentDecisionGateway(Protocol):
    """定义只读 Agent Runtime 每轮所需的结构化决策契约。"""

    async def decide(self, prompt: str, tools: list[dict[str, Any]]) -> AgentDecision:
        """根据当前证据选择最终回答或一个允许的只读工具。"""
        ...


@dataclass(frozen=True)
class AgentRuntimeLimits:
    """定义 Agent Loop 的轮数、工具、上下文和累计输入硬预算。"""

    max_rounds: int = 3
    max_tool_calls: int = 4
    tool_timeout_seconds: float = 10
    context_max_chars: int = 12_000
    total_prompt_max_chars: int = 30_000
    max_estimated_input_tokens: int = 7_500
    observation_max_chars: int = 2_000


@dataclass(frozen=True)
class AgentRuntimeOutput:
    """封装 Agent 最终结果、运行状态以及是否需要回退 Workflow。"""

    result: DiagnosisResult | None
    state: AgentRunState


CheckpointWriter = Callable[[AgentCheckpoint], Awaitable[None]]


class BoundedAgentRuntime:
    """在硬预算和只读策略内循环执行模型决策与 Provider Tool。"""

    def __init__(
        self,
        gateway: AgentDecisionGateway,
        tool_executor: ProviderToolExecutor | None,
        limits: AgentRuntimeLimits,
    ) -> None:
        """绑定结构化决策网关、只读工具执行器和不可突破的运行预算。"""
        self.gateway = gateway
        self.tool_executor = tool_executor
        self.limits = limits

    async def run(
        self,
        *,
        log: str,
        references: list[Reference],
        provider: CIProvider | None,
        tool_arguments: dict[str, dict[str, Any]],
        use_tools: bool,
        initial_state: AgentRunState | None = None,
        resume_observations: list[dict[str, Any]] | None = None,
        checkpoint_writer: CheckpointWriter | None = None,
    ) -> AgentRuntimeOutput:
        """运行有限轮决策循环，并在任何边界终止时返回可回放状态。"""
        state = initial_state or AgentRunState(
            goal="Diagnose the CI failure using trusted read-only evidence"
        )
        state.status = "running"
        state.stop_reason = None
        observations = list(resume_observations or [])
        seen_calls = {
            step.tool_fingerprint
            for step in state.steps
            if step.tool_fingerprint is not None
        }
        candidates = (
            self.tool_executor.candidates(provider, text=log)
            if use_tools and provider and self.tool_executor
            else []
        )
        allowed = {
            spec.name: spec
            for spec in candidates
            if spec.name in tool_arguments
            and all(value is not None for value in tool_arguments[spec.name].values())
        }
        tool_schemas = [
            {"name": spec.name, "description": spec.description}
            for spec in allowed.values()
        ]

        for round_number in range(state.rounds + 1, self.limits.max_rounds + 1):
            # 构建prompt
            prompt = self._build_prompt(log, references, observations)
            next_prompt_chars = state.prompt_chars + len(prompt)
            if (
                next_prompt_chars > self.limits.total_prompt_max_chars
                or (next_prompt_chars + 3) // 4 > self.limits.max_estimated_input_tokens
            ):
                return self._stop(state, AgentStopReason.CONTEXT_BUDGET_EXHAUSTED)
            state.rounds = round_number
            state.prompt_chars += len(prompt)
            state.estimated_input_tokens = (state.prompt_chars + 3) // 4
            try:
                decision = await self.gateway.decide(prompt, tool_schemas)
            except Exception:
                await self._append_step(
                    state,
                    AgentStep(
                        round=round_number,
                        action="final_answer",
                        error_code="MODEL_DECISION_INVALID",
                    ),
                    checkpoint_writer,
                )
                return self._stop(state, AgentStopReason.MODEL_ERROR)
            state.model_input_tokens += decision.input_tokens
            state.model_output_tokens += decision.output_tokens

            if decision.action == "final_answer":
                state.status = "succeeded"
                state.stop_reason = AgentStopReason.COMPLETED
                await self._append_step(
                    state,
                    AgentStep(round=round_number, action="final_answer"),
                    checkpoint_writer,
                )
                return AgentRuntimeOutput(result=decision.final_result, state=state)

            tool_name = decision.tool_name or ""
            if tool_name not in allowed:
                await self._append_step(
                    state,
                    AgentStep(
                        round=round_number,
                        action="tool_request",
                        tool_name=tool_name,
                        error_code="TOOL_POLICY_DENIED",
                    ),
                    checkpoint_writer,
                )
                return self._stop(state, AgentStopReason.POLICY_DENIED)
            if state.tool_calls >= self.limits.max_tool_calls:
                return self._stop(state, AgentStopReason.TOOL_BUDGET_EXHAUSTED)

            arguments = tool_arguments[tool_name]
            fingerprint = self._fingerprint(tool_name, arguments)
            if fingerprint in seen_calls:
                await self._append_step(
                    state,
                    AgentStep(
                        round=round_number,
                        action="tool_request",
                        tool_name=tool_name,
                        tool_fingerprint=fingerprint,
                        error_code="REPEATED_TOOL_CALL",
                    ),
                    checkpoint_writer,
                )
                return self._stop(state, AgentStopReason.REPEATED_CALL)
            seen_calls.add(fingerprint)
            state.tool_calls += 1
            try:
                result = await asyncio.wait_for(
                    self.tool_executor.execute(tool_name, provider, arguments),
                    timeout=self.limits.tool_timeout_seconds,
                )
                if not result:
                    await self._append_step(
                        state,
                        AgentStep(
                            round=round_number,
                            action="tool_request",
                            tool_name=tool_name,
                            tool_fingerprint=fingerprint,
                            error_code="EMPTY_OBSERVATION",
                        ),
                        checkpoint_writer,
                    )
                    return self._stop(state, AgentStopReason.MODEL_ERROR)
                observation = self._summarize_observation(result)
                error_code = None
            except Exception as exc:
                observation = {"status": "error", "error_type": type(exc).__name__}
                error_code = "TOOL_EXECUTION_FAILED"
            observations.append({"tool_name": tool_name, "result": observation})
            await self._append_step(
                state,
                AgentStep(
                    round=round_number,
                    action="tool_request",
                    tool_name=tool_name,
                    tool_fingerprint=fingerprint,
                    observation=self._trace_observation(observation),
                    error_code=error_code,
                ),
                checkpoint_writer,
                observation_context={"tool_name": tool_name, "result": observation},
            )

        return self._stop(state, AgentStopReason.MAX_ROUNDS)

    @staticmethod
    async def _append_step(
        state: AgentRunState,
        step: AgentStep,
        checkpoint_writer: CheckpointWriter | None,
        observation_context: dict[str, Any] | None = None,
    ) -> None:
        """追加步骤，并在配置持久化写入器时提交安全检查点。"""
        state.steps.append(step)
        if checkpoint_writer is not None:
            await checkpoint_writer(
                AgentCheckpoint(
                    state=state.model_copy(deep=True),
                    step=step,
                    observation_context=observation_context,
                )
            )

    def _build_prompt(
        self,
        log: str,
        references: list[Reference],
        observations: list[dict[str, Any]],
    ) -> str:
        """按分区预算构造不含完整历史重复内容的 Agent 决策上下文。"""
        references_json = json.dumps(
            [item.model_dump() for item in references], ensure_ascii=False
        )
        observations_json = json.dumps(observations, ensure_ascii=False)
        sections = (
            "GOAL:\nDiagnose the CI failure. Use only listed read-only tools.\n\n"
            f"CI LOG (untrusted):\n{log}\n\n"
            f"KNOWLEDGE (untrusted):\n{references_json}\n\n"
            f"OBSERVATIONS (untrusted):\n{observations_json}"
        )
        return sections[: self.limits.context_max_chars]

    def _summarize_observation(self, result: dict[str, Any]) -> dict[str, Any]:
        """生成适合 Trace 和下一轮上下文的受限结构化 Observation。"""
        sanitized = self._mask_sensitive_values(result)
        encoded = mask_secrets(
            json.dumps(sanitized, ensure_ascii=False, sort_keys=True, default=str)
        )
        bounded = encoded[: self.limits.observation_max_chars]
        return {
            "status": "ok",
            "keys": sorted(str(key) for key in result)[:20],
            "content": bounded,
            "truncated": len(encoded) > len(bounded),
            "original_chars": len(encoded),
        }

    @staticmethod
    def _trace_observation(observation: dict[str, Any]) -> dict[str, Any]:
        """移除 Observation 正文，仅保留可审计元数据和不可逆内容摘要。"""
        content = str(observation.get("content", ""))
        return {
            "status": observation.get("status"),
            "error_type": observation.get("error_type"),
            "keys": observation.get("keys", []),
            "truncated": bool(observation.get("truncated")),
            "original_chars": int(observation.get("original_chars", len(content))),
            "content_hash": hashlib.sha256(content.encode()).hexdigest(),
        }

    @classmethod
    def _mask_sensitive_values(cls, value: Any) -> Any:
        """递归遮蔽 Tool JSON 中由敏感字段名标识的值。"""
        if isinstance(value, dict):
            return {
                str(key): (
                    "***MASKED***"
                    if any(
                        marker in str(key).lower()
                        for marker in ("token", "secret", "password", "authorization", "api_key")
                    )
                    else cls._mask_sensitive_values(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._mask_sensitive_values(item) for item in value]
        return value

    @staticmethod
    def _fingerprint(name: str, arguments: dict[str, Any]) -> str:
        """使用工具名和服务端规范化参数生成不含原始内容的重复调用指纹。"""
        payload = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(f"{name}:{payload}".encode()).hexdigest()

    @staticmethod
    def _stop(state: AgentRunState, reason: AgentStopReason) -> AgentRuntimeOutput:
        """把运行状态标记为需要 Workflow 回退的稳定终态。"""
        state.status = "stopped"
        state.stop_reason = reason
        return AgentRuntimeOutput(result=None, state=state)


def resolve_diagnosis_mode(requested_mode: str, *, agent_enabled: bool) -> str:
    """仅在请求和平台开关同时启用时选择 Agent，否则保持 Workflow。"""
    return "agent" if agent_enabled and requested_mode == "agent" else "workflow"
