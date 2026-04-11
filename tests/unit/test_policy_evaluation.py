from __future__ import annotations

from memory_engine.runtime.policy import (
    evaluate_event,
    filter_prompt_fields,
    normalize_event_fields,
    validate_candidate_set,
)
from memory_engine.runtime.schemas import CandidateMemory, EventIngestRequest


class DummyDocument:
    def __init__(self, definition_jsonb):
        self.definition_jsonb = definition_jsonb


def _event(api_name: str, *, request_fields=None, response_fields=None, source_system="profile_service", http_method="POST", route_template="/v1/profile/address"):
    return EventIngestRequest(
        tenant_id="tenant_test",
        user_id="user_test",
        session_id="session_test",
        source_system=source_system,
        api_name=api_name,
        http_method=http_method,
        route_template=route_template,
        request={
            "summary": "request summary",
            "selected_fields": request_fields or {},
            "artifact_ref": None,
        },
        response={
            "status_code": 200,
            "summary": "response summary",
            "selected_fields": response_fields or {},
            "artifact_ref": None,
        },
    )


def _api_entry(**overrides):
    entry = {
        "api_name": "profile.updateAddress",
        "enabled": True,
        "capability_family": "PROFILE_WRITE",
        "method_semantics": "WRITE",
        "domain": "profile",
        "description": "Address update",
        "candidate_memory_types": ["profile.primary_address"],
        "default_action": "UPSERT",
        "repeat_policy": "BYPASS",
        "sensitivity_hint": "S2_PERSONAL",
        "source_trust": 100,
        "source_precedence_key": "explicit_user_write",
        "extractors": ["address_parser"],
        "relation_templates": ["USER_HAS_PRIMARY_ADDRESS"],
        "dedup_strategy_hint": "EXACT_SLOT",
        "conflict_strategy_hint": "SUPERSEDE_BY_PRECEDENCE",
        "tenant_override_allowed": True,
        "event_match": {
            "source_system": "profile_service",
            "http_method": "POST",
            "route_template": "/v1/profile/address",
        },
        "request_field_selectors": ["$.address"],
        "response_field_selectors": ["$.normalized_address"],
        "normalization_rules": {"primary_fact_source": "request_then_response"},
        "evidence_capture_policy": {"request": "summary_only", "response": "summary_only"},
        "llm_usage_mode": "ASSIST",
        "prompt_template_key": "memory.hybrid.ingest.v1",
        "llm_allowed_field_paths": ["$.normalized_fields.address"],
        "llm_blocked_field_paths": [],
        "notes": "",
    }
    entry.update(overrides)
    return entry


def _memory_definition():
    return {
        "entries": [
            {
                "memory_type": "profile.primary_address",
                "enabled": True,
                "memory_class": "fact",
                "subject_type": "User",
                "object_type": "Address",
                "cardinality": "ONE_ACTIVE",
                "identity_strategy": "user_id + slot(primary)",
                "merge_strategy": "MERGE_ATTRIBUTES_WHEN_EQUAL",
                "conflict_strategy": "SUPERSEDE_BY_PRECEDENCE",
                "allowed_sensitivity": "S2_PERSONAL",
                "embed_mode": "COARSE_SUMMARY_ONLY",
                "default_ttl_days": None,
                "retrieval_mode": "EXACT_THEN_VECTOR",
                "importance_default": 0.95,
                "tenant_override_allowed": True,
                "notes": "",
            },
            {
                "memory_type": "interest.topic",
                "enabled": True,
                "memory_class": "interest",
                "subject_type": "User",
                "object_type": "Topic",
                "cardinality": "MANY_SCORED",
                "identity_strategy": "user_id + canonical_topic_id",
                "merge_strategy": "REINFORCE_SCORE",
                "conflict_strategy": "NO_DIRECT_CONFLICT",
                "allowed_sensitivity": "S1_INTERNAL",
                "embed_mode": "SUMMARY",
                "default_ttl_days": 180,
                "retrieval_mode": "VECTOR_PLUS_FILTER",
                "importance_default": 0.6,
                "tenant_override_allowed": True,
                "notes": "",
            },
        ]
    }


def _policy_definition():
    return {
        "profile_name": "default-v1",
        "frequency": {
            "half_life_days": 14,
            "weights": {
                "decayed_weight": 0.45,
                "unique_sessions_30d": 0.25,
                "unique_days_30d": 0.20,
                "source_diversity_30d": 0.10,
            },
            "thresholds": {"persist": 0.70, "observe": 0.40},
            "burst_penalty": {
                "enabled": True,
                "penalty_value": 0.25,
                "same_session_ratio_threshold": 0.80,
            },
        },
        "sensitivity": {
            "hard_block_levels": ["S4_RESTRICTED", "S3_CONFIDENTIAL"],
            "memory_type_allow_ceiling": {
                "profile.primary_address": "S2_PERSONAL",
                "interest.topic": "S1_INTERNAL",
            },
        },
        "source_precedence": {
            "explicit_user_write": 100,
            "repeated_behavioral_signal": 50,
        },
        "conflict_windows": {"typo_correction_minutes": 5},
        "embedding_rules": {
            "raw_sensitive_embedding_allowed": False,
            "redact_address_detail": True,
        },
        "forget_rules": {"tombstone_on_delete": True, "remove_from_retrieval": True},
        "model_inference": {
            "enabled": True,
            "explicit_write_bypass": True,
            "hard_rule_bypass": True,
            "require_policy_validation": True,
            "low_confidence_threshold": 0.6,
            "allow_low_confidence_persist": True,
            "log_reasoning_summary": True,
        },
    }


def _bundle(api_entries):
    return {
        "api_ontology": DummyDocument({"entries": api_entries}),
        "memory_ontology": DummyDocument(_memory_definition()),
        "policy_profile": DummyDocument(_policy_definition()),
    }


def test_evaluate_event_explicit_write_bypass_skips_llm_assist() -> None:
    decision = evaluate_event(
        None,
        _event("profile.updateAddress", request_fields={"address": "123 Seongsu-ro"}),
        _bundle([_api_entry()]),
        None,
    )
    assert decision.action == "UPSERT"
    assert "EXPLICIT_WRITE_BYPASS" in decision.reason_codes
    assert decision.llm_assist.invoked is False


def test_evaluate_event_observes_unknown_read_api() -> None:
    decision = evaluate_event(
        None,
        _event(
            "search.readSomething",
            request_fields={},
            source_system="search_service",
            http_method="GET",
            route_template="/v1/search",
        ),
        {
            "api_ontology": DummyDocument({"entries": []}),
            "memory_ontology": DummyDocument({"entries": []}),
            "policy_profile": DummyDocument(_policy_definition()),
        },
        None,
    )
    assert decision.action == "OBSERVE"
    assert "UNKNOWN_API" in decision.reason_codes


def test_evaluate_event_blocks_when_tenant_override_raises_sensitivity() -> None:
    decision = evaluate_event(
        None,
        _event(
            "profile.updateAddress",
            request_fields={
                "address": "123 Seongsu-ro",
                "tenant_override_sensitivity": "S3_CONFIDENTIAL",
            },
        ),
        _bundle([_api_entry()]),
        None,
    )
    assert decision.action == "BLOCK"
    assert "SENSITIVITY_BLOCKED" in decision.reason_codes
    assert decision.llm_assist.invoked is False


def test_normalize_event_fields_for_primary_fact_sources() -> None:
    event = _event(
        "profile.updateAddress",
        request_fields={"address": "request value"},
        response_fields={"address": "response value"},
    )
    assert normalize_event_fields(event, "request_only") == {"address": "request value"}
    assert normalize_event_fields(event, "response_only") == {"address": "response value"}
    assert normalize_event_fields(event, "request_then_response") == {"address": "request value"}
    assert normalize_event_fields(event, "response_then_request") == {"address": "response value"}


def test_filter_prompt_fields_honors_allowed_and_blocked_paths() -> None:
    filtered = filter_prompt_fields(
        {
            "normalized_fields": {"query": "mortgage rates", "token": "secret"},
            "request": {"summary": "search", "selected_fields": {"query": "mortgage rates"}},
        },
        ["$.normalized_fields.query", "$.normalized_fields.token", "$.request.summary"],
        ["$.normalized_fields.token"],
    )
    assert filtered == {
        "normalized_fields": {"query": "mortgage rates"},
        "request": {"summary": "search"},
    }


def test_validate_candidate_set_rejects_ineligible_memory_type() -> None:
    candidates, reason_codes, blocked = validate_candidate_set(
        [
            CandidateMemory(
                memory_type="interest.missing",
                canonical_key="mortgage_rates",
                confidence=0.3,
                sensitivity="S1_INTERNAL",
                value={"topic": "mortgage_rates"},
                extractor="topic_extractor",
                source_trust=30,
                source_precedence_key="repeated_behavioral_signal",
                source_precedence_score=50,
            )
        ],
        {entry["memory_type"]: entry for entry in _memory_definition()["entries"]},
        type("PolicyHolder", (), {"sensitivity": type("SensitivityHolder", (), {"hard_block_levels": ["S4_RESTRICTED", "S3_CONFIDENTIAL"]})()})(),  # type: ignore[arg-type]
    )
    assert candidates == []
    assert "MODEL_INVALID_MEMORY_TYPE" in reason_codes
    assert blocked is False


def test_model_low_confidence_persisted_reason_code() -> None:
    search_entry = _api_entry(
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
    decision = evaluate_event(
        None,
        _event(
            "search.webSearch",
            request_fields={"query": "mortgage rates"},
            source_system="search_service",
            http_method="GET",
            route_template="/v1/search",
        ),
        _bundle([search_entry]),
        None,
    )
    assert decision.action == "UPSERT"
    assert decision.reason_codes == ["MODEL_LOW_CONFIDENCE_PERSISTED"]
    assert decision.llm_assist.invoked is True
    assert decision.llm_assist.confidence is not None and decision.llm_assist.confidence < 0.6
