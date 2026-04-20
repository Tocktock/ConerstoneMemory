from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx

from memory_engine.config.settings import EmbeddingProfileSettings, get_settings


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str

    def embed(self, text: str) -> list[float] | None: ...


def _normalize(values: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / length for value in values]


def _project(values: list[float], dimensions: int) -> list[float]:
    if len(values) == dimensions:
        return _normalize(values)
    buckets = [0.0] * dimensions
    for index, value in enumerate(values):
        buckets[index % dimensions] += value
    return _normalize(buckets)


class DisabledEmbeddingProvider:
    provider_name = "disabled"
    model_name = "disabled"

    def embed(self, text: str) -> list[float] | None:
        return None


class HashEmbeddingProvider:
    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions
        self.provider_name = "hash"
        self.model_name = f"hash-{dimensions}"

    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = []
        for index in range(self.dimensions):
            chunk = digest[index * 4 : (index + 1) * 4]
            if len(chunk) < 4:
                chunk = (chunk + digest)[:4]
            values.append((int.from_bytes(chunk, "big") / 2**32) * 2 - 1)
        return _normalize(values)


class OpenAIEmbeddingProvider:
    provider_name = "openai"

    def __init__(self, api_key: str, model: str, *, base_url: str, dimensions: int | None, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.model_name = model
        self.base_url = base_url.rstrip("/")
        self.dimensions = dimensions
        self.timeout_seconds = timeout_seconds

    def embed(self, text: str) -> list[float]:
        payload = {"input": text, "model": self.model_name}
        if self.dimensions is not None:
            payload["dimensions"] = self.dimensions
        response = httpx.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        vector = payload["data"][0]["embedding"]
        if self.dimensions is not None:
            return _project(vector, self.dimensions)
        return _normalize(vector)


class OllamaEmbeddingProvider:
    provider_name = "ollama"

    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model
        self.timeout_seconds = timeout_seconds

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            f"{self.base_url}/api/embed",
            headers={"Content-Type": "application/json"},
            json={"model": self.model_name, "input": text},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("embeddings") or []
        if not embeddings:
            raise ValueError("Ollama embedding response did not include embeddings")
        return _normalize(embeddings[0])


def _profile(settings_profile: EmbeddingProfileSettings | None) -> EmbeddingProfileSettings:
    if settings_profile is None:
        return EmbeddingProfileSettings(provider="disabled")
    return settings_profile


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    profile = _profile(settings.embedding_profile)
    if profile.provider == "openai" and profile.api_key and profile.model_name:
        return OpenAIEmbeddingProvider(
            api_key=profile.api_key,
            model=profile.model_name,
            base_url=profile.base_url or settings.openai_base_url,
            dimensions=profile.dimensions,
            timeout_seconds=profile.timeout_seconds,
        )
    if profile.provider == "ollama" and profile.model_name:
        return OllamaEmbeddingProvider(
            base_url=profile.base_url or settings.ollama_base_url,
            model=profile.model_name,
            timeout_seconds=profile.timeout_seconds,
        )
    if profile.provider == "hash":
        return HashEmbeddingProvider(profile.dimensions or settings.embedding_dimensions)
    return DisabledEmbeddingProvider()
