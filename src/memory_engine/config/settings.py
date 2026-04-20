from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class InferenceProviderRuntimeConfig(BaseModel):
    provider: Literal["ollama", "openai"]
    enabled: bool = True
    model_name: str
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: float = 30.0
    temperature: float = 0.0
    seed: int | None = 7


class EmbeddingProfileSettings(BaseModel):
    provider: Literal["disabled", "hash", "ollama", "openai"] = "ollama"
    model_name: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: float = 30.0
    dimensions: int | None = None


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
    sensitive_encryption_key: str | None = None
    auth_seed_users: str = (
        "viewer@memoryengine.local:viewer:viewer;"
        "editor@memoryengine.local:editor:editor;"
        "approver@memoryengine.local:approver:approver;"
        "operator@memoryengine.local:operator:operator;"
        "admin@memoryengine.local:admin:admin"
    )
    worker_poll_seconds: int = 2
    embedding_provider: Literal["disabled", "hash", "openai", "ollama"] = "ollama"
    embedding_dimensions: int = 8
    inference_provider_registry: dict[str, InferenceProviderRuntimeConfig] | None = None
    embedding_profile: EmbeddingProfileSettings | None = None
    ollama_base_url: str = "http://localhost:11434"
    ollama_inference_model: str = "gemma4:e4b"
    ollama_embedding_model: str = "qwen3-embedding:0.6b"
    ollama_timeout_seconds: float = 30.0
    ollama_temperature: float = 0.0
    ollama_seed: int | None = 7
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str | None = None
    openai_inference_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-large"
    openai_embedding_dimensions: int | None = None
    default_scope: str = "global"
    default_tenant: str | None = None
    synthetic_test_tenant: str = "tenant_synthetic"
    synthetic_test_user: str = "user_synthetic"
    docs_export_openapi_path: str = "apps/web/src/lib/api/openapi.json"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @model_validator(mode="after")
    def populate_provider_settings(self) -> "Settings":
        if self.inference_provider_registry is None:
            self.inference_provider_registry = {
                "ollama": InferenceProviderRuntimeConfig(
                    provider="ollama",
                    enabled=True,
                    model_name=self.ollama_inference_model,
                    base_url=self.ollama_base_url,
                    timeout_seconds=self.ollama_timeout_seconds,
                    temperature=self.ollama_temperature,
                    seed=self.ollama_seed,
                ),
                "openai": InferenceProviderRuntimeConfig(
                    provider="openai",
                    enabled=True,
                    model_name=self.openai_inference_model,
                    base_url=self.openai_base_url,
                    api_key=self.openai_api_key,
                    timeout_seconds=30.0,
                    temperature=0.0,
                    seed=None,
                ),
            }
        if self.embedding_profile is None:
            if self.embedding_provider == "disabled":
                self.embedding_profile = EmbeddingProfileSettings(provider="disabled")
            elif self.embedding_provider == "hash":
                self.embedding_profile = EmbeddingProfileSettings(
                    provider="hash",
                    model_name=f"hash-{self.embedding_dimensions}",
                    dimensions=self.embedding_dimensions,
                )
            elif self.embedding_provider == "openai":
                self.embedding_profile = EmbeddingProfileSettings(
                    provider="openai",
                    model_name=self.openai_embedding_model,
                    base_url=self.openai_base_url,
                    api_key=self.openai_api_key,
                    timeout_seconds=30.0,
                    dimensions=self.openai_embedding_dimensions,
                )
            else:
                self.embedding_profile = EmbeddingProfileSettings(
                    provider="ollama",
                    model_name=self.ollama_embedding_model,
                    base_url=self.ollama_base_url,
                    timeout_seconds=self.ollama_timeout_seconds,
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
