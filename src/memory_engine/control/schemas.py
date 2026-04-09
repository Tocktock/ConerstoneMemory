from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ScopeName = Literal["global", "environment", "tenant", "emergency_override"]
DocumentKind = Literal["api_ontology", "memory_ontology", "policy_profile"]


SENSITIVITY_RANK = {
    "S0_PUBLIC": 0,
    "S1_INTERNAL": 1,
    "S2_PERSONAL": 2,
    "S3_CONFIDENTIAL": 3,
    "S4_RESTRICTED": 4,
}


class APIOntologyEntry(BaseModel):
    api_name: str
    enabled: bool
    capability_family: str
    method_semantics: str
    domain: str
    description: str
    candidate_memory_types: list[str]
    default_action: str
    repeat_policy: str
    sensitivity_hint: str
    source_trust: int
    extractors: list[str]
    relation_templates: list[str]
    dedup_strategy_hint: str
    conflict_strategy_hint: str
    tenant_override_allowed: bool
    notes: str | None = None


class APIOntologyDefinition(BaseModel):
    document_name: str = "API Ontology"
    entries: list[APIOntologyEntry]

    @model_validator(mode="before")
    @classmethod
    def wrap_single_entry(cls, value: Any) -> Any:
        if isinstance(value, dict) and "entries" not in value and "api_name" in value:
            return {"entries": [value]}
        return value


class MemoryOntologyEntry(BaseModel):
    memory_type: str
    enabled: bool
    memory_class: str
    subject_type: str
    object_type: str | None = None
    value_type: str | None = None
    cardinality: str
    identity_strategy: str
    merge_strategy: str
    conflict_strategy: str
    allowed_sensitivity: str
    embed_mode: str
    default_ttl_days: int | None = None
    retrieval_mode: str
    importance_default: float
    tenant_override_allowed: bool
    notes: str | None = None


class MemoryOntologyDefinition(BaseModel):
    document_name: str = "Memory Ontology"
    entries: list[MemoryOntologyEntry]

    @model_validator(mode="before")
    @classmethod
    def wrap_single_entry(cls, value: Any) -> Any:
        if isinstance(value, dict) and "entries" not in value and "memory_type" in value:
            return {"entries": [value]}
        return value


class FrequencyWeightConfig(BaseModel):
    decayed_weight: float
    unique_sessions_30d: float
    unique_days_30d: float
    source_diversity_30d: float


class FrequencyThresholds(BaseModel):
    persist: float
    observe: float


class BurstPenalty(BaseModel):
    enabled: bool
    penalty_value: float
    same_session_ratio_threshold: float


class FrequencyConfig(BaseModel):
    half_life_days: int
    weights: FrequencyWeightConfig
    thresholds: FrequencyThresholds
    burst_penalty: BurstPenalty


class SensitivityConfig(BaseModel):
    hard_block_levels: list[str]
    memory_type_allow_ceiling: dict[str, str]


class ConflictWindowConfig(BaseModel):
    typo_correction_minutes: int


class EmbeddingRulesConfig(BaseModel):
    raw_sensitive_embedding_allowed: bool
    redact_address_detail: bool


class ForgetRulesConfig(BaseModel):
    tombstone_on_delete: bool
    remove_from_retrieval: bool


class PolicyProfileDefinition(BaseModel):
    profile_name: str
    frequency: FrequencyConfig
    sensitivity: SensitivityConfig
    source_precedence: dict[str, int]
    conflict_windows: ConflictWindowConfig
    embedding_rules: EmbeddingRulesConfig
    forget_rules: ForgetRulesConfig


class ConfigDocumentUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    scope: ScopeName = "global"
    tenant_id: str | None = None
    version: int | None = None
    base_version: int | None = None
    definition_json: dict[str, Any] | None = None
    definition_yaml: str | None = None

    @model_validator(mode="after")
    def require_definition(self) -> "ConfigDocumentUpsertRequest":
        if self.definition_json is None and self.definition_yaml is None:
            raise ValueError("definition_json or definition_yaml is required")
        return self


class ConfigDocumentResponse(BaseModel):
    id: str
    kind: DocumentKind
    name: str
    version: int
    status: str
    scope: str
    tenant_id: str | None
    checksum: str
    definition_json: dict[str, Any]
    definition_yaml: str
    created_by: str
    updated_at: str
    approved_by: str | None = None
    published_by: str | None = None


class ValidationIssue(BaseModel):
    id: str
    severity: str
    path: str
    code: str
    message: str
    document_id: str | None = None


class ValidationResponse(BaseModel):
    status: Literal["pass", "warn", "fail"]
    validated_document_ids: list[str]
    issues: list[ValidationIssue]


class ValidateRequest(BaseModel):
    config_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    api_ontology_document_id: str | None = None
    memory_ontology_document_id: str | None = None
    policy_profile_document_id: str | None = None
    environment: str = "dev"
    tenant_id: str | None = None


class ApproveResponse(BaseModel):
    id: str
    status: str
    approved_by: str


class PublishRequest(BaseModel):
    config_id: str | None = None
    api_ontology_document_id: str | None = None
    memory_ontology_document_id: str | None = None
    policy_profile_document_id: str | None = None
    environment: str = "dev"
    scope: ScopeName = "global"
    tenant_id: str | None = None
    release_notes: str = ""


class PublicationResponse(BaseModel):
    id: str
    environment: str
    scope: str
    tenant_id: str | None
    snapshot_hash: str
    is_active: bool
    published_by: str
    published_at: datetime
    rollback_of: str | None = None
    api_ontology_document_id: str
    memory_ontology_document_id: str
    policy_profile_document_id: str


class RollbackRequest(BaseModel):
    snapshot_id: str


class SimulationRequest(BaseModel):
    sample_event: dict[str, Any]
    config_id: str | None = None
    api_ontology_document_id: str | None = None
    memory_ontology_document_id: str | None = None
    policy_profile_document_id: str | None = None
    environment: str = "dev"
    tenant_id: str | None = None


class SimulationResponse(BaseModel):
    active_snapshot_id: str | None
    candidate_snapshot_id: str | None
    old_decision: dict[str, Any] | None
    new_decision: dict[str, Any]
    changed_reason_codes: list[str]
    changed_memory_candidates: list[str]
    expected_write_delta: int
    expected_block_delta: int
