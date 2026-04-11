from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from memory_engine.config.settings import get_settings
from memory_engine.runtime.prompts import get_prompt_template
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


class StubInferenceProvider:
    provider_name = "stub"
    model_name = "stub-memory-router-v1"

    def infer(self, request: InferenceRequest) -> InferenceResult:
        template = get_prompt_template(request.api_entry.prompt_template_key or "memory.hybrid.ingest.v1")
        payload = {
            "prompt_template_key": template.key,
            "prompt_version": template.version,
            "prompt_payload": request.prompt_payload,
            "api_name": request.event.api_name,
            "eligible_memory_types": request.eligible_memory_types,
        }
        input_hash = build_inference_input_hash(
            prompt_template_key=template.key,
            prompt_version=template.version,
            prompt_payload=request.prompt_payload,
            api_name=request.event.api_name,
            eligible_memory_types=request.eligible_memory_types,
        )
        meaningful_candidates = [
            candidate for candidate in request.base_candidates if candidate.memory_type in request.eligible_memory_types
        ]
        recommendation: InferenceRecommendation
        confidence: float
        reasoning_summary: str

        if not meaningful_candidates:
            recommendation = "OBSERVE"
            confidence = 0.18
            reasoning_summary = "No policy-eligible candidate could be derived from the normalized envelope."
        elif request.api_entry.capability_family in {"SEARCH_READ", "CONTENT_READ"}:
            recommendation = "UPSERT"
            confidence = 0.34
            reasoning_summary = "Behavioral signal is ambiguous, but candidate extraction is stable enough to assist persistence."
        else:
            recommendation = "UPSERT"
            confidence = 0.74
            reasoning_summary = "Structured evidence strongly supports persistence for the matched API event."

        candidates = [
            candidate.model_copy(update={"confidence": confidence})
            for candidate in meaningful_candidates
        ]
        return InferenceResult(
            provider=self.provider_name,
            model_name=self.model_name,
            prompt_template_key=template.key,
            prompt_version=template.version,
            input_hash=input_hash,
            recommendation=recommendation,
            confidence=confidence,
            reasoning_summary=reasoning_summary,
            candidates=candidates,
        )


class DisabledInferenceProvider:
    provider_name = "disabled"
    model_name = "disabled-inference"

    def infer(self, request: InferenceRequest) -> InferenceResult:
        template = get_prompt_template(request.api_entry.prompt_template_key or "memory.hybrid.ingest.v1")
        return InferenceResult(
            provider=self.provider_name,
            model_name=self.model_name,
            prompt_template_key=template.key,
            prompt_version=template.version,
            input_hash=build_inference_input_hash(
                prompt_template_key=template.key,
                prompt_version=template.version,
                prompt_payload=request.prompt_payload,
                api_name=request.event.api_name,
                eligible_memory_types=request.eligible_memory_types,
            ),
            recommendation="OBSERVE",
            confidence=0.0,
            reasoning_summary="Inference execution is disabled for this environment.",
            candidates=[],
        )


def get_inference_provider() -> InferenceProvider:
    settings = get_settings()
    if settings.inference_provider == "disabled":
        return DisabledInferenceProvider()
    return StubInferenceProvider()
