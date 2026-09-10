from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from .ci import ProviderCapability


ToolCallable = Callable[..., Awaitable[dict[str, Any]]]


class ToolSpec(BaseModel):
    """定义 Provider Tool 的能力、效果、风险与执行授权策略。"""

    model_config = {"arbitrary_types_allowed": True}

    name: str
    description: str
    func: ToolCallable
    capability: ProviderCapability
    input_schema: dict[str, Any] = Field(default_factory=dict)
    tags: frozenset[str] = Field(default_factory=frozenset)
    trigger_keywords: frozenset[str] = Field(default_factory=frozenset)
    read_only: bool = True
    enabled: bool = True
    effect: Literal["read", "write"] = "read"
    risk: Literal["low", "medium", "high"] = "low"
    policy: Literal["allow", "ask", "deny"] = "allow"
