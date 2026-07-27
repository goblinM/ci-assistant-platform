from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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
    return Settings()
