from __future__ import annotations

import hashlib
import math
from typing import Protocol

import httpx

from memory_engine.config.settings import get_settings


class EmbeddingProvider(Protocol):
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
    def embed(self, text: str) -> list[float] | None:
        return None


class HashEmbeddingProvider:
    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

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
    def __init__(self, api_key: str, model: str, dimensions: int) -> None:
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"input": text, "model": self.model},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        vector = payload["data"][0]["embedding"]
        return _project(vector, self.dimensions)


def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    if settings.embedding_provider == "hash":
        return HashEmbeddingProvider(settings.embedding_dimensions)
    return DisabledEmbeddingProvider()

