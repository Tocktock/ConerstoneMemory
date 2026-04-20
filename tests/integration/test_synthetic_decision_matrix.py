from __future__ import annotations

import pytest
from sqlalchemy import select

from memory_engine.db.models import Relation, RuntimeApiEvent
from memory_engine.runtime.service import process_next_job
from tests.support.builders import (
    auth_headers,
    base_api_entry,
    base_memory_definition,
    base_policy_definition,
    bundle_resolver,
    ingest_payload,
)


def _publish_bundle(client, headers, *, api_definition, memory_definition, policy_definition, tenant_id: str = "tenant_matrix") -> dict:
    scoped_payload = {"scope": "tenant", "tenant_id": tenant_id}
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
            "tenant_id": tenant_id,
        },
    ).json()
    assert validation["status"] == "pass"
    for document_id in [api_doc["id"], memory_doc["id"], policy_doc["id"]]:
        assert client.post(f"/v1/control/configs/{document_id}/approve", headers=headers).status_code == 200
    publication = client.post(
        "/v1/control/publish",
        headers=headers,
        json={
            "api_ontology_document_id": api_doc["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
            "scope": "tenant",
            "tenant_id": tenant_id,
            "release_notes": "matrix publish",
        },
    ).json()
    return {"tenant_id": tenant_id, "publication": publication}


@pytest.mark.parametrize(
    ("primary_fact_source", "request_fields", "response_fields", "expected_address"),
    [
        ("request_only", {"address": "11 Seongsu-ro"}, {"normalized_address": "22 Teheran-ro"}, "11 Seongsu-ro"),
        ("response_only", {"address": "11 Seongsu-ro"}, {"normalized_address": "22 Teheran-ro"}, "22 Teheran-ro"),
        ("request_then_response", {"address": "11 Seongsu-ro"}, {"normalized_address": "22 Teheran-ro"}, "11 Seongsu-ro"),
        ("response_then_request", {"address": "11 Seongsu-ro"}, {"normalized_address": "22 Teheran-ro"}, "22 Teheran-ro"),
    ],
)
def test_atomic_matrix_normalization_sources(
    client,
    db_session,
    primary_fact_source: str,
    request_fields: dict,
    response_fields: dict,
    expected_address: str,
) -> None:
    headers = auth_headers(client)
    api_definition = {
        "document_name": "Matrix API Ontology",
        "entries": [
            base_api_entry(
                normalization_rules={"primary_fact_source": primary_fact_source},
            )
        ],
    }
    published = _publish_bundle(
        client,
        headers,
        api_definition=api_definition,
        memory_definition={
            **base_memory_definition(),
            "entries": [entry for entry in base_memory_definition()["entries"] if entry["memory_type"] == "profile.primary_address"],
        },
        policy_definition=base_policy_definition(),
    )
    response = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=published["tenant_id"],
            user_id="user_norm",
            session_id=f"session_{primary_fact_source}",
            api_name="profile.updateAddress",
            source_system="profile_service",
            http_method="POST",
            route_template="/v1/profile/address",
            request_fields=request_fields,
            response_fields=response_fields,
        ),
    ).json()
    assert response["decision"]["action"] == "UPSERT"
    process_next_job(db_session, bundle_resolver)
    results = client.post(
        "/v1/memory/query",
        headers=headers,
        json={"tenant_id": published["tenant_id"], "user_id": "user_norm", "memory_type": "profile.primary_address"},
    ).json()
    assert results[0]["payload"]["address"] == expected_address


def test_atomic_matrix_artifact_capture_policy(client, db_session) -> None:
    headers = auth_headers(client)
    api_definition = {
        "document_name": "Matrix Artifact API",
        "entries": [
            base_api_entry(evidence_capture_policy={"request": "summary_plus_artifact_ref", "response": "summary_only"}),
        ],
    }
    published = _publish_bundle(
        client,
        headers,
        api_definition=api_definition,
        memory_definition={
            **base_memory_definition(),
            "entries": [entry for entry in base_memory_definition()["entries"] if entry["memory_type"] == "profile.primary_address"],
        },
        policy_definition=base_policy_definition(),
    )
    response = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=published["tenant_id"],
            user_id="user_artifact",
            session_id="session_artifact",
            api_name="profile.updateAddress",
            source_system="profile_service",
            http_method="POST",
            route_template="/v1/profile/address",
            request_fields={"address": "11 Seongsu-ro"},
            response_fields={"normalized_address": "11 Seongsu-ro"},
            request_artifact={"uri": "s3://bucket/address.json", "checksum_sha256": "abc", "size_bytes": 12},
        ),
    ).json()
    process_next_job(db_session, bundle_resolver)
    event = db_session.scalar(select(RuntimeApiEvent).where(RuntimeApiEvent.event_id == response["event_id"]))
    assert event is not None
    assert event.request_artifact_jsonb["uri"] == "s3://bucket/address.json"


def test_atomic_matrix_relation_deduplication(client, db_session) -> None:
    headers = auth_headers(client)
    api_definition = {
        "document_name": "Matrix Relation API",
        "entries": [
            base_api_entry(
                api_name="crm.linkCustomer",
                capability_family="RELATION_WRITE",
                method_semantics="WRITE",
                candidate_memory_types=["relationship.customer"],
                default_action="UPSERT",
                repeat_policy="BYPASS",
                sensitivity_hint="S2_PERSONAL",
                source_trust=90,
                source_precedence_key="structured_business_write",
                extractors=["customer_parser"],
                relation_templates=["relationship.customer"],
                event_match={
                    "source_system": "crm_service",
                    "http_method": "POST",
                    "route_template": "/v1/crm/customer",
                },
                request_field_selectors=["$.customer", "$.domain"],
                response_field_selectors=[],
                normalization_rules={"primary_fact_source": "request_only"},
                llm_usage_mode="DISABLED",
                prompt_template_key=None,
                llm_allowed_field_paths=[],
                notes="Relation dedupe",
            )
        ],
    }
    published = _publish_bundle(
        client,
        headers,
        api_definition=api_definition,
        memory_definition={
            **base_memory_definition(),
            "entries": [entry for entry in base_memory_definition()["entries"] if entry["memory_type"] == "relationship.customer"],
        },
        policy_definition=base_policy_definition(),
    )
    for session_id in ("crm_a", "crm_b"):
        response = client.post(
            "/v1/events/ingest",
            headers=headers,
            json=ingest_payload(
                tenant_id=published["tenant_id"],
                user_id="user_relation",
                session_id=session_id,
                api_name="crm.linkCustomer",
                source_system="crm_service",
                http_method="POST",
                route_template="/v1/crm/customer",
                request_fields={"customer": "ACME Corp", "domain": "acme.com"},
                response_fields={},
            ),
        ).json()
        assert response["decision"]["action"] == "UPSERT"
        process_next_job(db_session, bundle_resolver)
    relations = list(
        db_session.scalars(
            select(Relation).where(Relation.tenant_id == published["tenant_id"], Relation.state == "active")
        )
    )
    assert len(relations) == 1
    assert relations[0].evidence_count == 2
