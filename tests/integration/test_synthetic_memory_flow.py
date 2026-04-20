from __future__ import annotations

from sqlalchemy import select

from memory_engine.config.settings import get_settings
from memory_engine.db.models import InferenceRun, Memory, MemoryEmbedding, RuntimeApiEvent
from memory_engine.runtime.service import process_next_job
from tests.support.builders import (
    auth_headers,
    base_api_entry,
    base_memory_definition,
    base_policy_definition,
    bundle_resolver,
    ingest_payload,
)
from tests.support.ollama import assert_ollama_ready


def test_synthetic_memory_flow(client, db_session) -> None:
    assert_ollama_ready()
    settings = get_settings()
    headers = auth_headers(client)

    api_definition = {
        "document_name": "Synthetic API Ontology",
        "entries": [
            base_api_entry(
                evidence_capture_policy={"request": "summary_plus_artifact_ref", "response": "summary_only"},
                notes="Synthetic explicit write",
            ),
            base_api_entry(
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
                normalization_rules={"primary_fact_source": "request_only"},
                llm_usage_mode="ASSIST",
                prompt_template_key="memory.hybrid.search.v1",
                llm_allowed_field_paths=["$.normalized_fields.query"],
                notes="Synthetic ambiguous read",
            ),
            base_api_entry(
                api_name="auth.captureSecret",
                capability_family="CONTENT_READ",
                method_semantics="READ",
                candidate_memory_types=["interest.topic"],
                default_action="OBSERVE",
                repeat_policy="REQUIRED",
                sensitivity_hint="S1_INTERNAL",
                source_trust=20,
                source_precedence_key="repeated_behavioral_signal",
                extractors=["topic_extractor"],
                relation_templates=[],
                event_match={
                    "source_system": "auth_service",
                    "http_method": "POST",
                    "route_template": "/v1/auth/capture",
                },
                request_field_selectors=["$.token"],
                response_field_selectors=[],
                normalization_rules={"primary_fact_source": "request_only"},
                llm_usage_mode="ASSIST",
                prompt_template_key="memory.hybrid.ingest.v1",
                llm_allowed_field_paths=["$.normalized_fields.token"],
                notes="Synthetic hard block",
            ),
            base_api_entry(
                api_name="memory.forgetUserMemory",
                capability_family="DELETE_FORGET",
                method_semantics="DELETE",
                candidate_memory_types=[],
                default_action="FORGET",
                repeat_policy="BYPASS",
                sensitivity_hint="S1_INTERNAL",
                source_trust=100,
                source_precedence_key="explicit_user_write",
                extractors=[],
                relation_templates=[],
                event_match={
                    "source_system": "memory_service",
                    "http_method": "DELETE",
                    "route_template": "/v1/memory",
                },
                request_field_selectors=[],
                response_field_selectors=[],
                normalization_rules={"primary_fact_source": "request_only"},
                llm_usage_mode="DISABLED",
                prompt_template_key=None,
                llm_allowed_field_paths=[],
                notes="Synthetic forget",
            ),
        ],
    }
    memory_definition = base_memory_definition()
    policy_definition = base_policy_definition()

    scoped_payload = {"scope": "tenant", "tenant_id": settings.synthetic_test_tenant}
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
            "tenant_id": settings.synthetic_test_tenant,
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
            "tenant_id": settings.synthetic_test_tenant,
            "release_notes": "synthetic provider-gated flow",
        },
    ).json()
    assert publish["is_active"] is True

    first_address = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=settings.synthetic_test_tenant,
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
            request_artifact={
                "uri": "s3://memoryengine/request-artifacts/address-a.json",
                "checksum_sha256": "abc123",
                "size_bytes": 128,
            },
        ),
    ).json()
    assert first_address["decision"]["action"] == "UPSERT"
    assert first_address["decision"]["llm_assist"]["invoked"] is False
    assert first_address["decision"]["config_snapshot_id"] == publish["id"]
    process_next_job(db_session, bundle_resolver)

    runtime_event = db_session.scalar(select(RuntimeApiEvent).where(RuntimeApiEvent.event_id == first_address["event_id"]))
    assert runtime_event is not None
    assert runtime_event.config_snapshot_id == publish["id"]
    assert runtime_event.request_artifact_jsonb["uri"] == "s3://memoryengine/request-artifacts/address-a.json"

    address_memory = db_session.scalar(
        select(Memory).where(
            Memory.tenant_id == settings.synthetic_test_tenant,
            Memory.user_id == "user_123",
            Memory.memory_type == "profile.primary_address",
            Memory.state == "active",
        )
    )
    assert address_memory is not None
    assert address_memory.config_snapshot_id == publish["id"]
    embedding_row = db_session.scalar(
        select(MemoryEmbedding).where(
            MemoryEmbedding.memory_id == address_memory.memory_id,
            MemoryEmbedding.provider == settings.embedding_profile.provider,
            MemoryEmbedding.model_name == settings.embedding_profile.model_name,
        )
    )
    assert embedding_row is not None
    assert embedding_row.dimensions > 0
    assert embedding_row.text_hash

    address_results = client.post(
        "/v1/memory/query",
        headers=headers,
        json={
            "tenant_id": settings.synthetic_test_tenant,
            "user_id": "user_123",
            "memory_type": "profile.primary_address",
        },
    ).json()
    assert len(address_results) == 1
    assert address_results[0]["payload"]["address"] == "123 Seongsu-ro, Seongdong-gu, Seoul"

    search_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=settings.synthetic_test_tenant,
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
    assert search_event["decision"]["llm_assist"]["invoked"] is True
    assert search_event["decision"]["llm_assist"]["provider"] == "ollama"
    assert search_event["decision"]["llm_assist"]["model_name"] == settings.ollama_inference_model
    process_next_job(db_session, bundle_resolver)

    inference_run = db_session.scalar(select(InferenceRun).where(InferenceRun.source_event_id == search_event["event_id"]))
    assert inference_run is not None
    assert inference_run.model_provider == "ollama"
    assert inference_run.model_name == settings.ollama_inference_model
    assert inference_run.config_snapshot_id == publish["id"]

    if inference_run.final_action == "UPSERT":
        topic_results = client.post(
            "/v1/memory/query",
            headers=headers,
            json={
                "tenant_id": settings.synthetic_test_tenant,
                "user_id": "user_123",
                "memory_type": "interest.topic",
            },
        ).json()
        assert any(item["memory_type"] == "interest.topic" for item in topic_results)

    blocked_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=settings.synthetic_test_tenant,
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
    process_next_job(db_session, bundle_resolver)

    forget_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=settings.synthetic_test_tenant,
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
    process_next_job(db_session, bundle_resolver)

    after_forget = client.post(
        "/v1/memory/query",
        headers=headers,
        json={
            "tenant_id": settings.synthetic_test_tenant,
            "user_id": "user_123",
            "memory_type": "profile.primary_address",
        },
    ).json()
    assert after_forget == []
