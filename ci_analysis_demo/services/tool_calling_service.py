"""
专门处理自主 tool calling。
"""
import json
from typing import Any

from ci_analysis_demo.tools.base import LLMToolCall, ToolResult, ToolRuntimeContext
import logging

from ci_analysis_demo.tools.executor import ToolsExecutor

logger = logging.getLogger(__name__)


def parse_llm_tool_calls(raw_tool_calls: list[dict[str, Any]]) -> list[LLMToolCall]:
    """
    把不同模型返回的 tool_calls 统一转换成内部结构。
    """
    parsed_calls: list[LLMToolCall] = []
    for item in raw_tool_calls:
        try:
            # OpenAI-like 格式示例
            function = item.get("function", {})
            name = function.get("name")
            raw_arguments = function.get("arguments", "{}")
            if isinstance(raw_arguments, str):
                arguments = json.loads(raw_arguments)
            else:
                arguments = raw_arguments

            if not name:
                continue

            parsed_calls.append(
                LLMToolCall(
                    call_id=item.get("id"),
                    tool_name=name,
                    arguments=arguments,
                )
            )

        except Exception as e:
            logger.warning("failed to parse tool call: %s, error=%s", item, repr(e))

    return parsed_calls


async def execute_llm_tool_calls(
        tool_calls: list[LLMToolCall],
        tools_executor: ToolsExecutor,
        max_tool_calls: int = 3,
        runtime_context: ToolRuntimeContext | None = None,
) -> list[ToolResult]:
    """
    执行 LLM 请求的工具调用。
    """
    results: list[ToolResult] = []
    for call in tool_calls[:max_tool_calls]:
        result = await tools_executor.execute(
            tool_name=call.tool_name,
            arguments=call.arguments,
            runtime_context=runtime_context,
        )
        results.append(result)
    return results
