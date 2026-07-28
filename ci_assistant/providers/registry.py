from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ci_assistant.core.config import CIConnectionConfig

from .base import CIProvider


ProviderFactory = Callable[[CIConnectionConfig], CIProvider]


class ProviderRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}

    def register(self, provider_type: str, factory: ProviderFactory) -> None:
        """返回或维护 ``register`` 对应的能力信息。"""
        if provider_type in self._factories:
            raise ValueError(f"provider already registered: {provider_type}")
        self._factories[provider_type] = factory

    def create(self, connection: CIConnectionConfig) -> CIProvider:
        """创建 ``create`` 对应的领域对象或结果。"""
        try:
            factory = self._factories[connection.type]
        except KeyError as exc:
            raise ValueError(f"unsupported provider: {connection.type}") from exc
        return factory(connection)

    def supported_types(self) -> list[str]:
        """返回或维护 ``supported_types`` 对应的能力信息。"""
        return sorted(self._factories)

