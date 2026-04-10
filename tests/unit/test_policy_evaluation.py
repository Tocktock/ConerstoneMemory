from __future__ import annotations

from memory_engine.runtime.policy import evaluate_event
from memory_engine.runtime.schemas import EventIngestRequest


class DummyDocument:
    def __init__(self, definition_jsonb):
        self.definition_jsonb = definition_jsonb


def test_evaluate_event_blocks_restricted_sensitivity() -> None:
    bundle = {
        "api_ontology": DummyDocument(
            {
                "entries": [
                    {
                        "api_name": "profile.updateAddress",
                        "enabled": True,
                        "capability_family": "PROFILE_WRITE",
                        "method_semantics": "WRITE",
                        "domain": "profile",
                        "description": "Address update",
                        "candidate_memory_types": ["profile.primary_address"],
                        "default_action": "UPSERT",
                        "repeat_policy": "BYPASS",
                        "sensitivity_hint": "S4_RESTRICTED",
                        "source_trust": 100,
                        "source_precedence_key": "explicit_user_write",
                        "extractors": ["address_parser"],
                        "relation_templates": ["USER_HAS_PRIMARY_ADDRESS"],
                        "dedup_strategy_hint": "EXACT_SLOT",
                        "conflict_strategy_hint": "SUPERSEDE_BY_PRECEDENCE",
                        "tenant_override_allowed": True,
                        "notes": "",
                    }
                ]
            }
        ),
        "memory_ontology": DummyDocument(
            {
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
                    }
                ]
            }
        ),
        "policy_profile": DummyDocument(
            {
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
                    "memory_type_allow_ceiling": {"profile.primary_address": "S2_PERSONAL"},
                },
                "source_precedence": {"explicit_user_write": 100},
                "conflict_windows": {"typo_correction_minutes": 5},
                "embedding_rules": {
                    "raw_sensitive_embedding_allowed": False,
                    "redact_address_detail": True,
                },
                "forget_rules": {"tombstone_on_delete": True, "remove_from_retrieval": True},
            }
        ),
    }
    decision = evaluate_event(
        None,
        EventIngestRequest(
            tenant_id="tenant_test",
            user_id="user_test",
            api_name="profile.updateAddress",
            structured_fields={"address": "123 Seongsu-ro"},
        ),
        bundle,
        None,
    )
    assert decision.action == "BLOCK"
    assert "SENSITIVITY_BLOCKED" in decision.reason_codes


def test_evaluate_event_observes_unknown_read_api() -> None:
    decision = evaluate_event(
        None,
        EventIngestRequest(
            tenant_id="tenant_test",
            user_id="user_test",
            api_name="search.readSomething",
            structured_fields={},
        ),
        {
            "api_ontology": DummyDocument({"entries": []}),
            "memory_ontology": DummyDocument({"entries": []}),
            "policy_profile": DummyDocument(
                {
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
                        "memory_type_allow_ceiling": {},
                    },
                    "source_precedence": {"explicit_user_write": 100},
                    "conflict_windows": {"typo_correction_minutes": 5},
                    "embedding_rules": {
                        "raw_sensitive_embedding_allowed": False,
                        "redact_address_detail": True,
                    },
                    "forget_rules": {"tombstone_on_delete": True, "remove_from_retrieval": True},
                }
            ),
        },
        None,
    )
    assert decision.action == "OBSERVE"
    assert "UNKNOWN_API" in decision.reason_codes


def test_evaluate_event_blocks_when_tenant_override_raises_sensitivity() -> None:
    bundle = {
        "api_ontology": DummyDocument(
            {
                "entries": [
                    {
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
                        "notes": "",
                    }
                ]
            }
        ),
        "memory_ontology": DummyDocument(
            {
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
                    }
                ]
            }
        ),
        "policy_profile": DummyDocument(
            {
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
                    "memory_type_allow_ceiling": {"profile.primary_address": "S2_PERSONAL"},
                },
                "source_precedence": {"explicit_user_write": 100},
                "conflict_windows": {"typo_correction_minutes": 5},
                "embedding_rules": {
                    "raw_sensitive_embedding_allowed": False,
                    "redact_address_detail": True,
                },
                "forget_rules": {"tombstone_on_delete": True, "remove_from_retrieval": True},
            }
        ),
    }
    decision = evaluate_event(
        None,
        EventIngestRequest(
            tenant_id="tenant_test",
            user_id="user_test",
            api_name="profile.updateAddress",
            structured_fields={
                "address": "123 Seongsu-ro",
                "tenant_override_sensitivity": "S3_CONFIDENTIAL",
            },
        ),
        bundle,
        None,
    )
    assert decision.action == "BLOCK"
    assert "SENSITIVITY_BLOCKED" in decision.reason_codes
