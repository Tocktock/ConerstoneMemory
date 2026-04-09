from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEMORYENGINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MemoryEngine"
    environment: Literal["dev", "staging", "prod"] = "dev"
    database_url: str = (
        "postgresql+psycopg://memoryengine:memoryengine@localhost:5433/memoryengine"
    )
    auth_secret: str = "dev-secret-change-me"
    auth_token_ttl_minutes: int = 480
    auth_seed_users: str = (
        "viewer@memoryengine.local:viewer:viewer;"
        "editor@memoryengine.local:editor:editor;"
        "approver@memoryengine.local:approver:approver;"
        "operator@memoryengine.local:operator:operator;"
        "admin@memoryengine.local:admin:admin"
    )
    worker_poll_seconds: int = 2
    embedding_provider: Literal["disabled", "hash", "openai"] = "hash"
    embedding_dimensions: int = 8
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    default_scope: str = "global"
    default_tenant: str | None = None
    synthetic_test_tenant: str = "tenant_synthetic"
    synthetic_test_user: str = "user_synthetic"
    docs_export_openapi_path: str = "apps/web/src/lib/api/openapi.json"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
