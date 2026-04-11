from __future__ import annotations


def _auth_headers(client):
    response = client.post("/v1/auth/login", json={"email": "admin@memoryengine.local", "password": "admin"})
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _api_definition(document_name: str, precedence_key: str = "explicit_user_write") -> dict:
    return {
        "document_name": document_name,
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
                "source_precedence_key": precedence_key,
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
        ],
    }


def _memory_definition() -> dict:
    return {
        "document_name": "Lifecycle Memory Ontology",
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
        ],
    }


def _policy_definition() -> dict:
    return {
        "profile_name": "lifecycle-policy",
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
        },
    }


def test_control_lifecycle_publish_rollback_and_archive(client) -> None:
    headers = _auth_headers(client)

    api_doc = client.post(
        "/v1/control/api-ontology",
        headers=headers,
        json={"name": "Lifecycle API", "definition_json": _api_definition("Lifecycle API")},
    ).json()
    memory_doc = client.post(
        "/v1/control/memory-ontology",
        headers=headers,
        json={"name": "Lifecycle Memory", "definition_json": _memory_definition()},
    ).json()
    policy_doc = client.post(
        "/v1/control/policy-profiles",
        headers=headers,
        json={"name": "Lifecycle Policy", "definition_json": _policy_definition()},
    ).json()

    validation = client.post(
        "/v1/control/validate",
        headers=headers,
        json={
            "api_ontology_document_id": api_doc["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
        },
    ).json()
    assert validation["status"] == "pass"

    for document_id in [api_doc["id"], memory_doc["id"], policy_doc["id"]]:
        assert client.post(f"/v1/control/configs/{document_id}/approve", headers=headers).status_code == 200

    first_publication = client.post(
        "/v1/control/publish",
        headers=headers,
        json={
            "api_ontology_document_id": api_doc["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
            "scope": "global",
            "release_notes": "first publish",
        },
    ).json()
    assert first_publication["is_active"] is True
    assert first_publication["release_notes"] == "first publish"

    revised_api = client.put(
        f"/v1/control/configs/{api_doc['id']}",
        headers=headers,
        json={
            "name": "Lifecycle API v2",
            "scope": "global",
            "definition_json": _api_definition("Lifecycle API v2"),
        },
    ).json()
    assert revised_api["version"] == 2
    assert revised_api["base_version"] == 1
    assert revised_api["status"] == "draft"

    revised_validation = client.post(
        "/v1/control/validate",
        headers=headers,
        json={
            "api_ontology_document_id": revised_api["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
        },
    ).json()
    assert revised_validation["status"] == "pass"
    assert client.post(f"/v1/control/configs/{revised_api['id']}/approve", headers=headers).status_code == 200

    second_publication = client.post(
        "/v1/control/publish",
        headers=headers,
        json={
            "api_ontology_document_id": revised_api["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
            "scope": "global",
            "release_notes": "second publish",
        },
    ).json()
    assert second_publication["is_active"] is True
    assert second_publication["api_ontology_document_version"] == 2

    publications = client.get("/v1/control/publications?environment=dev&scope=global", headers=headers).json()
    assert len(publications) == 2

    rollback = client.post(
        "/v1/control/rollback",
        headers=headers,
        json={"snapshot_id": first_publication["id"]},
    ).json()
    assert rollback["rollback_of"] == first_publication["id"]
    assert rollback["is_active"] is True

    active_publications = client.get(
        "/v1/control/publications?environment=dev&scope=global&is_active=true",
        headers=headers,
    ).json()
    assert len(active_publications) == 1
    assert active_publications[0]["id"] == rollback["id"]

    archive = client.post(f"/v1/control/configs/{revised_api['id']}/archive", headers=headers)
    assert archive.status_code == 200
    assert archive.json()["status"] == "archived"


def test_invalid_document_cannot_reach_publication(client) -> None:
    headers = _auth_headers(client)
    invalid_api = client.post(
        "/v1/control/api-ontology",
        headers=headers,
        json={"name": "Invalid API", "definition_json": _api_definition("Invalid API", precedence_key="missing_precedence")},
    ).json()
    memory_doc = client.post(
        "/v1/control/memory-ontology",
        headers=headers,
        json={"name": "Lifecycle Memory", "definition_json": _memory_definition()},
    ).json()
    policy_doc = client.post(
        "/v1/control/policy-profiles",
        headers=headers,
        json={"name": "Lifecycle Policy", "definition_json": _policy_definition()},
    ).json()

    validation = client.post(
        "/v1/control/validate",
        headers=headers,
        json={
            "api_ontology_document_id": invalid_api["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
        },
    ).json()
    assert validation["status"] == "fail"

    publish = client.post(
        "/v1/control/publish",
        headers=headers,
        json={
            "api_ontology_document_id": invalid_api["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
            "scope": "global",
        },
    )
    assert publish.status_code == 400
