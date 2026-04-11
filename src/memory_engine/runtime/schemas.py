from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uri: str
    checksum_sha256: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)


class EventPayloadSide(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str | None = None
    selected_fields: dict[str, Any] = Field(default_factory=dict)
    artifact_ref: ArtifactRef | None = None


class EventResponseSide(EventPayloadSide):
    status_code: int | None = None


class EventIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str
    user_id: str
    session_id: str | None = None
    occurred_at: datetime | None = None
    source_system: str
    api_name: str
    http_method: str
    route_template: str
    request_id: str | None = None
    trace_id: str | None = None
    source_channel: str | None = None
    redaction_policy_version: str | None = None
    request: EventPayloadSide
    response: EventResponseSide


class CandidateMemory(BaseModel):
    memory_type: str
    canonical_key: str
    confidence: float
    sensitivity: str
    field_sensitivity_tags: list[str] = Field(default_factory=list)
    classifier_sensitivity: str = "S1_INTERNAL"
    value: dict[str, Any]
    relation_type: str | None = None
    extractor: str
    source_trust: int
    source_precedence_key: str
    source_precedence_score: int


class LLMAssistSummary(BaseModel):
    invoked: bool
    inference_id: str | None = None
    provider: str | None = None
    model_name: str | None = None
    prompt_template_key: str | None = None
    prompt_version: str | None = None
    recommendation: str | None = None
    confidence: float | None = None
    reasoning_summary: str | None = None


class DecisionEnvelope(BaseModel):
    config_snapshot_id: str | None
    event_id: str
    action: str
    reason_codes: list[str]
    candidates: list[CandidateMemory]
    repeat_score: float = 0.0
    llm_assist: LLMAssistSummary = Field(default_factory=lambda: LLMAssistSummary(invoked=False))


class MemoryQueryRequest(BaseModel):
    tenant_id: str
    user_id: str
    memory_type: str | None = None
    query_text: str | None = None
    top_k: int = 10


class ForgetRequest(BaseModel):
    tenant_id: str
    user_id: str
    memory_type: str | None = None
    canonical_key: str | None = None
    relation_type: str | None = None


class QueryResult(BaseModel):
    record_type: str
    record_id: str
    memory_type: str
    title: str
    state: str
    confidence: float
    importance: float
    sensitivity: str
    config_snapshot_id: str
    evidence_count: int
    tenant_id: str
    scope: str
    environment: str
    semantic_relevance: float
    recency_score: float
    final_score: float
    payload: dict[str, Any]
