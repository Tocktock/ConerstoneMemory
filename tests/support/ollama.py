from __future__ import annotations

import json
import urllib.error
import urllib.request

from memory_engine.config.settings import get_settings


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _extract_structured_json_text(content: str) -> str:
    candidate = content.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[4:].lstrip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and start < end:
        return candidate[start : end + 1]
    return candidate


def assert_ollama_ready() -> None:
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    with urllib.request.urlopen(f"{base_url}/api/tags", timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    model_names = {item["name"] for item in payload.get("models", []) if isinstance(item, dict) and item.get("name")}
    assert settings.ollama_inference_model in model_names
    assert settings.ollama_embedding_model in model_names
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
    content = ((chat_payload.get("message") or {}).get("content") or "").strip()
    assert content, "Ollama chat ping returned empty content"
    embed_payload = _post_json(
        f"{base_url}/api/embed",
        {"model": settings.ollama_embedding_model, "input": "memory-engine readiness check"},
        timeout=settings.ollama_timeout_seconds,
    )
    embeddings = embed_payload.get("embeddings") or []
    assert embeddings and isinstance(embeddings[0], list), "Ollama embed ping returned no embeddings"


def judge_workflow_intent(
    *,
    scenario_name: str,
    workflow_key: str,
    workflow_title: str,
    workflow_description: str,
    participant_entry_ids: list[str],
    relationship_edges: list[dict[str, str]],
    observed_api_name: str,
    executed_api_names: list[str],
    related_api_ids: list[str],
    intent_summary: str,
) -> dict:
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    response_schema = {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["pass", "fail"]},
            "faithful_to_observed_api": {"type": "boolean"},
            "unobserved_apis_are_context_only": {"type": "boolean"},
            "specific_and_concise": {"type": "boolean"},
            "aligned_with_workflow_definition": {"type": "boolean"},
            "relationship_context_consistent": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": [
            "verdict",
            "faithful_to_observed_api",
            "unobserved_apis_are_context_only",
            "specific_and_concise",
            "aligned_with_workflow_definition",
            "relationship_context_consistent",
            "reason",
        ],
    }
    prompt_payload = {
        "scenario_name": scenario_name,
        "workflow_key": workflow_key,
        "workflow_title": workflow_title,
        "workflow_description": workflow_description,
        "participant_entry_ids": participant_entry_ids,
        "relationship_edges": relationship_edges,
        "observed_api_name": observed_api_name,
        "executed_api_names": executed_api_names,
        "related_api_ids": related_api_ids,
        "intent_summary": intent_summary,
        "instructions": [
            "Judge whether the intent summary is faithful to the observed API and workflow definition.",
            "Unobserved related APIs must be treated as contextual references only, never as executed facts.",
            "The summary should stay specific, concise, and aligned to the workflow.",
            "The related API context should be consistent with the workflow participants and edges.",
        ],
    }
    payload = _post_json(
        f"{base_url}/api/chat",
        {
            "model": settings.ollama_inference_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict MemoryEngine synthetic test judge. "
                        "Return only JSON that matches the provided schema."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt_payload, sort_keys=True)},
            ],
            "stream": False,
            "format": response_schema,
            "options": {"temperature": 0.0, "seed": settings.ollama_seed},
        },
        timeout=settings.ollama_timeout_seconds,
    )
    content = ((payload.get("message") or {}).get("content") or "").strip()
    assert content, "Ollama judge returned empty content"
    return json.loads(_extract_structured_json_text(content))
