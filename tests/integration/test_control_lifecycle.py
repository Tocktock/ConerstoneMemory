from __future__ import annotations

from tests.support.builders import (
    auth_headers,
    base_api_entry,
    base_api_module,
    base_api_package_definition,
    base_memory_definition,
    base_policy_definition,
)


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
    definition = base_memory_definition()
    definition["document_name"] = "Lifecycle Memory Ontology"
    definition["entries"] = [entry for entry in definition["entries"] if entry["memory_type"] == "profile.primary_address"]
    return definition


def _policy_definition() -> dict:
    definition = base_policy_definition()
    definition["profile_name"] = "lifecycle-policy"
    definition["sensitivity"]["memory_type_allow_ceiling"] = {"profile.primary_address": "S2_PERSONAL"}
    definition["model_inference"]["provider_gate"]["rules"] = []
    return definition


def _workflow_api_definition(document_name: str, *, register_summary: str) -> dict:
    return base_api_package_definition(
        document_name=document_name,
        modules=[
            base_api_module(
                module_key="orders.lifecycle",
                title="Orders Lifecycle",
                entries=[
                    base_api_entry(
                        entry_id="order.register",
                        api_name="order.register",
                        capability_family="ENTITY_UPSERT",
                        method_semantics="WRITE",
                        candidate_memory_types=["interest.topic"],
                        default_action="UPSERT",
                        repeat_policy="BYPASS",
                        sensitivity_hint="S1_INTERNAL",
                        source_trust=80,
                        source_precedence_key="structured_business_write",
                        extractors=["topic_extractor"],
                        relation_templates=[],
                        dedup_strategy_hint="TOPIC_SCORE",
                        conflict_strategy_hint="NO_DIRECT_CONFLICT",
                        event_match={
                            "source_system": "order_service",
                            "http_method": "POST",
                            "route_template": "/v1/orders",
                        },
                        request_field_selectors=["$.topic"],
                        response_field_selectors=[],
                        normalization_rules={"primary_fact_source": "request_only"},
                        llm_usage_mode="DISABLED",
                        prompt_template_key=None,
                        llm_allowed_field_paths=[],
                        llm_blocked_field_paths=[],
                        notes="workflow lifecycle register",
                    ),
                ],
            ),
            base_api_module(
                module_key="orders.payment",
                title="Orders Payment",
                entries=[
                    base_api_entry(
                        entry_id="payment.charge",
                        api_name="payment.charge",
                        capability_family="ENTITY_UPSERT",
                        method_semantics="WRITE",
                        candidate_memory_types=["interest.topic"],
                        default_action="UPSERT",
                        repeat_policy="BYPASS",
                        sensitivity_hint="S1_INTERNAL",
                        source_trust=80,
                        source_precedence_key="structured_business_write",
                        extractors=["topic_extractor"],
                        relation_templates=[],
                        dedup_strategy_hint="TOPIC_SCORE",
                        conflict_strategy_hint="NO_DIRECT_CONFLICT",
                        event_match={
                            "source_system": "payment_service",
                            "http_method": "POST",
                            "route_template": "/v1/payments/charge",
                        },
                        request_field_selectors=["$.topic"],
                        response_field_selectors=[],
                        normalization_rules={"primary_fact_source": "request_only"},
                        llm_usage_mode="DISABLED",
                        prompt_template_key=None,
                        llm_allowed_field_paths=[],
                        llm_blocked_field_paths=[],
                        notes="workflow lifecycle charge",
                    ),
                ],
            ),
        ],
        workflows=[
            {
                "workflow_key": "order_checkout",
                "title": "Order checkout",
                "description": "Registering an order and charging payment belong to one workflow.",
                "participant_entry_ids": ["order.register", "payment.charge"],
                "relationship_edges": [
                    {
                        "from_entry_id": "order.register",
                        "to_entry_id": "payment.charge",
                        "edge_type": "ENABLES",
                    }
                ],
                "intent_memory_type": "intent.user_goal",
                "default_intent_summary": register_summary,
                "intent_rules": [
                    {
                        "observed_entry_ids": ["order.register"],
                        "summary": register_summary,
                    },
                    {
                        "observed_entry_ids": ["payment.charge"],
                        "summary": "User is completing payment for the order.",
                    },
                ],
            }
        ],
    )


def _workflow_memory_definition() -> dict:
    definition = base_memory_definition()
    definition["document_name"] = "Workflow Lifecycle Memory Ontology"
    definition["entries"] = [
        entry
        for entry in definition["entries"]
        if entry["memory_type"] in {"interest.topic", "intent.user_goal"}
    ]
    return definition


def _workflow_policy_definition() -> dict:
    definition = base_policy_definition()
    definition["profile_name"] = "workflow-lifecycle-policy"
    definition["model_inference"]["provider_gate"]["rules"] = []
    return definition


def test_control_lifecycle_publish_rollback_and_archive(client) -> None:
    headers = auth_headers(client)

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

    first_simulation = client.post(
        "/v1/control/simulate",
        headers=headers,
        json={
            "api_ontology_document_id": api_doc["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
            "sample_event": {
                "tenant_id": "tenant_test",
                "user_id": "user_test",
                "session_id": "session_test",
                "source_system": "profile_service",
                "api_name": "profile.updateAddress",
                "http_method": "POST",
                "route_template": "/v1/profile/address",
                "request": {"summary": "request", "selected_fields": {"address": "123 Seongsu-ro"}, "artifact_ref": None},
                "response": {"status_code": 200, "summary": "response", "selected_fields": {"normalized_address": "123 Seongsu-ro"}, "artifact_ref": None},
            },
        },
    ).json()
    assert first_simulation["active_snapshot_id"] == first_publication["id"]
    assert first_simulation["new_decision"]["config_snapshot_id"] == first_publication["id"]
    assert first_simulation["new_decision"]["action"] == "UPSERT"

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

    second_simulation = client.post(
        "/v1/control/simulate",
        headers=headers,
        json={
            "api_ontology_document_id": revised_api["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
            "sample_event": {
                "tenant_id": "tenant_test",
                "user_id": "user_test",
                "session_id": "session_test",
                "source_system": "profile_service",
                "api_name": "profile.updateAddress",
                "http_method": "POST",
                "route_template": "/v1/profile/address",
                "request": {"summary": "request", "selected_fields": {"address": "123 Seongsu-ro"}, "artifact_ref": None},
                "response": {"status_code": 200, "summary": "response", "selected_fields": {"normalized_address": "123 Seongsu-ro"}, "artifact_ref": None},
            },
        },
    ).json()
    assert second_simulation["active_snapshot_id"] == second_publication["id"]
    assert second_simulation["new_decision"]["config_snapshot_id"] == second_publication["id"]

    publications = client.get("/v1/control/publications?environment=dev&scope=global", headers=headers).json()
    assert len(publications) == 2

    rollback = client.post(
        "/v1/control/rollback",
        headers=headers,
        json={"snapshot_id": first_publication["id"]},
    ).json()
    assert rollback["rollback_of"] == first_publication["id"]
    assert rollback["is_active"] is True

    rollback_simulation = client.post(
        "/v1/control/simulate",
        headers=headers,
        json={
            "environment": "dev",
            "sample_event": {
                "tenant_id": "tenant_test",
                "user_id": "user_test",
                "session_id": "session_test",
                "source_system": "profile_service",
                "api_name": "profile.updateAddress",
                "http_method": "POST",
                "route_template": "/v1/profile/address",
                "request": {"summary": "request", "selected_fields": {"address": "123 Seongsu-ro"}, "artifact_ref": None},
                "response": {"status_code": 200, "summary": "response", "selected_fields": {"normalized_address": "123 Seongsu-ro"}, "artifact_ref": None},
            },
        },
    ).json()
    assert rollback_simulation["active_snapshot_id"] == rollback["id"]
    assert rollback_simulation["new_decision"]["config_snapshot_id"] == rollback["id"]

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
    headers = auth_headers(client)
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


def test_control_lifecycle_rollback_changes_future_workflow_intent_behavior(client) -> None:
    headers = auth_headers(client)

    first_api = client.post(
        "/v1/control/api-ontology",
        headers=headers,
        json={
            "name": "Workflow API v1",
            "definition_json": _workflow_api_definition(
                "Workflow API v1",
                register_summary="User is starting checkout for an order.",
            ),
        },
    ).json()
    memory_doc = client.post(
        "/v1/control/memory-ontology",
        headers=headers,
        json={"name": "Workflow Memory", "definition_json": _workflow_memory_definition()},
    ).json()
    policy_doc = client.post(
        "/v1/control/policy-profiles",
        headers=headers,
        json={"name": "Workflow Policy", "definition_json": _workflow_policy_definition()},
    ).json()

    first_validation = client.post(
        "/v1/control/validate",
        headers=headers,
        json={
            "api_ontology_document_id": first_api["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
        },
    ).json()
    assert first_validation["status"] == "pass"

    for document_id in [first_api["id"], memory_doc["id"], policy_doc["id"]]:
        assert client.post(f"/v1/control/configs/{document_id}/approve", headers=headers).status_code == 200

    first_publication = client.post(
        "/v1/control/publish",
        headers=headers,
        json={
            "api_ontology_document_id": first_api["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
            "scope": "global",
            "release_notes": "workflow v1 publish",
        },
    ).json()

    first_simulation = client.post(
        "/v1/control/simulate",
        headers=headers,
        json={
            "api_ontology_document_id": first_api["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
            "sample_event": {
                "tenant_id": "tenant_test",
                "user_id": "user_test",
                "session_id": "session_test",
                "source_system": "order_service",
                "api_name": "order.register",
                "http_method": "POST",
                "route_template": "/v1/orders",
                "request": {"summary": "request", "selected_fields": {"topic": "order checkout"}, "artifact_ref": None},
                "response": {"status_code": 200, "summary": "response", "selected_fields": {}, "artifact_ref": None},
            },
        },
    ).json()
    assert first_simulation["active_snapshot_id"] == first_publication["id"]
    assert first_simulation["new_decision"]["workflow_key"] == "order_checkout"
    assert first_simulation["new_decision"]["intent_summary"] == "User is starting checkout for an order."

    second_api = client.put(
        f"/v1/control/configs/{first_api['id']}",
        headers=headers,
        json={
            "name": "Workflow API v2",
            "scope": "global",
            "definition_json": _workflow_api_definition(
                "Workflow API v2",
                register_summary="User is placing an order and preparing to pay.",
            ),
        },
    ).json()
    second_validation = client.post(
        "/v1/control/validate",
        headers=headers,
        json={
            "api_ontology_document_id": second_api["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
        },
    ).json()
    assert second_validation["status"] == "pass"
    assert client.post(f"/v1/control/configs/{second_api['id']}/approve", headers=headers).status_code == 200

    second_publication = client.post(
        "/v1/control/publish",
        headers=headers,
        json={
            "api_ontology_document_id": second_api["id"],
            "memory_ontology_document_id": memory_doc["id"],
            "policy_profile_document_id": policy_doc["id"],
            "environment": "dev",
            "scope": "global",
            "release_notes": "workflow v2 publish",
        },
    ).json()

    second_simulation = client.post(
        "/v1/control/simulate",
        headers=headers,
        json={
            "environment": "dev",
            "sample_event": {
                "tenant_id": "tenant_test",
                "user_id": "user_test",
                "session_id": "session_test",
                "source_system": "order_service",
                "api_name": "order.register",
                "http_method": "POST",
                "route_template": "/v1/orders",
                "request": {"summary": "request", "selected_fields": {"topic": "order checkout"}, "artifact_ref": None},
                "response": {"status_code": 200, "summary": "response", "selected_fields": {}, "artifact_ref": None},
            },
        },
    ).json()
    assert second_simulation["active_snapshot_id"] == second_publication["id"]
    assert second_simulation["new_decision"]["intent_summary"] == "User is placing an order and preparing to pay."

    rollback = client.post(
        "/v1/control/rollback",
        headers=headers,
        json={"snapshot_id": first_publication["id"]},
    ).json()
    rollback_simulation = client.post(
        "/v1/control/simulate",
        headers=headers,
        json={
            "environment": "dev",
            "sample_event": {
                "tenant_id": "tenant_test",
                "user_id": "user_test",
                "session_id": "session_test",
                "source_system": "order_service",
                "api_name": "order.register",
                "http_method": "POST",
                "route_template": "/v1/orders",
                "request": {"summary": "request", "selected_fields": {"topic": "order checkout"}, "artifact_ref": None},
                "response": {"status_code": 200, "summary": "response", "selected_fields": {}, "artifact_ref": None},
            },
        },
    ).json()
    assert rollback_simulation["active_snapshot_id"] == rollback["id"]
    assert rollback_simulation["new_decision"]["intent_summary"] == "User is starting checkout for an order."
