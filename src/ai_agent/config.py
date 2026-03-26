from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_default_env = REPO_ROOT / ".env"
_fallback_env = REPO_ROOT / ".env.example"
ENV_PATH = _default_env if _default_env.exists() else _fallback_env


class Settings(BaseSettings):
    openai_api_key: str = "sk-placeholder"
    database_url: str = "sqlite:///./dev.db"
    redis_url: str = "redis://localhost:6379"
    debug: bool = True
    app_name: str = "AI Agent Combat Course"

    model_config = {
        "env_file": str(ENV_PATH),
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()