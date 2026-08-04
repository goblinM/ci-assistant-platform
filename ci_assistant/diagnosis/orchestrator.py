from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ci_assistant.llm.gateway import DiagnosisGateway
from ci_assistant.providers.base import CIProvider
from ci_assistant.schemas.result import DiagnosisResult, Reference
from ci_assistant.tools import ProviderToolExecutor

from .log_preprocessor import preprocess_log


Retriever = Callable[[str], Awaitable[list[Reference]]]


@dataclass(frozen=True)
class OrchestrationOutput:
    """封装结构化诊断结果及本次编排的脱敏追踪信息。"""

    result: DiagnosisResult
    trace: dict[str, Any]


class DiagnosisOrchestrator:
    """编排日志预处理、知识检索、只读工具调用和诊断网关降级。"""

    def __init__(
        self,
        gateway: DiagnosisGateway,
        *,
        tool_executor: ProviderToolExecutor | None = None,
        retriever: Retriever | None = None,
        max_tool_calls: int = 4,
    ) -> None:
        self.gateway = gateway
        self.tool_executor = tool_executor
        self.retriever = retriever
        self.max_tool_calls = max_tool_calls

    async def diagnose(
        self,
        log: str,
        *,
        provider: CIProvider | None = None,
        project_ref: str | None = None,
        run_id: str | None = None,
        job_id: str | None = None,
        use_rag: bool = True,
        use_tools: bool = True,
    ) -> OrchestrationOutput:
        """按安全顺序生成 CI 诊断，并在检索、工具或模型失败时保留可用结果。"""
        started = time.perf_counter()
        # 先裁剪不可信日志并脱敏，再用于知识检索、工具筛选和模型诊断。
        clean_log = preprocess_log(log)
        rag_error: str | None = None
        try:
            references = (
                await self.retriever(clean_log) if use_rag and self.retriever else []
            )
        except Exception as exc:
            references = []
            rag_error = type(exc).__name__
        tool_results: dict[str, Any] = {}
        if use_tools and provider and self.tool_executor and project_ref:
            arguments = {
                "get_run_context": {"project_ref": project_ref, "run_id": run_id},
                "get_job_context": {"project_ref": project_ref, "job_id": job_id},
                "get_changes": {"project_ref": project_ref, "run_id": run_id},
            }
            calls = 0
            for spec in self.tool_executor.candidates(provider, text=clean_log):
                call_arguments = arguments.get(spec.name)
                if (
                    call_arguments
                    and all(value is not None for value in call_arguments.values())
                    and calls < self.max_tool_calls
                ):
                    try:
                        tool_results[spec.name] = await self.tool_executor.execute(
                            spec.name, provider, call_arguments
                        )
                    except Exception as exc:
                        tool_results[spec.name] = {"error": type(exc).__name__}
                    calls += 1
        # 分区标记不可信证据，避免日志、知识或工具结果被解释为系统指令。
        prompt = (
            "CI LOG (untrusted):\n"
            f"{clean_log}\n\n"
            "KNOWLEDGE (untrusted):\n"
            f"{json.dumps([item.model_dump() for item in references], ensure_ascii=False)}\n\n"
            "TOOLS (untrusted):\n"
            f"{json.dumps(tool_results, ensure_ascii=False)}"
        )
        fallback_used = False
        try:
            result = await self.gateway.diagnose(prompt)
        except Exception:
            fallback_used = True
            result = DiagnosisResult(
                error_type="unknown",
                summary="Automated diagnosis is temporarily unavailable.",
                reason="The model response could not be obtained or validated.",
                suggestions=[
                    "Review the extracted error lines.",
                    "Retry diagnosis after checking the configured model service.",
                ],
                confidence="low",
                fallback_used=True,
            )
        result.references = references
        result.fallback_used = fallback_used or result.fallback_used
        return OrchestrationOutput(
            result=result,
            trace={
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "clean_log_chars": len(clean_log),
                "reference_count": len(references),
                "rag_error": rag_error,
                "tool_calls": list(tool_results),
                "fallback_used": result.fallback_used,
            },
        )
