from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ScopeName = Literal["global", "environment", "tenant", "emergency_override"]
DocumentKind = Literal["api_ontology", "memory_ontology", "policy_profile"]
MethodSemantics = Literal["READ", "WRITE", "DELETE"]
CapabilityFamily = Literal[
    "PROFILE_WRITE",
    "PREFERENCE_SET",
    "RELATION_WRITE",
    "ENTITY_UPSERT",
    "CONTENT_READ",
    "SEARCH_READ",
    "DELETE_FORGET",
    "UNKNOWN",
]
DefaultAction = Literal["BLOCK", "OBSERVE", "SESSION", "UPSERT", "FORGET"]
RepeatPolicy = Literal["BYPASS", "REQUIRED"]
MemoryClass = Literal["fact", "relation", "interest", "preference"]
CardinalityMode = Literal["ONE_ACTIVE", "MANY_UNIQUE_BY_OBJECT", "MANY_SCORED", "MANY_VERSIONED"]
MergeStrategy = Literal["MERGE_ATTRIBUTES_WHEN_EQUAL", "EVIDENCE_MERGE", "REINFORCE_SCORE", "REPLACE"]
ConflictStrategy = Literal[
    "SUPERSEDE_BY_PRECEDENCE",
    "DEDUP_BY_CANONICAL_OBJECT",
    "NO_DIRECT_CONFLICT",
    "CONFLICT",
    "REJECT",
]
EmbedMode = Literal["DISABLED", "SUMMARY", "COARSE_SUMMARY_ONLY"]
RetrievalMode = Literal["EXACT", "EXACT_THEN_VECTOR", "RELATION_THEN_VECTOR", "VECTOR_PLUS_FILTER"]
SensitivityLevel = Literal["S0_PUBLIC", "S1_INTERNAL", "S2_PERSONAL", "S3_CONFIDENTIAL", "S4_RESTRICTED"]
DocumentStatus = Literal["draft", "validated", "approved", "published", "archived"]


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
    capability_family: CapabilityFamily
    method_semantics: MethodSemantics
    domain: str
    description: str
    candidate_memory_types: list[str]
    default_action: DefaultAction
    repeat_policy: RepeatPolicy
    sensitivity_hint: SensitivityLevel
    source_trust: int = Field(ge=0, le=100)
    source_precedence_key: str
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
    memory_class: MemoryClass
    subject_type: str
    object_type: str | None = None
    value_type: str | None = None
    cardinality: CardinalityMode
    identity_strategy: str
    merge_strategy: MergeStrategy
    conflict_strategy: ConflictStrategy
    allowed_sensitivity: SensitivityLevel
    embed_mode: EmbedMode
    default_ttl_days: int | None = None
    retrieval_mode: RetrievalMode
    importance_default: float = Field(ge=0.0, le=1.0)
    tenant_override_allowed: bool
    notes: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> "MemoryOntologyEntry":
        if bool(self.object_type) == bool(self.value_type):
            raise ValueError("Exactly one of object_type or value_type must be set")
        if self.cardinality == "MANY_SCORED" and self.merge_strategy != "REINFORCE_SCORE":
            raise ValueError("MANY_SCORED memory types must use REINFORCE_SCORE")
        if self.cardinality == "ONE_ACTIVE" and self.conflict_strategy == "DEDUP_BY_CANONICAL_OBJECT":
            raise ValueError("ONE_ACTIVE memory types cannot use DEDUP_BY_CANONICAL_OBJECT")
        return self


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
    decayed_weight: float = Field(ge=0.0, le=1.0)
    unique_sessions_30d: float = Field(ge=0.0, le=1.0)
    unique_days_30d: float = Field(ge=0.0, le=1.0)
    source_diversity_30d: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_sum(self) -> "FrequencyWeightConfig":
        total = self.decayed_weight + self.unique_sessions_30d + self.unique_days_30d + self.source_diversity_30d
        if round(total, 6) > 1.0:
            raise ValueError("frequency weights must sum to 1.0 or less")
        return self


class FrequencyThresholds(BaseModel):
    persist: float = Field(ge=0.0, le=1.0)
    observe: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "FrequencyThresholds":
        if self.observe > self.persist:
            raise ValueError("observe threshold cannot exceed persist threshold")
        return self


class BurstPenalty(BaseModel):
    enabled: bool
    penalty_value: float = Field(ge=0.0, le=1.0)
    same_session_ratio_threshold: float = Field(ge=0.0, le=1.0)


class FrequencyConfig(BaseModel):
    half_life_days: int = Field(gt=0)
    weights: FrequencyWeightConfig
    thresholds: FrequencyThresholds
    burst_penalty: BurstPenalty


class SensitivityConfig(BaseModel):
    hard_block_levels: list[SensitivityLevel]
    memory_type_allow_ceiling: dict[str, SensitivityLevel]


class ConflictWindowConfig(BaseModel):
    typo_correction_minutes: int = Field(ge=0)


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

    @field_validator("source_precedence")
    @classmethod
    def validate_precedence(cls, value: dict[str, int]) -> dict[str, int]:
        if not value:
            raise ValueError("source_precedence must not be empty")
        for item, score in value.items():
            if score < 0:
                raise ValueError(f"source_precedence[{item}] must be non-negative")
        return value


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
        if self.scope in {"tenant", "emergency_override"} and not self.tenant_id:
            raise ValueError("tenant_id is required for tenant and emergency_override scopes")
        if self.scope in {"global", "environment"} and self.tenant_id is not None:
            raise ValueError("tenant_id is only allowed for tenant and emergency_override scopes")
        return self


class ConfigDocumentResponse(BaseModel):
    id: str
    kind: DocumentKind
    name: str
    version: int
    status: DocumentStatus
    scope: ScopeName
    tenant_id: str | None
    base_version: int | None
    checksum: str
    definition_json: dict[str, Any]
    definition_yaml: str
    created_by: str
    created_at: str
    updated_at: str
    approved_by: str | None = None
    approved_at: str | None = None
    published_by: str | None = None
    published_at: str | None = None


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
    status: DocumentStatus
    approved_by: str
    approved_at: str


class ArchiveResponse(BaseModel):
    id: str
    status: DocumentStatus


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
    scope: ScopeName
    tenant_id: str | None
    snapshot_hash: str
    is_active: bool
    release_notes: str
    published_by: str
    published_at: datetime
    rollback_of: str | None = None
    api_ontology_document_id: str
    memory_ontology_document_id: str
    policy_profile_document_id: str
    api_ontology_document_name: str
    memory_ontology_document_name: str
    policy_profile_document_name: str
    api_ontology_document_version: int
    memory_ontology_document_version: int
    policy_profile_document_version: int


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
