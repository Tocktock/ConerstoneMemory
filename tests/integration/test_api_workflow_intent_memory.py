from __future__ import annotations

from typing import Any

from tests.support.builders import (
    auth_headers,
    base_api_entry,
    base_api_module,
    base_api_package_definition,
    base_memory_definition,
    base_policy_definition,
    bundle_resolver,
    ingest_payload,
)
from memory_engine.runtime.service import process_next_job
from tests.support.ollama import assert_ollama_ready, judge_workflow_intent


def _workflow_entry(
    *,
    entry_id: str,
    api_name: str,
    source_system: str,
    http_method: str,
    route_template: str,
    module_key: str,
    method_semantics: str = "WRITE",
) -> dict:
    return base_api_entry(
        entry_id=entry_id,
        api_name=api_name,
        capability_family="ENTITY_UPSERT" if method_semantics == "WRITE" else "CONTENT_READ",
        method_semantics=method_semantics,
        candidate_memory_types=["interest.topic"],
        default_action="UPSERT" if method_semantics == "WRITE" else "OBSERVE",
        repeat_policy="BYPASS" if method_semantics == "WRITE" else "REQUIRED",
        sensitivity_hint="S1_INTERNAL",
        source_trust=80 if method_semantics == "WRITE" else 30,
        source_precedence_key="structured_business_write" if method_semantics == "WRITE" else "repeated_behavioral_signal",
        extractors=["topic_extractor"],
        relation_templates=[],
        dedup_strategy_hint="TOPIC_SCORE",
        conflict_strategy_hint="NO_DIRECT_CONFLICT",
        event_match={
            "source_system": source_system,
            "http_method": http_method,
            "route_template": route_template,
        },
        request_field_selectors=["$.topic"],
        response_field_selectors=[],
        normalization_rules={"primary_fact_source": "request_only"},
        llm_usage_mode="DISABLED",
        prompt_template_key=None,
        llm_allowed_field_paths=[],
        llm_blocked_field_paths=[],
        module_key=module_key,
        notes="workflow integration entry",
    )


def _workflow_api_definition(document_name: str) -> dict:
    return base_api_package_definition(
        document_name=document_name,
        modules=[
            base_api_module(
                module_key="orders.lifecycle",
                title="Orders Lifecycle",
                entries=[
                    _workflow_entry(
                        entry_id="order.register",
                        api_name="order.register",
                        source_system="order_service",
                        http_method="POST",
                        route_template="/v1/orders",
                        module_key="orders.lifecycle",
                    ),
                    _workflow_entry(
                        entry_id="order.get",
                        api_name="order.get",
                        source_system="order_service",
                        http_method="GET",
                        route_template="/v1/orders/{orderId}",
                        module_key="orders.lifecycle",
                        method_semantics="READ",
                    ),
                    _workflow_entry(
                        entry_id="order.search",
                        api_name="order.search",
                        source_system="order_service",
                        http_method="GET",
                        route_template="/v1/orders/search",
                        module_key="orders.lifecycle",
                        method_semantics="READ",
                    ),
                ],
            ),
            base_api_module(
                module_key="orders.payment",
                title="Orders Payment",
                entries=[
                    _workflow_entry(
                        entry_id="payment.charge",
                        api_name="payment.charge",
                        source_system="payment_service",
                        http_method="POST",
                        route_template="/v1/payments/charge",
                        module_key="orders.payment",
                    ),
                    _workflow_entry(
                        entry_id="payment.refund",
                        api_name="payment.refund",
                        source_system="payment_service",
                        http_method="POST",
                        route_template="/v1/payments/refund",
                        module_key="orders.payment",
                    ),
                ],
            ),
        ],
        workflows=[
            {
                "workflow_key": "order_checkout",
                "title": "Order checkout",
                "description": "Order registration, retrieval, charge, and refund form one checkout workflow.",
                "participant_entry_ids": [
                    "order.register",
                    "order.get",
                    "payment.charge",
                    "payment.refund",
                ],
                "relationship_edges": [
                    {
                        "from_entry_id": "order.register",
                        "to_entry_id": "order.get",
                        "edge_type": "READS_AFTER_WRITE",
                    },
                    {
                        "from_entry_id": "order.register",
                        "to_entry_id": "payment.charge",
                        "edge_type": "ENABLES",
                    },
                    {
                        "from_entry_id": "payment.refund",
                        "to_entry_id": "payment.charge",
                        "edge_type": "COMPENSATES",
                    },
                ],
                "intent_memory_type": "intent.user_goal",
                "default_intent_summary": "User is trying to place an order and complete payment.",
                "intent_rules": [
                    {
                        "observed_entry_ids": ["order.register"],
                        "summary": "User is trying to place an order and complete payment.",
                    },
                    {
                        "observed_entry_ids": ["payment.charge"],
                        "summary": "User is completing checkout and charging payment for an order.",
                    },
                    {
                        "observed_entry_ids": ["payment.refund"],
                        "summary": "User is correcting a prior checkout by refunding payment.",
                    },
                ],
            }
        ],
    )


def _publish_bundle(client, headers, *, tenant_id: str) -> dict:
    scoped_payload = {"scope": "tenant", "tenant_id": tenant_id}
    memory_definition = base_memory_definition()
    memory_definition["entries"] = [
        entry
        for entry in memory_definition["entries"]
        if entry["memory_type"] in {"interest.topic", "intent.user_goal"}
    ]
    api_doc = client.post(
        "/v1/control/api-ontology",
        headers=headers,
        json={**scoped_payload, "definition_json": _workflow_api_definition("Workflow Intent Package")},
    ).json()
    memory_doc = client.post(
        "/v1/control/memory-ontology",
        headers=headers,
        json={**scoped_payload, "definition_json": memory_definition},
    ).json()
    policy_doc = client.post(
        "/v1/control/policy-profiles",
        headers=headers,
        json={**scoped_payload, "definition_json": base_policy_definition()},
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
            "release_notes": "workflow intent package publish",
        },
    ).json()
    return {"tenant_id": tenant_id, "publication": publication}


def _workflow_metadata() -> dict[str, Any]:
    definition = _workflow_api_definition("Workflow Intent Package")
    return definition["workflows"][0]


def _assert_intent_judgment(
    *,
    scenario_name: str,
    observed_api_name: str,
    executed_api_names: list[str],
    related_api_ids: list[str],
    intent_summary: str,
) -> None:
    workflow = _workflow_metadata()
    judgment = judge_workflow_intent(
        scenario_name=scenario_name,
        workflow_key=workflow["workflow_key"],
        workflow_title=workflow["title"],
        workflow_description=workflow["description"],
        participant_entry_ids=workflow["participant_entry_ids"],
        relationship_edges=workflow["relationship_edges"],
        observed_api_name=observed_api_name,
        executed_api_names=executed_api_names,
        related_api_ids=related_api_ids,
        intent_summary=intent_summary,
    )
    assert judgment["verdict"] == "pass", judgment["reason"]
    assert judgment["faithful_to_observed_api"] is True, judgment
    assert judgment["unobserved_apis_are_context_only"] is True, judgment
    assert judgment["specific_and_concise"] is True, judgment
    assert judgment["aligned_with_workflow_definition"] is True, judgment
    assert judgment["relationship_context_consistent"] is True, judgment


def test_workflow_intent_memory_updates_and_preserves_related_api_links(client, db_session) -> None:
    headers = auth_headers(client)
    tenant_id = "tenant_workflow_intent"
    published = _publish_bundle(client, headers, tenant_id=tenant_id)

    register_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=tenant_id,
            user_id="user_checkout",
            session_id="session_register",
            api_name="order.register",
            source_system="order_service",
            http_method="POST",
            route_template="/v1/orders",
            request_fields={"topic": "order checkout"},
            response_fields={},
        ),
    ).json()
    assert register_event["decision"]["action"] == "UPSERT"
    assert register_event["decision"]["module_key"] == "orders.lifecycle"
    assert register_event["decision"]["workflow_key"] == "order_checkout"
    assert register_event["decision"]["related_api_ids"] == ["order.get", "payment.charge"]
    assert register_event["decision"]["intent_summary"] == "User is trying to place an order and complete payment."

    first_job = process_next_job(db_session, bundle_resolver)
    assert first_job is not None
    first_intent_memory_id = first_job.result_jsonb["workflow_intent_memory_id"]
    assert first_intent_memory_id is not None

    decision_records = client.get(f"/v1/memory/decisions?tenant={tenant_id}", headers=headers).json()
    assert decision_records[0]["workflow_key"] == "order_checkout"
    assert decision_records[0]["related_api_ids"] == ["order.get", "payment.charge"]
    assert decision_records[0]["intent_summary"] == "User is trying to place an order and complete payment."

    first_memories = client.get(
        f"/v1/memory/users/user_checkout?tenant_id={tenant_id}",
        headers=headers,
    ).json()
    first_intent_memory = next(item for item in first_memories if item["memory_type"] == "intent.user_goal")
    assert first_intent_memory["memory_id"] == first_intent_memory_id
    assert first_intent_memory["value"] == {
        "summary": "User is trying to place an order and complete payment.",
        "workflow_key": "order_checkout",
        "observed_api_name": "order.register",
        "related_api_ids": ["order.get", "payment.charge"],
        "evidence_event_ids": [register_event["event_id"]],
    }

    timeline = client.get(
        f"/v1/memory/users/user_checkout/timeline?tenant_id={tenant_id}",
        headers=headers,
    ).json()
    assert [item["api_name"] for item in timeline] == ["order.register"]

    charge_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=tenant_id,
            user_id="user_checkout",
            session_id="session_charge",
            api_name="payment.charge",
            source_system="payment_service",
            http_method="POST",
            route_template="/v1/payments/charge",
            request_fields={"topic": "order checkout"},
            response_fields={},
        ),
    ).json()
    assert charge_event["decision"]["workflow_key"] == "order_checkout"
    assert charge_event["decision"]["intent_summary"] == "User is completing checkout and charging payment for an order."

    second_job = process_next_job(db_session, bundle_resolver)
    assert second_job is not None
    assert second_job.result_jsonb["workflow_intent_memory_id"] == first_intent_memory_id

    second_memories = client.get(
        f"/v1/memory/users/user_checkout?tenant_id={tenant_id}",
        headers=headers,
    ).json()
    second_intent_memory = next(item for item in second_memories if item["memory_type"] == "intent.user_goal")
    assert second_intent_memory["memory_id"] == first_intent_memory_id
    assert second_intent_memory["value"]["summary"] == "User is completing checkout and charging payment for an order."
    assert second_intent_memory["value"]["workflow_key"] == "order_checkout"
    assert sorted(second_intent_memory["value"]["related_api_ids"]) == [
        "order.get",
        "order.register",
        "payment.charge",
        "payment.refund",
    ]
    assert sorted(second_intent_memory["value"]["evidence_event_ids"]) == sorted(
        [register_event["event_id"], charge_event["event_id"]]
    )

    refund_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=tenant_id,
            user_id="user_checkout",
            session_id="session_refund",
            api_name="payment.refund",
            source_system="payment_service",
            http_method="POST",
            route_template="/v1/payments/refund",
            request_fields={"topic": "refund order checkout"},
            response_fields={},
        ),
    ).json()
    assert refund_event["decision"]["workflow_key"] == "order_checkout"
    assert refund_event["decision"]["intent_summary"] == "User is correcting a prior checkout by refunding payment."

    third_job = process_next_job(db_session, bundle_resolver)
    assert third_job is not None
    assert third_job.result_jsonb["workflow_intent_memory_id"] == first_intent_memory_id

    final_memories = client.get(
        f"/v1/memory/users/user_checkout?tenant_id={tenant_id}",
        headers=headers,
    ).json()
    final_intent_memory = next(item for item in final_memories if item["memory_type"] == "intent.user_goal")
    assert final_intent_memory["memory_id"] == first_intent_memory_id
    assert final_intent_memory["value"]["summary"] == "User is correcting a prior checkout by refunding payment."
    assert sorted(final_intent_memory["value"]["evidence_event_ids"]) == sorted(
        [register_event["event_id"], charge_event["event_id"], refund_event["event_id"]]
    )

    final_timeline = client.get(
        f"/v1/memory/users/user_checkout/timeline?tenant_id={tenant_id}",
        headers=headers,
    ).json()
    assert [item["api_name"] for item in final_timeline] == [
        "payment.refund",
        "payment.charge",
        "order.register",
    ]
    assert all(item["api_name"] != "order.get" for item in final_timeline)
    assert published["publication"]["id"] == register_event["decision"]["config_snapshot_id"]


def test_workflow_intent_ai_judge_and_non_workflow_regression(client, db_session) -> None:
    assert_ollama_ready()
    headers = auth_headers(client)
    tenant_id = "tenant_workflow_intent_ai"
    _publish_bundle(client, headers, tenant_id=tenant_id)

    register_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=tenant_id,
            user_id="user_checkout_ai",
            session_id="session_register_ai",
            api_name="order.register",
            source_system="order_service",
            http_method="POST",
            route_template="/v1/orders",
            request_fields={"topic": "order checkout"},
            response_fields={},
        ),
    ).json()
    assert register_event["decision"]["workflow_key"] == "order_checkout"
    process_next_job(db_session, bundle_resolver)
    _assert_intent_judgment(
        scenario_name="order register -> order checkout intent",
        observed_api_name="order.register",
        executed_api_names=["order.register"],
        related_api_ids=register_event["decision"]["related_api_ids"],
        intent_summary=register_event["decision"]["intent_summary"],
    )

    charge_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=tenant_id,
            user_id="user_checkout_ai",
            session_id="session_charge_ai",
            api_name="payment.charge",
            source_system="payment_service",
            http_method="POST",
            route_template="/v1/payments/charge",
            request_fields={"topic": "order checkout"},
            response_fields={},
        ),
    ).json()
    assert charge_event["decision"]["workflow_key"] == "order_checkout"
    process_next_job(db_session, bundle_resolver)
    second_memories = client.get(
        f"/v1/memory/users/user_checkout_ai?tenant_id={tenant_id}",
        headers=headers,
    ).json()
    second_intent_memory = next(item for item in second_memories if item["memory_type"] == "intent.user_goal")
    _assert_intent_judgment(
        scenario_name="order register + payment charge -> stronger checkout intent",
        observed_api_name="payment.charge",
        executed_api_names=["order.register", "payment.charge"],
        related_api_ids=second_intent_memory["value"]["related_api_ids"],
        intent_summary=second_intent_memory["value"]["summary"],
    )

    refund_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=tenant_id,
            user_id="user_checkout_ai",
            session_id="session_refund_ai",
            api_name="payment.refund",
            source_system="payment_service",
            http_method="POST",
            route_template="/v1/payments/refund",
            request_fields={"topic": "refund order checkout"},
            response_fields={},
        ),
    ).json()
    assert refund_event["decision"]["workflow_key"] == "order_checkout"
    process_next_job(db_session, bundle_resolver)
    final_memories = client.get(
        f"/v1/memory/users/user_checkout_ai?tenant_id={tenant_id}",
        headers=headers,
    ).json()
    final_intent_memory = next(item for item in final_memories if item["memory_type"] == "intent.user_goal")
    _assert_intent_judgment(
        scenario_name="payment refund after charge -> corrective intent",
        observed_api_name="payment.refund",
        executed_api_names=["order.register", "payment.charge", "payment.refund"],
        related_api_ids=final_intent_memory["value"]["related_api_ids"],
        intent_summary=final_intent_memory["value"]["summary"],
    )

    unrelated_event = client.post(
        "/v1/events/ingest",
        headers=headers,
        json=ingest_payload(
            tenant_id=tenant_id,
            user_id="user_non_workflow",
            session_id="session_search_ai",
            api_name="order.search",
            source_system="order_service",
            http_method="GET",
            route_template="/v1/orders/search",
            request_fields={"topic": "browse orders"},
            response_fields={},
        ),
    ).json()
    assert unrelated_event["decision"]["module_key"] == "orders.lifecycle"
    assert unrelated_event["decision"]["workflow_key"] is None
    assert unrelated_event["decision"]["related_api_ids"] == []
    assert unrelated_event["decision"]["intent_summary"] is None
    unrelated_job = process_next_job(db_session, bundle_resolver)
    assert unrelated_job is not None
    assert unrelated_job.result_jsonb.get("workflow_intent_memory_id") is None
    unrelated_memories = client.get(
        f"/v1/memory/users/user_non_workflow?tenant_id={tenant_id}",
        headers=headers,
    ).json()
    assert all(item["memory_type"] != "intent.user_goal" for item in unrelated_memories)
