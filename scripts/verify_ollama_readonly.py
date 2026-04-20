from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from memory_engine.config.settings import get_settings


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _request(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(f"Ollama not reachable at {url}: {exc}") from exc


def _post_json(url: str, payload: dict, *, timeout: float) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(f"Ollama request failed at {url}: {exc}") from exc


def main() -> None:
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    payload = _request(f"{base_url}/api/tags")
    model_names = {item["name"] for item in payload.get("models", []) if isinstance(item, dict) and item.get("name")}
    _expect(settings.ollama_inference_model in model_names, f"Missing Ollama inference model: {settings.ollama_inference_model}")
    _expect(settings.ollama_embedding_model in model_names, f"Missing Ollama embedding model: {settings.ollama_embedding_model}")
    chat_payload = _post_json(
        f"{base_url}/api/chat",
        {
            "model": settings.ollama_inference_model,
            "messages": [{"role": "user", "content": "Return exactly OK"}],
            "stream": False,
            "options": {"temperature": 0.0, "seed": settings.ollama_seed},
        },
        timeout=settings.ollama_timeout_seconds,
    )
    chat_content = ((chat_payload.get("message") or {}).get("content") or "").strip()
    _expect(bool(chat_content), f"Ollama chat ping returned empty content for {settings.ollama_inference_model}")
    embed_payload = _post_json(
        f"{base_url}/api/embed",
        {"model": settings.ollama_embedding_model, "input": "memory-engine readiness check"},
        timeout=settings.ollama_timeout_seconds,
    )
    embeddings = embed_payload.get("embeddings") or []
    _expect(
        bool(embeddings and isinstance(embeddings[0], list)),
        f"Ollama embed ping returned no embeddings for {settings.ollama_embedding_model}",
    )
    print(f"PASS ollama {settings.ollama_inference_model}")
    print(f"PASS ollama {settings.ollama_embedding_model}")
    print("PASS ollama chat ping")
    print("PASS ollama embed ping")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive CLI handling
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
