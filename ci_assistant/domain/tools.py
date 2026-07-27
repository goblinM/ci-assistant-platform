from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

from .ci import ProviderCapability


ToolCallable = Callable[..., Awaitable[dict[str, Any]]]


class ToolSpec(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    name: str
    description: str
    func: ToolCallable
    capability: ProviderCapability
    tags: frozenset[str] = Field(default_factory=frozenset)
    trigger_keywords: frozenset[str] = Field(default_factory=frozenset)
    read_only: bool = True
    enabled: bool = True

