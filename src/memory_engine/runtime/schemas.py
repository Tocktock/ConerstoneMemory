from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EventIngestRequest(BaseModel):
    tenant_id: str
    user_id: str
    session_id: str | None = None
    api_name: str
    structured_fields: dict[str, Any] = Field(default_factory=dict)
    request_summary: str | None = None
    response_summary: str | None = None
    occurred_at: datetime | None = None


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


class DecisionEnvelope(BaseModel):
    config_snapshot_id: str | None
    event_id: str
    action: str
    reason_codes: list[str]
    candidates: list[CandidateMemory]
    repeat_score: float = 0.0


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
