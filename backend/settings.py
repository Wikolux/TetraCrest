from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import EMBEDDING_PROVIDER_OPENAI, VECTOR_STORE_NULL


class Settings(BaseSettings):
    app_name: str = "TetraCrest Enterprise Operating System"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/tetracrest"
    redis_url: str = "redis://localhost:6379/0"
    upload_storage_path: str = "uploads"
    max_upload_size_bytes: int = 10 * 1024 * 1024
    embedding_provider: str = EMBEDDING_PROVIDER_OPENAI
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    openai_api_key: str | None = None
    vector_store_provider: str = VECTOR_STORE_NULL
    vector_store_table: str = "embedding_vectors"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
