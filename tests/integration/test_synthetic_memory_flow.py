from __future__ import annotations

from memory_engine.control.service import get_document_or_404, resolve_snapshot
from memory_engine.runtime.service import process_next_job


def _auth_headers(client):
    response = client.post("/v1/auth/login", json={"email": "admin@memoryengine.local", "password": "admin"})
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _bundle_resolver(db_session, tenant_id: str | None):
    snapshot = resolve_snapshot(db_session, environment="dev", tenant_id=tenant_id)
    assert snapshot is not None
    return {
        "api_ontology": get_document_or_404(db_session, snapshot.api_ontology_document_id),
        "memory_ontology": get_document_or_404(db_session, snapshot.memory_ontology_document_id),
        "policy_profile": get_document_or_404(db_session, snapshot.policy_profile_document_id),
    }, snapshot


def test_synthetic_memory_flow(client, db_session) -> None:
    headers = _auth_headers(client)

    api_definition = {
        "document_name": "Synthetic API Ontology",
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
                "notes": "Synthetic test",
            },
            {
                "api_name": "docs.openDocument",
                "enabled": True,
                "capability_family": "CONTENT_READ",
                "method_semantics": "READ",
                "domain": "docs",
                "description": "Open document",
                "candidate_memory_types": ["interest.topic"],
                "default_action": "OBSERVE",
                "repeat_policy": "REQUIRED",
                "sensitivity_hint": "S1_INTERNAL",
                "source_trust": 40,
                "source_precedence_key": "repeated_behavioral_signal",
                "extractors": ["topic_extractor"],
                "relation_templates": [],
                "dedup_strategy_hint": "TOPIC_SCORE",
                "conflict_strategy_hint": "NO_DIRECT_CONFLICT",
                "tenant_override_allowed": True,
                "notes": "Synthetic test",
            },
            {
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
                "notes": "Synthetic test",
            },
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
                "source_precedence_key": "structured_business_write",
                "extractors": ["customer_parser"],
                "relation_templates": ["USER_WORKS_WITH_CUSTOMER"],
                "dedup_strategy_hint": "ENTITY_RELATION",
                "conflict_strategy_hint": "DEDUP_BY_CANONICAL_OBJECT",
                "tenant_override_allowed": True,
                "notes": "Synthetic test",
            },
        ],
    }
    memory_definition = {
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
                "embed_mode": "SUMMARY",
                "default_ttl_days": None,
                "retrieval_mode": "RELATION_THEN_VECTOR",
                "importance_default": 0.85,
                "tenant_override_allowed": True,
                "notes": "",
            },
        ],
    }
    policy_definition = {
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
    }

    scoped_payload = {"scope": "tenant", "tenant_id": "tenant_synthetic"}
    api_doc = client.post(
        "/v1/control/api-ontology",
        headers=headers,
        json={**scoped_payload, "definition_json": api_definition},
    ).json()
    memory_doc = client.post(
        "/v1/control/memory-ontology",
        headers=headers,
        json={**scoped_payload, "definition_json": memory_definition},
    ).json()
    policy_doc = client.post(
        "/v1/control/policy-profiles",
        headers=headers,
        json={**scoped_payload, "definition_json": policy_definition},
    ).json()

    validation = client.post(
        "/v1/control/validate",
        headers=headers,
        json={
            "api_ontology_document_id": api_doc["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
            "tenant_id": "tenant_synthetic",
        },
    ).json()
    assert validation["status"] == "pass"

    for document_id in [api_doc["id"], memory_doc["id"], policy_doc["id"]]:
        approve = client.post(f"/v1/control/configs/{document_id}/approve", headers=headers)
        assert approve.status_code == 200

    publish = client.post(
        "/v1/control/publish",
        headers=headers,
        json={
            "api_ontology_document_id": api_doc["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
            "scope": "tenant",
            "tenant_id": "tenant_synthetic",
            "release_notes": "synthetic test",
        },
    ).json()
    assert publish["is_active"] is True
    assert publish["release_notes"] == "synthetic test"
    assert publish["api_ontology_document_id"] == api_doc["id"]

    address_ingest = client.post(
        "/v1/events/ingest",
        headers=headers,
        json={
            "tenant_id": "tenant_synthetic",
            "user_id": "user_123",
            "session_id": "session_a",
            "api_name": "profile.updateAddress",
            "structured_fields": {"address": "123 Seongsu-ro, Seongdong-gu, Seoul"},
        },
    ).json()
    assert address_ingest["decision"]["action"] == "UPSERT"
    process_next_job(db_session, _bundle_resolver)

    address_results = client.post(
        "/v1/memory/query",
        headers=headers,
        json={"tenant_id": "tenant_synthetic", "user_id": "user_123", "memory_type": "profile.primary_address"},
    ).json()
    assert any(item["memory_type"] == "profile.primary_address" for item in address_results)
    assert address_results[0]["payload"]["address"] == "123 Seongsu-ro, Seongdong-gu, Seoul"

    second_address_ingest = client.post(
        "/v1/events/ingest",
        headers=headers,
        json={
            "tenant_id": "tenant_synthetic",
            "user_id": "user_123",
            "session_id": "session_b",
            "api_name": "profile.updateAddress",
            "structured_fields": {"address": "55 Teheran-ro, Gangnam-gu, Seoul"},
        },
    ).json()
    assert second_address_ingest["decision"]["action"] == "UPSERT"
    process_next_job(db_session, _bundle_resolver)

    superseded_address_results = client.post(
        "/v1/memory/query",
        headers=headers,
        json={"tenant_id": "tenant_synthetic", "user_id": "user_123", "memory_type": "profile.primary_address"},
    ).json()
    assert len(superseded_address_results) == 1
    assert superseded_address_results[0]["payload"]["address"] == "55 Teheran-ro, Gangnam-gu, Seoul"

    for index in range(5):
        response = client.post(
            "/v1/events/ingest",
            headers=headers,
            json={
                "tenant_id": "tenant_synthetic",
                "user_id": "user_123",
                "session_id": f"session_{index}",
                "api_name": "docs.openDocument",
                "structured_fields": {"document_title": "Real Estate Tax Guide"},
            },
        )
        assert response.status_code == 200
        process_next_job(db_session, _bundle_resolver)

    topic_results = client.post(
        "/v1/memory/query",
        headers=headers,
        json={"tenant_id": "tenant_synthetic", "user_id": "user_123", "memory_type": "interest.topic"},
    ).json()
    assert any(item["memory_type"] == "interest.topic" for item in topic_results)

    search_response = client.post(
        "/v1/events/ingest",
        headers=headers,
        json={
            "tenant_id": "tenant_synthetic",
            "user_id": "user_123",
            "session_id": "search_one_off",
            "api_name": "search.webSearch",
            "structured_fields": {"query": "one off search"},
        },
    ).json()
    assert search_response["decision"]["action"] == "OBSERVE"
    process_next_job(db_session, _bundle_resolver)
    one_off_results = client.post(
        "/v1/memory/query",
        headers=headers,
        json={"tenant_id": "tenant_synthetic", "user_id": "user_123", "query_text": "one off search"},
    ).json()
    assert all(item["title"] != "one_off_search" for item in one_off_results)

    for customer in ["ABC Corp", "ABC Corporation"]:
        response = client.post(
            "/v1/events/ingest",
            headers=headers,
            json={
                "tenant_id": "tenant_synthetic",
                "user_id": "user_123",
                "session_id": f"crm_{customer}",
                "api_name": "crm.createDeal",
                "structured_fields": {"customer": customer, "domain": "abc.com"},
            },
        )
        assert response.status_code == 200
        process_next_job(db_session, _bundle_resolver)

    relation_results = client.post(
        "/v1/memory/query",
        headers=headers,
        json={"tenant_id": "tenant_synthetic", "user_id": "user_123"},
    ).json()
    relation_items = [item for item in relation_results if item["record_type"] == "relation"]
    assert len(relation_items) == 1

    forget = client.post(
        "/v1/memory/forget",
        headers=headers,
        json={
            "tenant_id": "tenant_synthetic",
            "user_id": "user_123",
            "memory_type": "profile.primary_address",
        },
    )
    assert forget.status_code == 200
    after_forget = client.post(
        "/v1/memory/query",
        headers=headers,
        json={"tenant_id": "tenant_synthetic", "user_id": "user_123", "memory_type": "profile.primary_address"},
    ).json()
    assert after_forget == []
