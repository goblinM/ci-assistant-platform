from __future__ import annotations

from typing import Any

from ci_assistant.domain.tools import ToolSpec
from ci_assistant.providers.base import CIProvider


class ProviderToolExecutor:
    """按启用状态、只读策略、项目允许列表和 Provider 能力筛选并执行工具。"""

    def __init__(self, specs: list[ToolSpec]) -> None:
        self._specs = {spec.name: spec for spec in specs}

    def candidates(
        self,
        provider: CIProvider,
        *,
        text: str = "",
        allowed_tools: set[str] | None = None,
    ) -> list[ToolSpec]:
        """返回当前 Provider 和日志特征允许使用的只读工具候选。"""
        normalized = text.lower()
        candidates = []
        for spec in self._specs.values():
            if (
                not spec.enabled
                or not spec.read_only
                or spec.effect != "read"
                or spec.policy != "allow"
            ):
                continue
            if allowed_tools is not None and spec.name not in allowed_tools:
                continue
            if spec.capability not in provider.capabilities:
                continue
            if spec.trigger_keywords and normalized:
                if not any(keyword in normalized for keyword in spec.trigger_keywords):
                    continue
            candidates.append(spec)
        return candidates

    async def execute(
        self,
        name: str,
        provider: CIProvider,
        arguments: dict[str, Any],
        *,
        allowed_tools: set[str] | None = None,
    ) -> dict[str, Any]:
        """再次校验工具权限与 Provider 能力后执行，防止绕过候选筛选直接调用。"""
        try:
            spec = self._specs[name]
        except KeyError as exc:
            raise ValueError(f"unknown tool: {name}") from exc
        if (
            not spec.enabled
            or not spec.read_only
            or spec.effect != "read"
            or spec.policy != "allow"
        ):
            raise PermissionError(f"tool is not enabled for read-only execution: {name}")
        if allowed_tools is not None and name not in allowed_tools:
            raise PermissionError(f"tool is not allowed by project policy: {name}")
        if spec.capability not in provider.capabilities:
            raise ValueError(
                f"provider {provider.provider_type} lacks {spec.capability.value}"
            )
        return await spec.func(provider, **arguments)
