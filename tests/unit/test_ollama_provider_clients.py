from __future__ import annotations

import json

from memory_engine.control.schemas import APIOntologyEntry, PolicyProfileDefinition
from memory_engine.runtime.inference import (
    InferenceRequest,
    OllamaInferenceProvider,
    OpenAIInferenceProvider,
    select_inference_provider_ids,
)
from memory_engine.runtime.schemas import CandidateMemory, EventIngestRequest
from memory_engine.worker.embeddings import OllamaEmbeddingProvider
from tests.support.builders import base_api_entry, base_policy_definition


class DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def _request() -> InferenceRequest:
    return InferenceRequest(
        event=EventIngestRequest(
            tenant_id="tenant_test",
            user_id="user_test",
            session_id="session_test",
            source_system="search_service",
            api_name="search.webSearch",
            http_method="GET",
            route_template="/v1/search",
            request={
                "summary": "search request",
                "selected_fields": {"query": "mortgage rates"},
                "artifact_ref": None,
            },
            response={
                "status_code": 200,
                "summary": "search response",
                "selected_fields": {},
                "artifact_ref": None,
            },
        ),
        normalized_envelope={"normalized_fields": {"query": "mortgage rates"}},
        prompt_payload={"normalized_fields": {"query": "mortgage rates"}},
        api_entry=APIOntologyEntry.model_validate(
            base_api_entry(
                api_name="search.webSearch",
                capability_family="SEARCH_READ",
                method_semantics="READ",
                candidate_memory_types=["interest.topic"],
                default_action="OBSERVE",
                repeat_policy="REQUIRED",
                sensitivity_hint="S1_INTERNAL",
                source_trust=30,
                source_precedence_key="repeated_behavioral_signal",
                extractors=["topic_extractor"],
                relation_templates=[],
                event_match={
                    "source_system": "search_service",
                    "http_method": "GET",
                    "route_template": "/v1/search",
                },
                request_field_selectors=["$.query"],
                response_field_selectors=[],
                llm_usage_mode="ASSIST",
                prompt_template_key="memory.hybrid.search.v1",
                llm_allowed_field_paths=["$.normalized_fields.query"],
            )
        ),
        eligible_memory_types=["interest.topic"],
        base_candidates=[
            CandidateMemory(
                memory_type="interest.topic",
                canonical_key="mortgage_rates",
                confidence=0.3,
                sensitivity="S1_INTERNAL",
                value={"topic": "mortgage_rates", "raw": "mortgage rates"},
                extractor="topic_extractor",
                source_trust=30,
                source_precedence_key="repeated_behavioral_signal",
                source_precedence_score=50,
            )
        ],
    )


def test_select_inference_provider_ids_uses_matching_rule() -> None:
    definition = base_policy_definition()
    definition["model_inference"]["provider_gate"]["rules"][0]["memory_types"] = ["interest.topic"]
    policy = PolicyProfileDefinition.model_validate(definition)
    provider_ids = select_inference_provider_ids(_request().api_entry, _request().base_candidates, policy)
    assert provider_ids == ["ollama", "openai"]


def test_ollama_inference_provider_builds_chat_request_and_parses_response(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return DummyResponse(
            {
                "message": {
                    "content": json_module.dumps(
                        {
                            "recommendation": "UPSERT",
                            "confidence": 0.42,
                            "reasoning_summary": "Ambiguous interest persists after review.",
                            "candidate_indexes": [0],
                        }
                    )
                }
            }
        )

    json_module = json
    monkeypatch.setattr("httpx.post", fake_post)
    provider = OllamaInferenceProvider(
        type(
            "Config",
            (),
            {
                "model_name": "gemma4:e4b",
                "base_url": "http://localhost:11434",
                "timeout_seconds": 30.0,
                "temperature": 0.0,
                "seed": 7,
            },
        )()
    )
    result = provider.infer(_request())
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["json"]["model"] == "gemma4:e4b"
    assert result.provider == "ollama"
    assert result.candidates[0].memory_type == "interest.topic"
    assert result.confidence == 0.42


def test_ollama_inference_provider_retries_once_on_invalid_structured_output(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return DummyResponse({"message": {"content": "{\"recommendation\":\"UPSERT\""}})
        return DummyResponse(
            {
                "message": {
                    "content": json_module.dumps(
                        {
                            "recommendation": "UPSERT",
                            "confidence": 0.42,
                            "reasoning_summary": "Ambiguous interest persists after review.",
                            "candidate_indexes": [0],
                        }
                    )
                }
            }
        )

    json_module = json
    monkeypatch.setattr("httpx.post", fake_post)
    provider = OllamaInferenceProvider(
        type(
            "Config",
            (),
            {
                "model_name": "gemma4:e4b",
                "base_url": "http://localhost:11434",
                "timeout_seconds": 30.0,
                "temperature": 0.0,
                "seed": 7,
            },
        )()
    )
    result = provider.infer(_request())
    assert calls["count"] == 2
    assert result.provider == "ollama"


def test_ollama_inference_provider_extracts_json_from_markdown_wrapped_content(monkeypatch) -> None:
    def fake_post(url, headers=None, json=None, timeout=None):
        return DummyResponse(
            {
                "message": {
                    "content": """Here is the structured response.

```json
{
  "recommendation": "UPSERT",
  "confidence": 0.42,
  "reasoning_summary": "Ambiguous interest persists after review.",
  "candidate_indexes": [0]
}
```""",
                }
            }
        )

    monkeypatch.setattr("httpx.post", fake_post)
    provider = OllamaInferenceProvider(
        type(
            "Config",
            (),
            {
                "model_name": "gemma4:e4b",
                "base_url": "http://localhost:11434",
                "timeout_seconds": 30.0,
                "temperature": 0.0,
                "seed": 7,
            },
        )()
    )
    result = provider.infer(_request())
    assert result.provider == "ollama"
    assert result.candidates[0].memory_type == "interest.topic"
    assert result.confidence == 0.42


def test_openai_inference_provider_parses_chat_completion(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return DummyResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json_module.dumps(
                                {
                                    "recommendation": "OBSERVE",
                                    "confidence": 0.2,
                                    "reasoning_summary": "Not enough confidence.",
                                    "candidate_indexes": [],
                                }
                            )
                        }
                    }
                ]
            }
        )

    json_module = json
    monkeypatch.setattr("httpx.post", fake_post)
    provider = OpenAIInferenceProvider(
        type(
            "Config",
            (),
            {
                "model_name": "gpt-5-mini",
                "base_url": "https://api.openai.com/v1",
                "api_key": "test-key",
                "timeout_seconds": 30.0,
                "temperature": 0.0,
                "seed": None,
            },
        )()
    )
    result = provider.infer(_request())
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["json"]["model"] == "gpt-5-mini"
    assert result.provider == "openai"
    assert result.recommendation == "OBSERVE"


def test_openai_inference_provider_requires_api_key_at_construction() -> None:
    try:
        OpenAIInferenceProvider(
            type(
                "Config",
                (),
                {
                    "model_name": "gpt-5-mini",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": None,
                    "timeout_seconds": 30.0,
                    "temperature": 0.0,
                    "seed": None,
                },
            )()
        )
    except ValueError as exc:
        assert str(exc) == "OpenAI provider requires an API key"
    else:
        raise AssertionError("expected missing OpenAI API key to fail provider construction")


def test_ollama_embedding_provider_hits_embed_endpoint(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return DummyResponse({"embeddings": [[0.5, 0.5, 0.5]]})

    monkeypatch.setattr("httpx.post", fake_post)
    provider = OllamaEmbeddingProvider("http://localhost:11434", "qwen3-embedding:0.6b", 30.0)
    vector = provider.embed("hello world")
    assert captured["url"] == "http://localhost:11434/api/embed"
    assert captured["json"]["model"] == "qwen3-embedding:0.6b"
    assert vector is not None and len(vector) == 3
