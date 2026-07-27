from __future__ import annotations

import os
from collections.abc import Mapping

from ci_assistant.core.config import PlatformSettings

from .base import CIProvider
from .gitlab.client import GitLabClient
from .gitlab.provider import GitLabProvider
from .jenkins.client import JenkinsClient
from .jenkins.provider import JenkinsProvider


class ProviderManager:
    def __init__(self, providers: Mapping[str, CIProvider]) -> None:
        self._providers = dict(providers)

    def get(self, connection_id: str) -> CIProvider:
        try:
            return self._providers[connection_id]
        except KeyError as exc:
            raise KeyError(f"unknown CI connection: {connection_id}") from exc

    def list(self) -> list[CIProvider]:
        return list(self._providers.values())


def build_provider_manager(
    settings: PlatformSettings,
    *,
    environ: Mapping[str, str] | None = None,
) -> ProviderManager:
    environment = os.environ if environ is None else environ
    providers: dict[str, CIProvider] = {}
    for connection in settings.ci.connections:
        if connection.id in providers:
            raise ValueError(f"duplicate CI connection: {connection.id}")
        if connection.type == "gitlab":
            token = environment.get(connection.token_env, "")
            if not token:
                raise ValueError(
                    f"missing credential environment variable: {connection.token_env}"
                )
            webhook_secret = (
                environment.get(connection.webhook_secret_env, "")
                if connection.webhook_secret_env
                else None
            )
            providers[connection.id] = GitLabProvider(
                connection.id,
                GitLabClient(connection.base_url, token),
                webhook_secret=webhook_secret,
            )
        elif connection.type == "jenkins":
            token = environment.get(connection.token_env, "")
            username = (
                environment.get(connection.username_env, "")
                if connection.username_env
                else ""
            )
            if not token or not username:
                raise ValueError(
                    "missing Jenkins username or token credential environment variable"
                )
            webhook_secret = (
                environment.get(connection.webhook_secret_env, "")
                if connection.webhook_secret_env
                else None
            )
            providers[connection.id] = JenkinsProvider(
                connection.id,
                JenkinsClient(connection.base_url, username, token),
                webhook_secret=webhook_secret,
            )
        else:
            raise ValueError(f"provider is not implemented: {connection.type}")
    return ProviderManager(providers)
