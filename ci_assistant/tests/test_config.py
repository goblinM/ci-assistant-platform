from pathlib import Path

import pytest
from pydantic import ValidationError

from ci_assistant.core.config import ConfigurationError, load_settings


def test_load_settings_applies_all_precedence_layers(tmp_path: Path) -> None:
    """验证 ``test_load_settings_applies_all_precedence_layers`` 所描述的预期行为。"""
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
app:
  port: 7000
ai:
  base_url: https://yaml.example/v1
  api_key: yaml-key
  model: yaml-model
""",
        encoding="utf-8",
    )
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    (secrets_dir / "LLM_API_KEY").write_text("secret-key\n", encoding="utf-8")

    settings = load_settings(
        config_path,
        environ={"APP_PORT": "8000", "LLM_API_KEY": "environment-key"},
        secrets_dir=secrets_dir,
    )

    assert settings.app.port == 8000
    assert settings.ai.base_url == "https://yaml.example/v1"
    assert settings.ai.api_key.get_secret_value() == "secret-key"
    assert settings.ai.model == "yaml-model"


def test_nested_environment_variables_are_supported() -> None:
    """验证 ``test_nested_environment_variables_are_supported`` 所描述的预期行为。"""
    settings = load_settings(
        environ={
            "CI_ASSISTANT__APP__ENVIRONMENT": "test",
            "CI_ASSISTANT__KNOWLEDGE__CONTEXT_MAX_CHARS": "9000",
        }
    )

    assert settings.app.environment == "test"
    assert settings.knowledge.context_max_chars == 9000


def test_unlimited_ocr_nested_configuration_is_supported() -> None:
    """验证 Unlimited-OCR 可通过嵌套环境变量启用和限流。"""
    settings = load_settings(
        environ={
            "CI_ASSISTANT__KNOWLEDGE__UNLIMITED_OCR__ENABLED": "true",
            "CI_ASSISTANT__KNOWLEDGE__UNLIMITED_OCR__BASE_URL": (
                "http://ocr.internal:10000"
            ),
            "CI_ASSISTANT__KNOWLEDGE__UNLIMITED_OCR__MAX_PDF_PAGES": "20",
        }
    )

    assert settings.knowledge.unlimited_ocr.enabled is True
    assert settings.knowledge.unlimited_ocr.base_url == "http://ocr.internal:10000"
    assert settings.knowledge.unlimited_ocr.max_pdf_pages == 20


def test_unlimited_ocr_rejects_non_http_service_url() -> None:
    """验证 Unlimited-OCR 拒绝非 HTTP 服务地址。"""
    with pytest.raises(ValidationError, match="base_url must start"):
        load_settings(
            environ={
                "CI_ASSISTANT__KNOWLEDGE__UNLIMITED_OCR__BASE_URL": (
                    "file:///tmp/ocr"
                )
            }
        )


def test_connection_ids_must_be_unique(tmp_path: Path) -> None:
    """验证 ``test_connection_ids_must_be_unique`` 所描述的预期行为。"""
    config_path = tmp_path / "config.yml"
    config_path.write_text(
        """
ci:
  connections:
    - {id: main, type: gitlab, base_url: https://gitlab.example.com, token_env: GITLAB_TOKEN}
    - {id: main, type: jenkins, base_url: https://jenkins.example.com, token_env: JENKINS_TOKEN}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="connection ids must be unique"):
        load_settings(config_path, environ={})


def test_production_rejects_reload_and_missing_ai_settings() -> None:
    """验证 ``test_production_rejects_reload_and_missing_ai_settings`` 所描述的预期行为。"""
    with pytest.raises(ValidationError, match="missing production settings"):
        load_settings(environ={"APP_ENVIRONMENT": "production"})

    with pytest.raises(ValidationError, match="reload cannot be enabled"):
        load_settings(
            environ={
                "APP_ENVIRONMENT": "production",
                "APP_RELOAD": "true",
                "LLM_API_URL": "https://llm.example/v1",
                "LLM_API_KEY": "key",
                "LLM_MODEL": "model",
            }
        )


def test_production_allows_rule_gateway_without_external_ai_settings() -> None:
    """验证 ``test_production_allows_rule_gateway_without_external_ai_settings`` 所描述的预期行为。"""
    settings = load_settings(
        environ={
            "APP_ENVIRONMENT": "production",
            "CI_ASSISTANT__AI__PROVIDER": "rule",
            "API_KEYS_JSON": '{"admin-key":"*"}',
        }
    )

    assert settings.ai.provider == "rule"


def test_api_key_tenant_must_be_uuid_or_admin_wildcard() -> None:
    """验证 ``test_api_key_tenant_must_be_uuid_or_admin_wildcard`` 所描述的预期行为。"""
    with pytest.raises(ValidationError, match="tenant values must be UUIDs"):
        load_settings(
            environ={
                "APP_ENVIRONMENT": "production",
                "CI_ASSISTANT__AI__PROVIDER": "rule",
                "API_KEYS_JSON": '{"key":"not-a-uuid"}',
            }
        )


def test_missing_explicit_config_file_is_an_error(tmp_path: Path) -> None:
    """验证 ``test_missing_explicit_config_file_is_an_error`` 所描述的预期行为。"""
    with pytest.raises(ConfigurationError, match="config file does not exist"):
        load_settings(tmp_path / "missing.yml", environ={})
