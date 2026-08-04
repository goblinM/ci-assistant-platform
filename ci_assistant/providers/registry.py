from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ci_assistant.core.config import CIConnectionConfig

from .base import CIProvider


ProviderFactory = Callable[[CIConnectionConfig], CIProvider]


class ProviderRegistry:
    """注册 Provider 工厂，并按连接类型创建符合统一协议的实例。"""

    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}

    def register(self, provider_type: str, factory: ProviderFactory) -> None:
        """注册唯一 Provider 类型，拒绝静默覆盖已有工厂。"""
        if provider_type in self._factories:
            raise ValueError(f"provider already registered: {provider_type}")
        self._factories[provider_type] = factory

    def create(self, connection: CIConnectionConfig) -> CIProvider:
        """按连接配置选择工厂并创建 Provider，不支持的类型明确失败。"""
        try:
            factory = self._factories[connection.type]
        except KeyError as exc:
            raise ValueError(f"unsupported provider: {connection.type}") from exc
        return factory(connection)

    def supported_types(self) -> list[str]:
        """按稳定顺序返回当前注册的 Provider 类型。"""
        return sorted(self._factories)
