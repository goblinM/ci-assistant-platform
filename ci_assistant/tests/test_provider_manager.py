from ci_assistant.core.config import load_settings
from ci_assistant.providers.github.provider import GitHubProvider
from ci_assistant.providers.gitlab.provider import GitLabProvider
from ci_assistant.providers.manager import build_provider_manager


def test_provider_manager_builds_gitlab_from_connection_config(tmp_path) -> None:
    """验证 ``test_provider_manager_builds_gitlab_from_connection_config`` 所描述的预期行为。"""
    config = tmp_path / "config.yml"
    config.write_text(
        """
ci:
  connections:
    - id: primary
      type: gitlab
      base_url: https://gitlab.example.com
      token_env: GITLAB_TOKEN
      webhook_secret_env: GITLAB_WEBHOOK_SECRET
""",
        encoding="utf-8",
    )
    settings = load_settings(config, environ={})

    manager = build_provider_manager(
        settings,
        environ={"GITLAB_TOKEN": "token", "GITLAB_WEBHOOK_SECRET": "secret"},
    )

    provider = manager.get("primary")
    assert isinstance(provider, GitLabProvider)
    assert provider.webhook_secret == "secret"


def test_provider_manager_builds_github_from_connection_config(tmp_path) -> None:
    """验证 Provider Manager 从配置构建 GitHub Provider。"""
    config = tmp_path / "config.yml"
    config.write_text(
        """
ci:
  connections:
    - id: github-main
      type: github
      base_url: https://api.github.com
      token_env: GITHUB_APP_TOKEN
      webhook_secret_env: GITHUB_WEBHOOK_SECRET
""",
        encoding="utf-8",
    )
    settings = load_settings(config, environ={})

    manager = build_provider_manager(
        settings,
        environ={"GITHUB_APP_TOKEN": "token", "GITHUB_WEBHOOK_SECRET": "secret"},
    )

    provider = manager.get("github-main")
    assert isinstance(provider, GitHubProvider)
    assert provider.webhook_secret == "secret"
