from unittest.mock import MagicMock

from ci_assistant.core.config import CIConnectionConfig
from ci_assistant.providers.registry import ProviderRegistry


def test_provider_registry_creates_registered_provider() -> None:
    registry = ProviderRegistry()
    provider = MagicMock()
    factory = MagicMock(return_value=provider)
    registry.register("gitlab", factory)
    connection = CIConnectionConfig(
        id="main",
        type="gitlab",
        base_url="https://gitlab.example.com",
        token_env="GITLAB_TOKEN",
    )

    assert registry.create(connection) is provider
    assert registry.supported_types() == ["gitlab"]
    factory.assert_called_once_with(connection)

