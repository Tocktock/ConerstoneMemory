from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError

from memory_engine.config.settings import InferenceProviderRuntimeConfig, get_settings
from memory_engine.control.schemas import APIOntologyEntry, PolicyProfileDefinition, SENSITIVITY_RANK
from memory_engine.runtime.prompts import get_prompt_template, render_prompt_payload
from memory_engine.runtime.schemas import CandidateMemory, EventIngestRequest


InferenceRecommendation = Literal["UPSERT", "OBSERVE", "BLOCK"]


@dataclass(frozen=True)
class InferenceRequest:
    event: EventIngestRequest
    normalized_envelope: dict[str, Any]
    prompt_payload: dict[str, Any]
    api_entry: Any
    eligible_memory_types: list[str]
    base_candidates: list[CandidateMemory]


@dataclass(frozen=True)
class InferenceResult:
    provider: str
    model_name: str
    prompt_template_key: str
    prompt_version: str
    input_hash: str
    recommendation: InferenceRecommendation
    confidence: float
    reasoning_summary: str
    candidates: list[CandidateMemory]


class InferenceProvider(Protocol):
    provider_name: str
    model_name: str

    def infer(self, request: InferenceRequest) -> InferenceResult:
        ...


class StructuredInferenceResponse(BaseModel):
    recommendation: InferenceRecommendation
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_summary: str
    candidate_indexes: list[int] = Field(default_factory=list)


def _json_hash(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_inference_input_hash(
    *,
    prompt_template_key: str,
    prompt_version: str,
    prompt_payload: dict[str, Any],
    api_name: str,
    eligible_memory_types: list[str],
) -> str:
    return _json_hash(
        {
            "prompt_template_key": prompt_template_key,
            "prompt_version": prompt_version,
            "prompt_payload": prompt_payload,
            "api_name": api_name,
            "eligible_memory_types": eligible_memory_types,
        }
    )


def _unique(values: list[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value not in ordered:
            ordered.append(value)
    return ordered


def select_inference_provider_ids(
    api_entry: APIOntologyEntry,
    candidates: list[CandidateMemory],
    policy: PolicyProfileDefinition,
) -> list[str]:
    gate = policy.model_inference.provider_gate
    candidate_types = {candidate.memory_type for candidate in candidates}
    max_sensitivity = (
        max((candidate.sensitivity for candidate in candidates), key=lambda item: SENSITIVITY_RANK[item])
        if candidates
        else None
    )
    for rule in gate.rules:
        if rule.capability_families and api_entry.capability_family not in rule.capability_families:
            continue
        if rule.llm_usage_modes and api_entry.llm_usage_mode not in rule.llm_usage_modes:
            continue
        if rule.memory_types and not candidate_types.intersection(rule.memory_types):
            continue
        if (
            rule.max_sensitivity is not None
            and max_sensitivity is not None
            and SENSITIVITY_RANK[max_sensitivity] > SENSITIVITY_RANK[rule.max_sensitivity]
        ):
            continue
        return _unique(rule.provider_order)
    return [gate.default_provider]


def _render_messages(request: InferenceRequest) -> tuple[list[dict[str, str]], str, str]:
    template = get_prompt_template(request.api_entry.prompt_template_key or "memory.hybrid.ingest.v1")
    base_candidates = [
        {
            "index": index,
            "memory_type": candidate.memory_type,
            "canonical_key": candidate.canonical_key,
            "confidence": candidate.confidence,
            "sensitivity": candidate.sensitivity,
            "value": candidate.value,
        }
        for index, candidate in enumerate(request.base_candidates)
    ]
    event_context = {
        "api_name": request.event.api_name,
        "capability_family": request.api_entry.capability_family,
        "method_semantics": request.api_entry.method_semantics,
        "llm_usage_mode": request.api_entry.llm_usage_mode,
        "eligible_memory_types": request.eligible_memory_types,
    }
    return (
        render_prompt_payload(
            template=template,
            event_context=event_context,
            prompt_payload=request.prompt_payload,
            base_candidates=base_candidates,
        ),
        template.key,
        template.version,
    )


def _selection_to_result(
    *,
    selection: StructuredInferenceResponse,
    request: InferenceRequest,
    provider_name: str,
    model_name: str,
    prompt_template_key: str,
    prompt_version: str,
) -> InferenceResult:
    selected_candidates: list[CandidateMemory] = []
    for index in selection.candidate_indexes:
        if index < 0 or index >= len(request.base_candidates):
            continue
        candidate = request.base_candidates[index]
        selected_candidates.append(candidate.model_copy(update={"confidence": max(candidate.confidence, selection.confidence)}))
    return InferenceResult(
        provider=provider_name,
        model_name=model_name,
        prompt_template_key=prompt_template_key,
        prompt_version=prompt_version,
        input_hash=build_inference_input_hash(
            prompt_template_key=prompt_template_key,
            prompt_version=prompt_version,
            prompt_payload=request.prompt_payload,
            api_name=request.event.api_name,
            eligible_memory_types=request.eligible_memory_types,
        ),
        recommendation=selection.recommendation,
        confidence=selection.confidence,
        reasoning_summary=selection.reasoning_summary,
        candidates=selected_candidates,
    )


def _strip_base_url(base_url: str | None, *, fallback: str) -> str:
    return (base_url or fallback).rstrip("/")


def _extract_openai_message_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("OpenAI response missing choices")
    message = (choices[0] or {}).get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
        return "".join(text_parts)
    raise ValueError("OpenAI response missing message content")


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


class OllamaInferenceProvider:
    provider_name = "ollama"

    def __init__(self, config: InferenceProviderRuntimeConfig) -> None:
        self.config = config
        self.model_name = config.model_name
        self.base_url = _strip_base_url(config.base_url, fallback="http://localhost:11434")

    def infer(self, request: InferenceRequest) -> InferenceResult:
        messages, template_key, template_version = _render_messages(request)
        # Live local models can occasionally return truncated structured JSON.
        # Retry once before policy-level fallback changes provider behavior.
        for attempt in range(2):
            try:
                response = httpx.post(
                    f"{self.base_url}/api/chat",
                    headers={"Content-Type": "application/json"},
                    json={
                        "model": self.model_name,
                        "messages": messages,
                        "stream": False,
                        "format": StructuredInferenceResponse.model_json_schema(),
                        "options": {
                            "temperature": self.config.temperature,
                            "seed": self.config.seed,
                        },
                    },
                    timeout=self.config.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                message = payload.get("message") or {}
                content = message.get("content")
                if not isinstance(content, str):
                    raise ValueError("Ollama response missing message content")
                selection = StructuredInferenceResponse.model_validate_json(_extract_structured_json_text(content))
                return _selection_to_result(
                    selection=selection,
                    request=request,
                    provider_name=self.provider_name,
                    model_name=self.model_name,
                    prompt_template_key=template_key,
                    prompt_version=template_version,
                )
            except (httpx.HTTPError, ValidationError, ValueError):
                if attempt == 1:
                    raise
        raise AssertionError("unreachable")


class OpenAIInferenceProvider:
    provider_name = "openai"

    def __init__(self, config: InferenceProviderRuntimeConfig) -> None:
        self.config = config
        if not config.api_key:
            raise ValueError("OpenAI provider requires an API key")
        self.model_name = config.model_name
        self.base_url = _strip_base_url(config.base_url, fallback="https://api.openai.com/v1")

    def infer(self, request: InferenceRequest) -> InferenceResult:
        messages, template_key, template_version = _render_messages(request)
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model_name,
                "temperature": self.config.temperature,
                "messages": messages,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "memory_engine_inference",
                        "schema": StructuredInferenceResponse.model_json_schema(),
                    },
                },
            },
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        selection = StructuredInferenceResponse.model_validate_json(
            _extract_structured_json_text(_extract_openai_message_content(payload))
        )
        return _selection_to_result(
            selection=selection,
            request=request,
            provider_name=self.provider_name,
            model_name=self.model_name,
            prompt_template_key=template_key,
            prompt_version=template_version,
        )


def get_inference_provider(provider_id: str) -> InferenceProvider:
    settings = get_settings()
    config = (settings.inference_provider_registry or {}).get(provider_id)
    if config is None:
        raise ValueError(f"Unknown inference provider id: {provider_id}")
    if not config.enabled:
        raise ValueError(f"Inference provider is disabled: {provider_id}")
    if config.provider == "ollama":
        return OllamaInferenceProvider(config)
    if config.provider == "openai":
        return OpenAIInferenceProvider(config)
    raise ValueError(f"Unsupported inference provider kind: {config.provider}")
