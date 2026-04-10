from __future__ import annotations

from memory_engine.control.service import validate_definition


def test_validate_definition_flags_unknown_memory_reference() -> None:
    issues = validate_definition(
        "api_ontology",
        {
            "document_name": "API Ontology",
            "entries": [
                {
                    "api_name": "search.webSearch",
                    "enabled": True,
                    "capability_family": "SEARCH_READ",
                    "method_semantics": "READ",
                    "domain": "search",
                    "description": "Search",
                    "candidate_memory_types": ["interest.missing"],
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
                    "notes": "",
                }
            ],
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
                {
                    "api_name": "crm.createDeal",
                    "enabled": True,
                    "capability_family": "RELATION_WRITE",
                    "method_semantics": "WRITE",
                    "domain": "crm",
                    "description": "Create deal",
                    "candidate_memory_types": ["relationship.customer"],
                    "default_action": "UPSERT",
                    "repeat_policy": "BYPASS",
                    "sensitivity_hint": "S2_PERSONAL",
                    "source_trust": 90,
                    "source_precedence_key": "missing_precedence",
                    "extractors": ["customer_parser"],
                    "relation_templates": ["USER_WORKS_WITH_CUSTOMER"],
                    "dedup_strategy_hint": "ENTITY_RELATION",
                    "conflict_strategy_hint": "DEDUP_BY_CANONICAL_OBJECT",
                    "tenant_override_allowed": True,
                    "notes": "",
                }
            ],
        },
        reference_memory_types={"relationship.customer"},
        policy_definition={
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
                "memory_type_allow_ceiling": {"relationship.customer": "S2_PERSONAL"},
            },
            "source_precedence": {"structured_business_write": 80},
            "conflict_windows": {"typo_correction_minutes": 5},
            "embedding_rules": {
                "raw_sensitive_embedding_allowed": False,
                "redact_address_detail": True,
            },
            "forget_rules": {"tombstone_on_delete": True, "remove_from_retrieval": True},
        },
    )
    assert any(issue.code == "precedence.unknown" for issue in issues)
