from __future__ import annotations

import os
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator


class ConfigurationError(ValueError):
    """表示配置文件、Secret 目录或配置结构无法被安全加载。"""


class AppConfig(BaseModel):
    """定义应用环境、监听地址、数据目录和默认租户。"""

    environment: Literal["development", "test", "production"] = "development"
    data_dir: Path = Path("data")
    host: str = "0.0.0.0"
    port: int = Field(default=8080, ge=1, le=65535)
    reload: bool = False
    tenant_id: UUID = UUID("00000000-0000-0000-0000-000000000001")
    tenant_name: str = "Default Tenant"
    tenant_slug: str = "default"


class AIConfig(BaseModel):
    """定义诊断模型网关、凭据、超时和有限重试配置。"""

    provider: str = "openai_compatible"
    base_url: str = ""
    api_key: SecretStr = SecretStr("")
    model: str = ""
    timeout_seconds: float = Field(default=30, gt=0)
    max_retries: int = Field(default=2, ge=0, le=10)


class CIConnectionConfig(BaseModel):
    """定义单个 CI Provider 连接及其凭据环境变量名称。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type: Literal["gitlab", "jenkins", "github"]
    base_url: str
    token_env: str
    username_env: str | None = None
    webhook_secret_env: str | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        """仅接受 HTTP(S) Provider 地址，并移除末尾斜杠。"""
        if not value.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return value.rstrip("/")


class CIConfig(BaseModel):
    """保存平台 CI 连接集合并保证连接 ID 唯一。"""

    connections: list[CIConnectionConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def connection_ids_are_unique(self) -> CIConfig:
        """拒绝重复连接 ID，避免运行期 Provider 被静默覆盖。"""
        ids = [connection.id for connection in self.connections]
        if len(ids) != len(set(ids)):
            raise ValueError("CI connection ids must be unique")
        return self


class DatabaseConfig(BaseModel):
    """定义 PostgreSQL 异步连接及连接池容量边界。"""

    url: SecretStr = SecretStr(
        "postgresql+asyncpg://ci_assistant:ci_assistant@localhost:5432/ci_assistant"
    )
    pool_size: int = Field(default=5, ge=1)
    max_overflow: int = Field(default=10, ge=0)
    pool_timeout_seconds: float = Field(default=30, gt=0)
    echo: bool = False


class RedisConfig(BaseModel):
    """定义 Celery Broker 和短期结果使用的 Redis 地址。"""

    url: SecretStr = SecretStr("redis://localhost:6379/0")


class UnlimitedOCRConfig(BaseModel):
    """独立 Unlimited-OCR 推理服务和文档资源限制。"""

    enabled: bool = False
    base_url: str = "http://unlimited-ocr:10000"
    model: str = "Unlimited-OCR"
    timeout_seconds: float = Field(default=1200, gt=0, le=3600)
    max_file_bytes: int = Field(default=20_000_000, ge=1_000_000)
    max_parsed_chars: int = Field(default=5_000_000, ge=100_000)
    max_pdf_pages: int = Field(default=40, ge=1, le=200)
    max_total_pixels: int = Field(default=100_000_000, ge=1_000_000)
    pdf_dpi: int = Field(default=150, ge=72, le=300)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        """校验 Unlimited-OCR 服务 URL。"""
        if not value.startswith(("http://", "https://")):
            raise ValueError("Unlimited-OCR base_url must start with http:// or https://")
        return value.rstrip("/")


class RerankerConfig(BaseModel):
    """Cross-Encoder/BGE 本地或独立服务配置。"""

    backend: Literal["disabled", "local", "http"] = "disabled"
    base_url: str = "http://reranker:8080"
    endpoint: str = "/rerank"
    model: str = "BAAI/bge-reranker-v2-m3"
    api_key: SecretStr = SecretStr("")
    timeout_seconds: float = Field(default=15, gt=0, le=120)
    candidate_multiplier: int = Field(default=4, ge=2, le=20)
    device: str = "cpu"
    batch_size: int = Field(default=16, ge=1, le=256)
    max_length: int = Field(default=512, ge=64, le=8192)
    revision: str | None = None
    local_files_only: bool = False

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        """校验 Reranker 服务 URL 必须使用 HTTP(S) 协议。"""
        if not value.startswith(("http://", "https://")):
            raise ValueError("Reranker base_url must start with http:// or https://")
        return value.rstrip("/")

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        """校验 Reranker 服务端点为站内绝对路径。"""
        if not value.startswith("/") or value.startswith("//"):
            raise ValueError("Reranker endpoint must be an absolute path")
        return value


class KnowledgeConfig(BaseModel):
    """聚合知识索引、Embedding cache、OCR 和 Reranker 配置。"""

    embedding_model: str = "local-hashing-v1"
    embedding_dimension: int = Field(default=384, ge=64, le=4096)
    index_backend: Literal["faiss"] = "faiss"
    storage_path: Path = Path("data/knowledge")
    context_max_chars: int = Field(default=6000, ge=1000)
    embedding_cache_enabled: bool = True
    embedding_cache_path: Path | None = None
    embedding_cache_max_entries: int = Field(default=100_000, ge=1000)
    unlimited_ocr: UnlimitedOCRConfig = Field(default_factory=UnlimitedOCRConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)


class SecurityConfig(BaseModel):
    """保存 API Key 到租户的敏感映射配置。"""

    api_keys_json: SecretStr = SecretStr("{}")

    def api_keys(self) -> dict[str, str]:
        """解析并校验 API Key 映射；租户值只能是 UUID 或管理员通配符。"""
        try:
            value = json.loads(self.api_keys_json.get_secret_value())
        except json.JSONDecodeError as exc:
            raise ValueError("security.api_keys_json must be valid JSON") from exc
        if not isinstance(value, dict) or not all(
            isinstance(key, str) and isinstance(tenant, str)
            for key, tenant in value.items()
        ):
            raise ValueError("security.api_keys_json must map API keys to tenant UUIDs or '*'")
        for tenant in value.values():
            if tenant != "*":
                try:
                    UUID(tenant)
                except ValueError as exc:
                    raise ValueError(
                        "security.api_keys_json tenant values must be UUIDs or '*'"
                    ) from exc
        return value


class PlatformSettings(BaseModel):
    """聚合平台全部配置，并在生产环境执行额外安全校验。"""

    model_config = ConfigDict(extra="forbid")

    app: AppConfig = Field(default_factory=AppConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    ci: CIConfig = Field(default_factory=CIConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    @model_validator(mode="after")
    def validate_production_settings(self) -> PlatformSettings:
        """禁止生产热重载，并要求模型配置和至少一个租户 API Key。"""
        if self.app.environment != "production":
            return self
        if self.app.reload:
            raise ValueError("Uvicorn reload cannot be enabled in production")
        missing = []
        if self.ai.provider != "rule":
            missing = [
                name
                for name, value in (
                    ("ai.base_url", self.ai.base_url),
                    ("ai.api_key", self.ai.api_key.get_secret_value()),
                    ("ai.model", self.ai.model),
                )
                if not value
            ]
        if missing:
            raise ValueError(f"missing production settings: {', '.join(missing)}")
        if not self.security.api_keys():
            raise ValueError("production requires at least one tenant-scoped API key")
        return self


_ENV_ALIASES: dict[str, tuple[str, ...]] = {
    "APP_ENVIRONMENT": ("app", "environment"),
    "APP_HOST": ("app", "host"),
    "APP_PORT": ("app", "port"),
    "APP_RELOAD": ("app", "reload"),
    "LLM_API_URL": ("ai", "base_url"),
    "LLM_API_KEY": ("ai", "api_key"),
    "LLM_MODEL": ("ai", "model"),
    "LLM_TIMEOUT_SECONDS": ("ai", "timeout_seconds"),
    "LLM_MAX_RETRIES": ("ai", "max_retries"),
    "DATABASE_URL": ("database", "url"),
    "REDIS_URL": ("redis", "url"),
    "RAG_CONTEXT_MAX_CHARS": ("knowledge", "context_max_chars"),
    "API_KEYS_JSON": ("security", "api_keys_json"),
}


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _set_nested(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = target
    for part in path[:-1]:
        current = current.setdefault(part, {})
    current[path[-1]] = value


def _environment_overrides(environ: Mapping[str, str]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for name, value in environ.items():
        if name in _ENV_ALIASES:
            _set_nested(overrides, _ENV_ALIASES[name], value)
        elif name.startswith("CI_ASSISTANT__"):
            path = tuple(part.lower() for part in name.removeprefix("CI_ASSISTANT__").split("__"))
            if all(path):
                _set_nested(overrides, path, value)
    return overrides


def _read_secret_overrides(directory: Path) -> dict[str, Any]:
    if not directory.exists():
        raise ConfigurationError(f"secret directory does not exist: {directory}")
    if not directory.is_dir():
        raise ConfigurationError(f"secret path is not a directory: {directory}")

    secret_values: dict[str, str] = {}
    for path in directory.iterdir():
        if path.is_file():
            secret_values[path.name] = path.read_text(encoding="utf-8").rstrip("\r\n")
    return _environment_overrides(secret_values)


def load_settings(
    config_path: str | Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    secrets_dir: str | Path | None = None,
) -> PlatformSettings:
    """Load defaults < YAML < environment < secret files."""

    environment = os.environ if environ is None else environ
    selected_config = config_path or environment.get("CI_ASSISTANT_CONFIG")
    values: dict[str, Any] = {}

    if selected_config:
        path = Path(selected_config)
        if not path.is_file():
            raise ConfigurationError(f"config file does not exist: {path}")
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ConfigurationError(f"invalid YAML in {path}: {exc}") from exc
        if not isinstance(document, Mapping):
            raise ConfigurationError("config root must be a mapping")
        _deep_merge(values, document)

    _deep_merge(values, _environment_overrides(environment))

    selected_secrets = secrets_dir or environment.get("CI_ASSISTANT_SECRET_DIR")
    if selected_secrets:
        _deep_merge(values, _read_secret_overrides(Path(selected_secrets)))

    return PlatformSettings.model_validate(values)
