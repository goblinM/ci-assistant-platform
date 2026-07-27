from ci_assistant.core.config import load_settings
from ci_assistant.providers.gitlab.provider import GitLabProvider
from ci_assistant.providers.manager import build_provider_manager


def test_provider_manager_builds_gitlab_from_connection_config(tmp_path) -> None:
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

