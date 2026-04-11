from __future__ import annotations

from memory_engine.control.service import validate_definition


def _api_entry(**overrides):
    entry = {
        "api_name": "search.webSearch",
        "enabled": True,
        "capability_family": "SEARCH_READ",
        "method_semantics": "READ",
        "domain": "search",
        "description": "Search",
        "candidate_memory_types": ["interest.topic"],
        "default_action": "OBSERVE",
        "repeat_policy": "REQUIRED",
        "sensitivity_hint": "S1_INTERNAL",
        "source_trust": 30,
        "source_precedence_key": "repeated_behavioral_signal",
        "extractors": ["topic_extractor"],
        "relation_templates": [],
        "dedup_strategy_hint": "TOPIC_SCORE",
        "conflict_strategy_hint": "NO_DIRECT_CONFLICT",
        "tenant_override_allowed": True,
        "event_match": {
            "source_system": "search_service",
            "http_method": "GET",
            "route_template": "/v1/search",
        },
        "request_field_selectors": ["$.query"],
        "response_field_selectors": ["$.result_count"],
        "normalization_rules": {"primary_fact_source": "request_then_response"},
        "evidence_capture_policy": {"request": "summary_only", "response": "summary_only"},
        "llm_usage_mode": "DISABLED",
        "prompt_template_key": None,
        "llm_allowed_field_paths": [],
        "llm_blocked_field_paths": [],
        "notes": "",
    }
    entry.update(overrides)
    return entry


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
            "memory_type_allow_ceiling": {"interest.topic": "S1_INTERNAL", "relationship.customer": "S2_PERSONAL"},
        },
        "source_precedence": {"structured_business_write": 80, "repeated_behavioral_signal": 50},
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


def test_validate_definition_flags_unknown_memory_reference() -> None:
    issues = validate_definition(
        "api_ontology",
        {
            "document_name": "API Ontology",
            "entries": [_api_entry(candidate_memory_types=["interest.missing"])],
        },
        reference_memory_types={"interest.topic"},
    )
    assert any(issue.code == "reference.integrity" for issue in issues)


def test_validate_definition_flags_unknown_precedence_key() -> None:
    issues = validate_definition(
        "api_ontology",
        {
            "document_name": "API Ontology",
            "entries": [
                _api_entry(
                    api_name="crm.createDeal",
                    capability_family="RELATION_WRITE",
                    method_semantics="WRITE",
                    candidate_memory_types=["relationship.customer"],
                    default_action="UPSERT",
                    repeat_policy="BYPASS",
                    sensitivity_hint="S2_PERSONAL",
                    source_trust=90,
                    source_precedence_key="missing_precedence",
                    extractors=["customer_parser"],
                    relation_templates=["USER_WORKS_WITH_CUSTOMER"],
                    event_match={
                        "source_system": "crm_service",
                        "http_method": "POST",
                        "route_template": "/v1/deals",
                    },
                    request_field_selectors=["$.customer", "$.domain"],
                )
            ],
        },
        reference_memory_types={"relationship.customer"},
        policy_definition=_policy_definition(),
    )
    assert any(issue.code == "precedence.unknown" for issue in issues)


def test_validate_definition_flags_selector_without_root_marker() -> None:
    issues = validate_definition(
        "api_ontology",
        {
            "document_name": "API Ontology",
            "entries": [_api_entry(request_field_selectors=["query"])],
        },
        reference_memory_types={"interest.topic"},
        policy_definition=_policy_definition(),
    )
    assert any(issue.code == "value_error" for issue in issues)


def test_validate_definition_flags_unknown_prompt_template() -> None:
    issues = validate_definition(
        "api_ontology",
        {
            "document_name": "API Ontology",
            "entries": [
                _api_entry(
                    llm_usage_mode="ASSIST",
                    prompt_template_key="memory.hybrid.missing.v1",
                    llm_allowed_field_paths=["$.normalized_fields.query"],
                )
            ],
        },
        reference_memory_types={"interest.topic"},
        policy_definition=_policy_definition(),
    )
    assert any(issue.code == "prompt_template.unknown" for issue in issues)


def test_validate_definition_flags_invalid_model_inference_flags() -> None:
    invalid_policy = _policy_definition()
    invalid_policy["model_inference"]["require_policy_validation"] = False
    issues = validate_definition(
        "policy_profile",
        invalid_policy,
    )
    assert any(issue.code == "value_error" for issue in issues)
