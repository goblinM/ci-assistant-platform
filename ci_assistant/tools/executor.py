from __future__ import annotations

from typing import Any

from ci_assistant.domain.tools import ToolSpec
from ci_assistant.providers.base import CIProvider


class ProviderToolExecutor:
    def __init__(self, specs: list[ToolSpec]) -> None:
        self._specs = {spec.name: spec for spec in specs}

    def candidates(
        self,
        provider: CIProvider,
        *,
        text: str = "",
        allowed_tools: set[str] | None = None,
    ) -> list[ToolSpec]:
        """执行 ``candidates`` 对应的领域操作。"""
        normalized = text.lower()
        candidates = []
        for spec in self._specs.values():
            if not spec.enabled or not spec.read_only:
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
        """执行 ``execute`` 对应的领域操作。"""
        try:
            spec = self._specs[name]
        except KeyError as exc:
            raise ValueError(f"unknown tool: {name}") from exc
        if not spec.enabled or not spec.read_only:
            raise PermissionError(f"tool is not enabled for read-only execution: {name}")
        if allowed_tools is not None and name not in allowed_tools:
            raise PermissionError(f"tool is not allowed by project policy: {name}")
        if spec.capability not in provider.capabilities:
            raise ValueError(
                f"provider {provider.provider_type} lacks {spec.capability.value}"
            )
        return await spec.func(provider, **arguments)

