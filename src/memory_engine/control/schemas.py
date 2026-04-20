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
PrimaryFactSource = Literal["request_only", "response_only", "request_then_response", "response_then_request"]
EvidenceCaptureMode = Literal["none", "summary_only", "summary_plus_artifact_ref"]
LLMUsageMode = Literal["DISABLED", "ASSIST", "REQUIRE"]
WorkflowEdgeType = Literal[
    "PRECEDES",
    "READS_AFTER_WRITE",
    "ENABLES",
    "COMPENSATES",
    "ALTERNATIVE_TO",
]


SENSITIVITY_RANK = {
    "S0_PUBLIC": 0,
    "S1_INTERNAL": 1,
    "S2_PERSONAL": 2,
    "S3_CONFIDENTIAL": 3,
    "S4_RESTRICTED": 4,
}


class APIOntologyEntry(BaseModel):
    entry_id: str | None = None
    module_key: str | None = None
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
    event_match: "EventMatchConfig"
    request_field_selectors: list[str]
    response_field_selectors: list[str]
    normalization_rules: "NormalizationRulesConfig"
    evidence_capture_policy: "EvidenceCapturePolicyConfig"
    llm_usage_mode: LLMUsageMode = "DISABLED"
    prompt_template_key: str | None = None
    llm_allowed_field_paths: list[str] = Field(default_factory=list)
    llm_blocked_field_paths: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("request_field_selectors", "response_field_selectors", "llm_allowed_field_paths", "llm_blocked_field_paths")
    @classmethod
    def validate_json_paths(cls, value: list[str]) -> list[str]:
        invalid = [item for item in value if not item.startswith("$.")]
        if invalid:
            raise ValueError(f"All selector paths must start with $.: {invalid}")
        return value

    @model_validator(mode="after")
    def validate_llm_fields(self) -> "APIOntologyEntry":
        if not self.entry_id:
            self.entry_id = self.api_name
        if self.llm_usage_mode != "DISABLED" and not self.prompt_template_key:
            raise ValueError("prompt_template_key is required when llm_usage_mode is ASSIST or REQUIRE")
        overlap = set(self.llm_allowed_field_paths) & set(self.llm_blocked_field_paths)
        if overlap:
            raise ValueError(f"llm_allowed_field_paths and llm_blocked_field_paths overlap: {sorted(overlap)}")
        return self


class EventMatchConfig(BaseModel):
    source_system: str = Field(min_length=1)
    http_method: str = Field(min_length=1)
    route_template: str = Field(min_length=1)


class NormalizationRulesConfig(BaseModel):
    primary_fact_source: PrimaryFactSource = "request_then_response"


class EvidenceCapturePolicyConfig(BaseModel):
    request: EvidenceCaptureMode = "summary_only"
    response: EvidenceCaptureMode = "summary_only"


class APIOntologyModule(BaseModel):
    module_key: str
    title: str
    description: str = ""
    entries: list[APIOntologyEntry]


class APIWorkflowRelationshipEdge(BaseModel):
    from_entry_id: str
    to_entry_id: str
    edge_type: WorkflowEdgeType


class APIWorkflowIntentRule(BaseModel):
    observed_entry_ids: list[str]
    summary: str


class APIWorkflowDefinition(BaseModel):
    workflow_key: str
    title: str
    description: str = ""
    participant_entry_ids: list[str]
    relationship_edges: list[APIWorkflowRelationshipEdge] = Field(default_factory=list)
    intent_memory_type: str
    default_intent_summary: str
    intent_rules: list[APIWorkflowIntentRule] = Field(default_factory=list)


class APIOntologyDefinition(BaseModel):
    document_name: str = "API Ontology"
    modules: list[APIOntologyModule] = Field(default_factory=list)
    workflows: list[APIWorkflowDefinition] = Field(default_factory=list)
    entries: list[APIOntologyEntry] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def wrap_single_entry(cls, value: Any) -> Any:
        if isinstance(value, dict) and "entries" not in value and "api_name" in value:
            return {"entries": [value]}
        return value

    @model_validator(mode="after")
    def validate_shape(self) -> "APIOntologyDefinition":
        return self


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


class ProviderGateRule(BaseModel):
    capability_families: list[CapabilityFamily] = Field(default_factory=list)
    llm_usage_modes: list[LLMUsageMode] = Field(default_factory=list)
    memory_types: list[str] = Field(default_factory=list)
    max_sensitivity: SensitivityLevel | None = None
    provider_order: list[str]

    @field_validator("provider_order")
    @classmethod
    def validate_provider_order(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("provider_order must not be empty")
        return value


class ProviderGateConfig(BaseModel):
    default_provider: str
    rules: list[ProviderGateRule] = Field(default_factory=list)


class ModelInferenceConfig(BaseModel):
    enabled: bool
    explicit_write_bypass: bool
    hard_rule_bypass: bool
    require_policy_validation: bool
    low_confidence_threshold: float = Field(ge=0.0, le=1.0)
    allow_low_confidence_persist: bool
    log_reasoning_summary: bool
    provider_gate: ProviderGateConfig

    @model_validator(mode="after")
    def validate_flags(self) -> "ModelInferenceConfig":
        if self.allow_low_confidence_persist and not self.require_policy_validation:
            raise ValueError("allow_low_confidence_persist requires require_policy_validation")
        return self


class PolicyProfileDefinition(BaseModel):
    profile_name: str
    frequency: FrequencyConfig
    sensitivity: SensitivityConfig
    source_precedence: dict[str, int]
    conflict_windows: ConflictWindowConfig
    embedding_rules: EmbeddingRulesConfig
    forget_rules: ForgetRulesConfig
    model_inference: ModelInferenceConfig

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
