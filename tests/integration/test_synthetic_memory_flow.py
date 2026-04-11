from __future__ import annotations

from sqlalchemy import select

from memory_engine.control.service import get_document_or_404, resolve_snapshot
from memory_engine.db.models import InferenceRun, Memory, RuntimeApiEvent
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


def _ingest_payload(
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
):
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
            "artifact_ref": None,
        },
        "response": {
            "status_code": 200,
            "summary": response_summary,
            "selected_fields": response_fields or {},
            "artifact_ref": None,
        },
    }


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
                "event_match": {
                    "source_system": "profile_service",
                    "http_method": "POST",
                    "route_template": "/v1/profile/address",
                },
                "request_field_selectors": ["$.address"],
                "response_field_selectors": ["$.normalized_address"],
                "normalization_rules": {"primary_fact_source": "request_then_response"},
                "evidence_capture_policy": {"request": "summary_plus_artifact_ref", "response": "summary_only"},
                "llm_usage_mode": "ASSIST",
                "prompt_template_key": "memory.hybrid.ingest.v1",
                "llm_allowed_field_paths": ["$.normalized_fields.address"],
                "llm_blocked_field_paths": [],
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
                "event_match": {
                    "source_system": "search_service",
                    "http_method": "GET",
                    "route_template": "/v1/search",
                },
                "request_field_selectors": ["$.query"],
                "response_field_selectors": [],
                "normalization_rules": {"primary_fact_source": "request_only"},
                "evidence_capture_policy": {"request": "summary_only", "response": "summary_only"},
                "llm_usage_mode": "ASSIST",
                "prompt_template_key": "memory.hybrid.search.v1",
                "llm_allowed_field_paths": ["$.normalized_fields.query"],
                "llm_blocked_field_paths": [],
                "notes": "Synthetic test",
            },
            {
                "api_name": "auth.captureSecret",
                "enabled": True,
                "capability_family": "CONTENT_READ",
                "method_semantics": "READ",
                "domain": "auth",
                "description": "Unsafe secret capture",
                "candidate_memory_types": ["interest.topic"],
                "default_action": "OBSERVE",
                "repeat_policy": "REQUIRED",
                "sensitivity_hint": "S1_INTERNAL",
                "source_trust": 20,
                "source_precedence_key": "repeated_behavioral_signal",
                "extractors": ["topic_extractor"],
                "relation_templates": [],
                "dedup_strategy_hint": "TOPIC_SCORE",
                "conflict_strategy_hint": "NO_DIRECT_CONFLICT",
                "tenant_override_allowed": True,
                "event_match": {
                    "source_system": "auth_service",
                    "http_method": "POST",
                    "route_template": "/v1/auth/capture",
                },
                "request_field_selectors": ["$.token"],
                "response_field_selectors": [],
                "normalization_rules": {"primary_fact_source": "request_only"},
                "evidence_capture_policy": {"request": "summary_only", "response": "summary_only"},
                "llm_usage_mode": "ASSIST",
                "prompt_template_key": "memory.hybrid.ingest.v1",
                "llm_allowed_field_paths": ["$.normalized_fields.token"],
                "llm_blocked_field_paths": [],
                "notes": "Synthetic test",
            },
            {
                "api_name": "memory.forgetUserMemory",
                "enabled": True,
                "capability_family": "DELETE_FORGET",
                "method_semantics": "DELETE",
                "domain": "memory",
                "description": "Forget user memory",
                "candidate_memory_types": [],
                "default_action": "FORGET",
                "repeat_policy": "BYPASS",
                "sensitivity_hint": "S1_INTERNAL",
                "source_trust": 100,
                "source_precedence_key": "explicit_user_write",
                "extractors": [],
                "relation_templates": [],
                "dedup_strategy_hint": "NONE",
                "conflict_strategy_hint": "NO_DIRECT_CONFLICT",
                "tenant_override_allowed": True,
                "event_match": {
                    "source_system": "memory_service",
                    "http_method": "DELETE",
                    "route_template": "/v1/memory",
                },
                "request_field_selectors": [],
                "response_field_selectors": [],
                "normalization_rules": {"primary_fact_source": "request_only"},
                "evidence_capture_policy": {"request": "summary_only", "response": "summary_only"},
                "llm_usage_mode": "DISABLED",
                "prompt_template_key": None,
                "llm_allowed_field_paths": [],
                "llm_blocked_field_paths": [],
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
            },
        },
        "source_precedence": {
            "explicit_user_write": 100,
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

    first_address = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=_ingest_payload(
            tenant_id="tenant_synthetic",
            user_id="user_123",
            session_id="session_a",
            api_name="profile.updateAddress",
            source_system="profile_service",
            http_method="POST",
            route_template="/v1/profile/address",
            request_fields={"address": "123 Seongsu-ro, Seongdong-gu, Seoul"},
            response_fields={"normalized_address": "123 Seongsu-ro, Seongdong-gu, Seoul"},
            request_summary="User submitted a new primary address",
            response_summary="Profile service accepted normalized primary address",
        ),
    ).json()
    assert first_address["decision"]["action"] == "UPSERT"
    assert first_address["decision"]["llm_assist"]["invoked"] is False
    process_next_job(db_session, _bundle_resolver)

    second_address = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=_ingest_payload(
            tenant_id="tenant_synthetic",
            user_id="user_123",
            session_id="session_b",
            api_name="profile.updateAddress",
            source_system="profile_service",
            http_method="POST",
            route_template="/v1/profile/address",
            request_fields={"address": "55 Teheran-ro, Gangnam-gu, Seoul"},
            response_fields={"normalized_address": "55 Teheran-ro, Gangnam-gu, Seoul"},
        ),
    ).json()
    assert second_address["decision"]["action"] == "UPSERT"
    assert second_address["decision"]["llm_assist"]["invoked"] is False
    process_next_job(db_session, _bundle_resolver)

    address_results = client.post(
        "/v1/memory/query",
        headers=headers,
        json={"tenant_id": "tenant_synthetic", "user_id": "user_123", "memory_type": "profile.primary_address"},
    ).json()
    assert len(address_results) == 1
    assert address_results[0]["payload"]["address"] == "55 Teheran-ro, Gangnam-gu, Seoul"
    assert db_session.scalar(select(InferenceRun).where(InferenceRun.source_event_id == first_address["event_id"])) is None
    assert db_session.scalar(select(InferenceRun).where(InferenceRun.source_event_id == second_address["event_id"])) is None

    search_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=_ingest_payload(
            tenant_id="tenant_synthetic",
            user_id="user_123",
            session_id="session_search",
            api_name="search.webSearch",
            source_system="search_service",
            http_method="GET",
            route_template="/v1/search",
            request_fields={"query": "mortgage rates"},
            response_fields={},
            request_summary="User searched for mortgage rates",
            response_summary="Search service returned results",
        ),
    ).json()
    assert search_event["decision"]["action"] == "UPSERT"
    assert search_event["decision"]["reason_codes"] == ["MODEL_LOW_CONFIDENCE_PERSISTED"]
    assert search_event["decision"]["llm_assist"]["invoked"] is True
    process_next_job(db_session, _bundle_resolver)

    inference_run = db_session.scalar(select(InferenceRun).where(InferenceRun.source_event_id == search_event["event_id"]))
    assert inference_run is not None
    assert inference_run.final_action == "UPSERT"
    assert inference_run.llm_confidence < 0.6

    topic_results = client.post(
        "/v1/memory/query",
        headers=headers,
        json={"tenant_id": "tenant_synthetic", "user_id": "user_123", "memory_type": "interest.topic"},
    ).json()
    assert any(item["memory_type"] == "interest.topic" for item in topic_results)

    blocked_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=_ingest_payload(
            tenant_id="tenant_synthetic",
            user_id="user_123",
            session_id="session_secret",
            api_name="auth.captureSecret",
            source_system="auth_service",
            http_method="POST",
            route_template="/v1/auth/capture",
            request_fields={"token": "secret-token"},
            response_fields={},
        ),
    ).json()
    assert blocked_event["decision"]["action"] == "BLOCK"
    assert blocked_event["decision"]["llm_assist"]["invoked"] is False
    assert db_session.scalar(select(InferenceRun).where(InferenceRun.source_event_id == blocked_event["event_id"])) is None
    process_next_job(db_session, _bundle_resolver)

    forget_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=_ingest_payload(
            tenant_id="tenant_synthetic",
            user_id="user_123",
            session_id="session_forget",
            api_name="memory.forgetUserMemory",
            source_system="memory_service",
            http_method="DELETE",
            route_template="/v1/memory",
            request_fields={},
            response_fields={},
        ),
    ).json()
    assert forget_event["decision"]["action"] == "FORGET"
    assert forget_event["decision"]["llm_assist"]["invoked"] is False
    process_next_job(db_session, _bundle_resolver)

    assert db_session.scalar(select(InferenceRun).where(InferenceRun.source_event_id == forget_event["event_id"])) is None
    after_forget = client.post(
        "/v1/memory/query",
        headers=headers,
        json={"tenant_id": "tenant_synthetic", "user_id": "user_123", "memory_type": "profile.primary_address"},
    ).json()
    assert after_forget == []

    search_runtime_event = db_session.scalar(select(RuntimeApiEvent).where(RuntimeApiEvent.event_id == search_event["event_id"]))
    assert search_runtime_event is not None
    assert search_runtime_event.source_system == "search_service"
    assert search_runtime_event.http_method == "GET"
    assert search_runtime_event.route_template == "/v1/search"
    assert search_runtime_event.structured_fields_jsonb == {"query": "mortgage rates"}

    active_memories = list(
        db_session.scalars(
            select(Memory).where(
                Memory.tenant_id == "tenant_synthetic",
                Memory.user_id == "user_123",
                Memory.state == "active",
            )
        )
    )
    assert active_memories == []
