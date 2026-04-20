from __future__ import annotations

from memory_engine.control.service import get_document_or_404, resolve_snapshot


def auth_headers(client, *, email: str = "admin@memoryengine.local", password: str = "admin") -> dict[str, str]:
    response = client.post("/v1/auth/login", json={"email": email, "password": password})
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def base_api_entry(**overrides) -> dict:
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
    entry["entry_id"] = str(overrides.get("entry_id") or entry["api_name"])
    return entry


def base_api_module(
    *,
    module_key: str = "profile.core",
    title: str = "Profile Core",
    description: str = "",
    entries: list[dict] | None = None,
) -> dict:
    return {
        "module_key": module_key,
        "title": title,
        "description": description,
        "entries": entries if entries is not None else [base_api_entry()],
    }


def base_api_package_definition(
    *,
    document_name: str = "Synthetic API Ontology",
    modules: list[dict] | None = None,
    workflows: list[dict] | None = None,
) -> dict:
    return {
        "document_name": document_name,
        "modules": modules if modules is not None else [base_api_module()],
        "workflows": workflows if workflows is not None else [],
    }


def base_memory_definition() -> dict:
    return {
        "document_name": "Synthetic Memory Ontology",
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
            {
                "memory_type": "relationship.customer",
                "enabled": True,
                "memory_class": "relation",
                "subject_type": "User",
                "object_type": "Customer",
                "cardinality": "MANY_UNIQUE_BY_OBJECT",
                "identity_strategy": "user_id + canonical_customer_id",
                "merge_strategy": "EVIDENCE_MERGE",
                "conflict_strategy": "DEDUP_BY_CANONICAL_OBJECT",
                "allowed_sensitivity": "S2_PERSONAL",
                "embed_mode": "DISABLED",
                "default_ttl_days": None,
                "retrieval_mode": "RELATION_THEN_VECTOR",
                "importance_default": 0.7,
                "tenant_override_allowed": True,
                "notes": "",
            },
            {
                "memory_type": "intent.user_goal",
                "enabled": True,
                "memory_class": "fact",
                "subject_type": "User",
                "value_type": "IntentSummary",
                "cardinality": "ONE_ACTIVE",
                "identity_strategy": "user_id + workflow_key",
                "merge_strategy": "MERGE_ATTRIBUTES_WHEN_EQUAL",
                "conflict_strategy": "SUPERSEDE_BY_PRECEDENCE",
                "allowed_sensitivity": "S1_INTERNAL",
                "embed_mode": "SUMMARY",
                "default_ttl_days": None,
                "retrieval_mode": "EXACT_THEN_VECTOR",
                "importance_default": 0.85,
                "tenant_override_allowed": True,
                "notes": "",
            },
        ],
    }


def base_policy_definition(**overrides) -> dict:
    definition = {
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
                "interest.topic": "S1_INTERNAL",
                "profile.primary_address": "S2_PERSONAL",
                "relationship.customer": "S2_PERSONAL",
                "intent.user_goal": "S1_INTERNAL",
            },
        },
        "source_precedence": {
            "explicit_user_write": 100,
            "structured_business_write": 80,
            "repeated_behavioral_signal": 50,
        },
        "conflict_windows": {"typo_correction_minutes": 5},
        "embedding_rules": {"raw_sensitive_embedding_allowed": False, "redact_address_detail": True},
        "forget_rules": {"tombstone_on_delete": True, "remove_from_retrieval": True},
        "model_inference": {
            "enabled": True,
            "explicit_write_bypass": True,
            "hard_rule_bypass": True,
            "require_policy_validation": True,
            "low_confidence_threshold": 0.6,
            "allow_low_confidence_persist": True,
            "log_reasoning_summary": True,
            "provider_gate": {
                "default_provider": "ollama",
                "rules": [
                    {
                        "capability_families": ["SEARCH_READ", "CONTENT_READ"],
                        "llm_usage_modes": ["ASSIST", "REQUIRE"],
                        "memory_types": [],
                        "max_sensitivity": "S1_INTERNAL",
                        "provider_order": ["ollama", "openai"],
                    }
                ],
            },
        },
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(definition.get(key), dict):
            definition[key] = {**definition[key], **value}
        else:
            definition[key] = value
    return definition


def ingest_payload(
    *,
    tenant_id: str,
    user_id: str,
    api_name: str,
    source_system: str,
    http_method: str,
    route_template: str,
    session_id: str,
    request_fields: dict,
    response_fields: dict | None = None,
    request_summary: str = "request summary",
    response_summary: str = "response summary",
    request_artifact: dict | None = None,
    response_artifact: dict | None = None,
) -> dict:
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "session_id": session_id,
        "source_system": source_system,
        "api_name": api_name,
        "http_method": http_method,
        "route_template": route_template,
        "request_id": f"req_{session_id}",
        "trace_id": f"trace_{session_id}",
        "source_channel": "api_gateway",
        "redaction_policy_version": "v1",
        "request": {
            "summary": request_summary,
            "selected_fields": request_fields,
            "artifact_ref": request_artifact,
        },
        "response": {
            "status_code": 200,
            "summary": response_summary,
            "selected_fields": response_fields or {},
            "artifact_ref": response_artifact,
        },
    }


def bundle_resolver(db_session, tenant_id: str | None):
    snapshot = resolve_snapshot(db_session, environment="dev", tenant_id=tenant_id)
    assert snapshot is not None
    return {
        "api_ontology": get_document_or_404(db_session, snapshot.api_ontology_document_id),
        "memory_ontology": get_document_or_404(db_session, snapshot.memory_ontology_document_id),
        "policy_profile": get_document_or_404(db_session, snapshot.policy_profile_document_id),
    }, snapshot
