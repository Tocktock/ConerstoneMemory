from __future__ import annotations

from memory_engine.control.service import validate_definition
from tests.support.builders import (
    base_api_module,
    base_api_package_definition,
    base_memory_definition,
    base_policy_definition,
)


def _api_entry(**overrides):
    entry = {
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
        "response_field_selectors": ["$.result_count"],
        "normalization_rules": {"primary_fact_source": "request_then_response"},
        "evidence_capture_policy": {"request": "summary_only", "response": "summary_only"},
        "llm_usage_mode": "DISABLED",
        "prompt_template_key": None,
        "llm_allowed_field_paths": [],
        "llm_blocked_field_paths": [],
        "notes": "",
    }
    entry.update(overrides)
    entry["entry_id"] = str(overrides.get("entry_id") or entry["api_name"])
    return entry


def _policy_definition():
    definition = base_policy_definition()
    definition["source_precedence"] = {"structured_business_write": 80, "repeated_behavioral_signal": 50}
    return definition


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
    return _api_entry(
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
        notes="workflow package test entry",
    )


def _checkout_package(**workflow_overrides) -> dict:
    workflows = [
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
                {"from_entry_id": "order.register", "to_entry_id": "order.get", "edge_type": "READS_AFTER_WRITE"},
                {"from_entry_id": "order.register", "to_entry_id": "payment.charge", "edge_type": "ENABLES"},
                {"from_entry_id": "payment.refund", "to_entry_id": "payment.charge", "edge_type": "COMPENSATES"},
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
    ]
    workflows[0].update(workflow_overrides)
    return base_api_package_definition(
        document_name="Package API Ontology",
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
        workflows=workflows,
    )


def test_validate_definition_flags_unknown_memory_reference() -> None:
    issues = validate_definition(
        "api_ontology",
        {
            "document_name": "API Ontology",
            "entries": [_api_entry(candidate_memory_types=["interest.missing"])],
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
                _api_entry(
                    api_name="crm.createDeal",
                    capability_family="RELATION_WRITE",
                    method_semantics="WRITE",
                    candidate_memory_types=["relationship.customer"],
                    default_action="UPSERT",
                    repeat_policy="BYPASS",
                    sensitivity_hint="S2_PERSONAL",
                    source_trust=90,
                    source_precedence_key="missing_precedence",
                    extractors=["customer_parser"],
                    relation_templates=["USER_WORKS_WITH_CUSTOMER"],
                    event_match={
                        "source_system": "crm_service",
                        "http_method": "POST",
                        "route_template": "/v1/deals",
                    },
                    request_field_selectors=["$.customer", "$.domain"],
                )
            ],
        },
        reference_memory_types={"relationship.customer"},
        policy_definition=_policy_definition(),
    )
    assert any(issue.code == "precedence.unknown" for issue in issues)


def test_validate_definition_flags_selector_without_root_marker() -> None:
    issues = validate_definition(
        "api_ontology",
        {
            "document_name": "API Ontology",
            "entries": [_api_entry(request_field_selectors=["query"])],
        },
        reference_memory_types={"interest.topic"},
        policy_definition=_policy_definition(),
    )
    assert any(issue.code == "value_error" for issue in issues)


def test_validate_definition_flags_unknown_prompt_template() -> None:
    issues = validate_definition(
        "api_ontology",
        {
            "document_name": "API Ontology",
            "entries": [
                _api_entry(
                    llm_usage_mode="ASSIST",
                    prompt_template_key="memory.hybrid.missing.v1",
                    llm_allowed_field_paths=["$.normalized_fields.query"],
                )
            ],
        },
        reference_memory_types={"interest.topic"},
        policy_definition=_policy_definition(),
    )
    assert any(issue.code == "prompt_template.unknown" for issue in issues)


def test_validate_definition_flags_invalid_model_inference_flags() -> None:
    invalid_policy = _policy_definition()
    invalid_policy["model_inference"]["require_policy_validation"] = False
    issues = validate_definition(
        "policy_profile",
        invalid_policy,
    )
    assert any(issue.code == "value_error" for issue in issues)


def test_validate_definition_flags_unknown_provider_gate_reference() -> None:
    invalid_policy = _policy_definition()
    invalid_policy["model_inference"]["provider_gate"]["default_provider"] = "missing_provider"
    issues = validate_definition("policy_profile", invalid_policy)
    assert any(issue.code == "inference_provider.unknown" for issue in issues)


def test_validate_definition_accepts_package_modules_and_workflows() -> None:
    memory_types = {entry["memory_type"] for entry in base_memory_definition()["entries"]}
    issues = validate_definition(
        "api_ontology",
        _checkout_package(),
        reference_memory_types=memory_types,
        policy_definition=_policy_definition(),
    )
    assert issues == []


def test_validate_definition_flags_unknown_workflow_intent_memory_type() -> None:
    memory_types = {entry["memory_type"] for entry in base_memory_definition()["entries"]}
    issues = validate_definition(
        "api_ontology",
        _checkout_package(intent_memory_type="intent.missing"),
        reference_memory_types=memory_types,
        policy_definition=_policy_definition(),
    )
    assert any(
        issue.code == "reference.integrity" and issue.path == "workflows.order_checkout.intent_memory_type"
        for issue in issues
    )


def test_validate_definition_flags_dangling_workflow_entry_reference() -> None:
    memory_types = {entry["memory_type"] for entry in base_memory_definition()["entries"]}
    issues = validate_definition(
        "api_ontology",
        _checkout_package(participant_entry_ids=["order.register", "payment.charge", "payment.missing"]),
        reference_memory_types=memory_types,
        policy_definition=_policy_definition(),
    )
    assert any(issue.code == "workflow.entry_missing" for issue in issues)


def test_validate_definition_flags_ambiguous_compiled_match_in_package() -> None:
    first_entry = _workflow_entry(
        entry_id="order.register",
        api_name="order.register",
        source_system="order_service",
        http_method="POST",
        route_template="/v1/orders",
        module_key="orders.lifecycle",
    )
    second_entry = _workflow_entry(
        entry_id="order.register.duplicate",
        api_name="order.register",
        source_system="order_service",
        http_method="POST",
        route_template="/v1/orders",
        module_key="orders.duplicate",
    )
    issues = validate_definition(
        "api_ontology",
        base_api_package_definition(
            document_name="Ambiguous API Package",
            modules=[
                base_api_module(module_key="orders.lifecycle", title="Orders Lifecycle", entries=[first_entry]),
                base_api_module(module_key="orders.duplicate", title="Orders Duplicate", entries=[second_entry]),
            ],
            workflows=[],
        ),
        reference_memory_types={entry["memory_type"] for entry in base_memory_definition()["entries"]},
        policy_definition=_policy_definition(),
    )
    assert any(issue.code == "api_entry.ambiguous_match" for issue in issues)
