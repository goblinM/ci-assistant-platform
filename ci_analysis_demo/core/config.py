from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """定义旧兼容接口的模型、GitLab 和本地 RAG 环境配置。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "ai-ci-assistant"
    llm_api_url: str
    llm_api_key: str
    llm_model: str = "your-model-name"
    llm_timeout_seconds: float = 20.0
    llm_max_retries: int = 2

    gitlab_base_url: str = "https://gitlab.example.com"
    gitlab_private_token: str = ""
    gitlab_timeout_seconds: float = 20

    retrieve_top_k: int = 3
    rag_min_score: float = 0.25
    rag_candidate_multiplier: int = 4
    rag_context_max_chars: int = 6000


@lru_cache
def get_settings() -> Settings:
    """获取 ``get_settings`` 对应的数据。"""
    return Settings()
