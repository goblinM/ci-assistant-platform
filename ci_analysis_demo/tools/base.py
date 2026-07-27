"""
定义ToolResult，ToolCallRecord等统一模型
"""
from pydantic import BaseModel, Field
from typing import Any, Callable

from pydantic.dataclasses import dataclass


@dataclass
class ToolSpec:
    # ToolSpec
    #   ↓
    # ToolAdapter
    #   ↓
    # MCP / Skill / HTTP API / Python Function
    name: str
    description: str
    func: Callable[..., dict[str, Any]]
    parameters_schema: dict[str, Any]
    provider: str = "local"
    enabled: bool = True
    read_only: bool = True
    tags: list[str] | None = None
    result_trimmer: Callable[..., dict[str, Any] | None] | None = None
    # 声明适合什么场景
    trigger_keywords: list[str] | None = None
    always_candidate: bool = False
    """
    如果 provider = local → 调本地函数
    如果 provider = mcp → 调 MCP client
    如果 provider = skill → 调 skill executor
    如果 provider = http → 调内部 API
    """


class LLMToolCall(BaseModel):
    call_id: str | None = None
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    # 工具结果
    tool_name: str
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: float | None = None


class ToolRuntimeContext(BaseModel):
    """仅在单次分析请求内传递的工具运行时数据。"""
    trace_id: str | None = None
    prefetched: dict[str, dict[str, Any]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def cache_key(*parts: str | int | None) -> str:
        return ":".join(str(part) for part in parts if part is not None)

    def get_prefetched(self, resource: str, *key_parts: str | int | None) -> Any:
        key = self.cache_key(*key_parts)
        return self.prefetched.get(resource, {}).get(key)


class ToolCallRequest(BaseModel):
    # 工具请求
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolContext(BaseModel):
    primary_error: dict[str, Any] | None = None
    matched_errors: list[dict[str, Any]] = Field(default_factory=list)
    results: list[ToolResult] = Field(default_factory=list)

    @property
    def called_tool_names(self) -> list[str]:
        return [item.tool_name for item in self.results]

    @property
    def successful_tool_names(self) -> list[str]:
        return [item.tool_name for item in self.results if item.success]

    @property
    def failed_tool_names(self) -> list[str]:
        return [item.tool_name for item in self.results if not item.success]

    def to_prompt_context(self) -> dict[str, Any]:
        return {
            "primary_error": self.primary_error,
            "matched_errors": self.matched_errors,
            "tool_results": [
                {
                    "tool_name": result.tool_name,
                    "success": result.success,
                    "data": result.data,
                    "error": result.error,
                }
                for result in self.results
            ],
        }
