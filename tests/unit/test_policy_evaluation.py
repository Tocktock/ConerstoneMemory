from __future__ import annotations

from memory_engine.runtime.inference import InferenceResult
from memory_engine.runtime.policy import (
    evaluate_event,
    filter_prompt_fields,
    normalize_event_fields,
    validate_candidate_set,
)
from memory_engine.runtime.schemas import CandidateMemory, EventIngestRequest
from tests.support.builders import (
    base_api_module,
    base_api_package_definition,
    base_memory_definition,
    base_policy_definition,
)


class DummyDocument:
    def __init__(self, definition_jsonb):
        self.definition_jsonb = definition_jsonb


def _event(api_name: str, *, request_fields=None, response_fields=None, source_system="profile_service", http_method="POST", route_template="/v1/profile/address"):
    return EventIngestRequest(
        tenant_id="tenant_test",
        user_id="user_test",
        session_id="session_test",
        source_system=source_system,
        api_name=api_name,
        http_method=http_method,
        route_template=route_template,
        request={
            "summary": "request summary",
            "selected_fields": request_fields or {},
            "artifact_ref": None,
        },
        response={
            "status_code": 200,
            "summary": "response summary",
            "selected_fields": response_fields or {},
            "artifact_ref": None,
        },
    )


def _api_entry(**overrides):
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


def _policy_definition():
    definition = base_policy_definition()
    definition["source_precedence"] = {
        "explicit_user_write": 100,
        "repeated_behavioral_signal": 50,
    }
    return definition


def _bundle(api_entries):
    return {
        "api_ontology": DummyDocument({"entries": api_entries}),
        "memory_ontology": DummyDocument(base_memory_definition()),
        "policy_profile": DummyDocument(_policy_definition()),
    }


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
        source_precedence_key="explicit_user_write" if method_semantics == "WRITE" else "repeated_behavioral_signal",
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


def _workflow_bundle():
    return {
        "api_ontology": DummyDocument(
            base_api_package_definition(
                document_name="Checkout Package",
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
                workflows=[
                    {
                        "workflow_key": "order_checkout",
                        "title": "Order checkout",
                        "description": "Order registration, retrieval, charge, and refund form one workflow.",
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
        ),
        "memory_ontology": DummyDocument(base_memory_definition()),
        "policy_profile": DummyDocument(_policy_definition()),
    }


def test_evaluate_event_explicit_write_bypass_skips_llm_assist() -> None:
    decision = evaluate_event(
        None,
        _event("profile.updateAddress", request_fields={"address": "123 Seongsu-ro"}),
        _bundle([_api_entry()]),
        None,
    )
    assert decision.action == "UPSERT"
    assert "EXPLICIT_WRITE_BYPASS" in decision.reason_codes
    assert decision.llm_assist.invoked is False


def test_evaluate_event_observes_unknown_read_api() -> None:
    decision = evaluate_event(
        None,
        _event(
            "search.readSomething",
            request_fields={},
            source_system="search_service",
            http_method="GET",
            route_template="/v1/search",
        ),
        {
            "api_ontology": DummyDocument({"entries": []}),
            "memory_ontology": DummyDocument({"entries": []}),
            "policy_profile": DummyDocument(_policy_definition()),
        },
        None,
    )
    assert decision.action == "OBSERVE"
    assert "UNKNOWN_API" in decision.reason_codes


def test_evaluate_event_blocks_when_tenant_override_raises_sensitivity() -> None:
    decision = evaluate_event(
        None,
        _event(
            "profile.updateAddress",
            request_fields={
                "address": "123 Seongsu-ro",
                "tenant_override_sensitivity": "S3_CONFIDENTIAL",
            },
        ),
        _bundle([_api_entry()]),
        None,
    )
    assert decision.action == "BLOCK"
    assert "SENSITIVITY_BLOCKED" in decision.reason_codes
    assert decision.llm_assist.invoked is False


def test_evaluate_event_resolves_workflow_context_from_api_package() -> None:
    decision = evaluate_event(
        None,
        _event(
            "order.register",
            request_fields={"topic": "order checkout"},
            source_system="order_service",
            http_method="POST",
            route_template="/v1/orders",
        ),
        _workflow_bundle(),
        None,
    )
    assert decision.action == "UPSERT"
    assert decision.observed_entry_id == "order.register"
    assert decision.module_key == "orders.lifecycle"
    assert decision.workflow_key == "order_checkout"
    assert decision.related_api_ids == ["order.get", "payment.charge"]
    assert decision.intent_summary == "User is trying to place an order and complete payment."
    assert decision.intent_memory_type == "intent.user_goal"


def test_normalize_event_fields_for_primary_fact_sources() -> None:
    event = _event(
        "profile.updateAddress",
        request_fields={"address": "request value"},
        response_fields={"address": "response value"},
    )
    assert normalize_event_fields(event, "request_only") == {"address": "request value"}
    assert normalize_event_fields(event, "response_only") == {"address": "response value"}
    assert normalize_event_fields(event, "request_then_response") == {"address": "request value"}
    assert normalize_event_fields(event, "response_then_request") == {"address": "response value"}


def test_filter_prompt_fields_honors_allowed_and_blocked_paths() -> None:
    filtered = filter_prompt_fields(
        {
            "normalized_fields": {"query": "mortgage rates", "token": "secret"},
            "request": {"summary": "search", "selected_fields": {"query": "mortgage rates"}},
        },
        ["$.normalized_fields.query", "$.normalized_fields.token", "$.request.summary"],
        ["$.normalized_fields.token"],
    )
    assert filtered == {
        "normalized_fields": {"query": "mortgage rates"},
        "request": {"summary": "search"},
    }


def test_validate_candidate_set_rejects_ineligible_memory_type() -> None:
    candidates, reason_codes, blocked = validate_candidate_set(
        [
            CandidateMemory(
                memory_type="interest.missing",
                canonical_key="mortgage_rates",
                confidence=0.3,
                sensitivity="S1_INTERNAL",
                value={"topic": "mortgage_rates"},
                extractor="topic_extractor",
                source_trust=30,
                source_precedence_key="repeated_behavioral_signal",
                source_precedence_score=50,
            )
        ],
        {entry["memory_type"]: entry for entry in base_memory_definition()["entries"]},
        type("PolicyHolder", (), {"sensitivity": type("SensitivityHolder", (), {"hard_block_levels": ["S4_RESTRICTED", "S3_CONFIDENTIAL"]})()})(),  # type: ignore[arg-type]
    )
    assert candidates == []
    assert "MODEL_INVALID_MEMORY_TYPE" in reason_codes
    assert blocked is False


def test_model_low_confidence_persisted_reason_code(monkeypatch) -> None:
    search_entry = _api_entry(
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
        llm_usage_mode="ASSIST",
        prompt_template_key="memory.hybrid.search.v1",
        llm_allowed_field_paths=["$.normalized_fields.query"],
    )
    dummy_result = InferenceResult(
        provider="ollama",
        model_name="gemma4:e4b",
        prompt_template_key="memory.hybrid.search.v1",
        prompt_version="2026-04-11",
        input_hash="hash",
        recommendation="UPSERT",
        confidence=0.34,
        reasoning_summary="low confidence persist",
        candidates=[
            CandidateMemory(
                memory_type="interest.topic",
                canonical_key="mortgage_rates",
                confidence=0.34,
                sensitivity="S1_INTERNAL",
                value={"topic": "mortgage_rates", "raw": "mortgage rates"},
                extractor="topic_extractor",
                source_trust=30,
                source_precedence_key="repeated_behavioral_signal",
                source_precedence_score=50,
            )
        ],
    )

    class DummyProvider:
        provider_name = "ollama"
        model_name = "gemma4:e4b"

        def infer(self, request):
            return dummy_result

    monkeypatch.setattr("memory_engine.runtime.policy.get_inference_provider", lambda provider_id: DummyProvider())
    decision = evaluate_event(
        None,
        _event(
            "search.webSearch",
            request_fields={"query": "mortgage rates"},
            source_system="search_service",
            http_method="GET",
            route_template="/v1/search",
        ),
        _bundle([search_entry]),
        None,
    )
    assert decision.action == "UPSERT"
    assert decision.reason_codes == ["MODEL_LOW_CONFIDENCE_PERSISTED"]
    assert decision.llm_assist.invoked is True
    assert decision.llm_assist.confidence is not None and decision.llm_assist.confidence < 0.6


def test_model_invocation_failure_keeps_primary_provider_attribution(monkeypatch) -> None:
    search_entry = _api_entry(
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
        llm_usage_mode="ASSIST",
        prompt_template_key="memory.hybrid.search.v1",
        llm_allowed_field_paths=["$.normalized_fields.query"],
    )

    class FailingPrimaryProvider:
        provider_name = "ollama"
        model_name = "gemma4:e4b"

        def infer(self, request):
            raise ValueError("temporary ollama failure")

    def fake_get_provider(provider_id: str):
        if provider_id == "ollama":
            return FailingPrimaryProvider()
        raise ValueError("OpenAI provider requires an API key")

    monkeypatch.setattr("memory_engine.runtime.policy.get_inference_provider", fake_get_provider)
    decision = evaluate_event(
        None,
        _event(
            "search.webSearch",
            request_fields={"query": "mortgage rates"},
            source_system="search_service",
            http_method="GET",
            route_template="/v1/search",
        ),
        _bundle([search_entry]),
        None,
    )
    assert decision.llm_assist.invoked is True
    assert decision.llm_assist.provider == "ollama"
    assert decision.llm_assist.model_name == "gemma4:e4b"
    assert "MODEL_INVOCATION_FAILED" in decision.reason_codes
