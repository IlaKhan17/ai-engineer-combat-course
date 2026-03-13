from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openai_api_key: str = "sk-placeholder"
    database_url: str = "sqlite:///./dev.db"
    redis_url: str = "redis://localhost:6379"
    debug: bool = True
    app_name: str = "AI Agent Combat Course"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()