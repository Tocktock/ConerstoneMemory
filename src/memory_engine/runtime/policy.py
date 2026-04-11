from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from memory_engine.control.schemas import (
    APIOntologyDefinition,
    APIOntologyEntry,
    MemoryOntologyDefinition,
    PolicyProfileDefinition,
    SENSITIVITY_RANK,
)
from memory_engine.db.models import ConfigDocument, ConfigPublication, InferenceRun, SignalCounter
from memory_engine.id_utils import new_id
from memory_engine.runtime.extractors import EXTRACTOR_REGISTRY
from memory_engine.runtime.inference import (
    InferenceResult,
    InferenceRequest,
    build_inference_input_hash,
    get_inference_provider,
)
from memory_engine.runtime.prompts import get_prompt_template
from memory_engine.runtime.schemas import CandidateMemory, DecisionEnvelope, EventIngestRequest, LLMAssistSummary


_MISSING = object()


def _max_sensitivity(levels: list[str]) -> str:
    valid_levels = [level for level in levels if level in SENSITIVITY_RANK]
    return max(valid_levels or ["S1_INTERNAL"], key=lambda item: SENSITIVITY_RANK[item])


def _classifier_sensitivity(fields: dict[str, Any]) -> str:
    normalized_keys = {str(key).lower() for key in fields}
    normalized_values = " ".join(str(value).lower() for value in fields.values() if value is not None)
    if {"password", "secret", "token", "ssn"} & normalized_keys:
        return "S4_RESTRICTED"
    if {"salary", "medical", "diagnosis"} & normalized_keys:
        return "S3_CONFIDENTIAL"
    if {"address", "email", "phone", "customer", "domain"} & normalized_keys:
        return "S2_PERSONAL"
    if any(marker in normalized_values for marker in ["ssn", "password", "secret token"]):
        return "S4_RESTRICTED"
    if any(marker in normalized_values for marker in ["salary", "medical", "diagnosis"]):
        return "S3_CONFIDENTIAL"
    return "S1_INTERNAL"


def _tenant_override_sensitivity(fields: dict[str, Any]) -> str | None:
    for key in ("tenant_override_sensitivity", "sensitivity_override"):
        value = fields.get(key)
        if isinstance(value, str) and value in SENSITIVITY_RANK:
            return value
    return None


def _bundle_to_definition(bundle: Mapping[str, ConfigDocument]) -> tuple[
    APIOntologyDefinition, MemoryOntologyDefinition, PolicyProfileDefinition
]:
    return (
        APIOntologyDefinition.model_validate(bundle["api_ontology"].definition_jsonb),
        MemoryOntologyDefinition.model_validate(bundle["memory_ontology"].definition_jsonb),
        PolicyProfileDefinition.model_validate(bundle["policy_profile"].definition_jsonb),
    )


def compute_repeat_score(counter: SignalCounter | None, policy: PolicyProfileDefinition) -> float:
    if counter is None:
        return 0.0
    weights = policy.frequency.weights
    normalized = (
        weights.decayed_weight * min(counter.decayed_weight, 1.0)
        + weights.unique_sessions_30d * min(counter.unique_sessions_30d / 5, 1.0)
        + weights.unique_days_30d * min(counter.unique_days_30d / 5, 1.0)
        + weights.source_diversity_30d * min(counter.source_diversity_30d / 3, 1.0)
    )
    if (
        policy.frequency.burst_penalty.enabled
        and counter.same_session_burst_ratio >= policy.frequency.burst_penalty.same_session_ratio_threshold
    ):
        normalized -= policy.frequency.burst_penalty.penalty_value
    return max(0.0, min(normalized, 1.0))


def _signal_key(event: EventIngestRequest, memory_type: str, canonical_key: str) -> str:
    return f"{event.user_id}:{memory_type}:{canonical_key}"


def _flatten_selected_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in fields.items():
        if isinstance(value, Mapping):
            flattened.update(_flatten_selected_fields(value))
        else:
            flattened[str(key)] = value
    return flattened


def normalize_event_fields(event: EventIngestRequest, primary_fact_source: str) -> dict[str, Any]:
    request_fields = _flatten_selected_fields(event.request.selected_fields)
    response_fields = _flatten_selected_fields(event.response.selected_fields)
    if primary_fact_source == "request_only":
        return dict(request_fields)
    if primary_fact_source == "response_only":
        return dict(response_fields)
    if primary_fact_source == "request_then_response":
        return {**response_fields, **request_fields}
    if primary_fact_source == "response_then_request":
        return {**request_fields, **response_fields}
    raise ValueError(f"Unsupported primary_fact_source: {primary_fact_source}")


def build_normalized_envelope(event: EventIngestRequest, normalized_fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "tenant_id": event.tenant_id,
        "user_id": event.user_id,
        "session_id": event.session_id,
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "source_system": event.source_system,
        "api_name": event.api_name,
        "http_method": event.http_method,
        "route_template": event.route_template,
        "request_id": event.request_id,
        "trace_id": event.trace_id,
        "source_channel": event.source_channel,
        "redaction_policy_version": event.redaction_policy_version,
        "request": event.request.model_dump(mode="json"),
        "response": event.response.model_dump(mode="json"),
        "normalized_fields": normalized_fields,
    }


def _path_parts(path: str) -> list[str]:
    if not path.startswith("$."):
        raise ValueError(f"Path must start with $.: {path}")
    return [part for part in path[2:].split(".") if part]


def _extract_path(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for part in _path_parts(path):
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _assign_path(target: MutableMapping[str, Any], path: str, value: Any) -> None:
    current: MutableMapping[str, Any] = target
    parts = _path_parts(path)
    for part in parts[:-1]:
        existing = current.get(part)
        if not isinstance(existing, MutableMapping):
            existing = {}
            current[part] = existing
        current = existing
    current[parts[-1]] = value


def _remove_path(target: MutableMapping[str, Any], path: str) -> None:
    parts = _path_parts(path)
    stack: list[tuple[MutableMapping[str, Any], str]] = []
    current: MutableMapping[str, Any] | Any = target
    for part in parts[:-1]:
        if not isinstance(current, MutableMapping) or part not in current:
            return
        stack.append((current, part))
        current = current[part]
    if isinstance(current, MutableMapping):
        current.pop(parts[-1], None)
    for parent, part in reversed(stack):
        child = parent.get(part)
        if isinstance(child, MutableMapping) and not child:
            parent.pop(part, None)


def filter_prompt_fields(payload: dict[str, Any], allowed_paths: list[str], blocked_paths: list[str]) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    for path in allowed_paths:
        value = _extract_path(payload, path)
        if value is _MISSING:
            continue
        _assign_path(filtered, path, value)
    for path in blocked_paths:
        _remove_path(filtered, path)
    return filtered


def match_api_entry(api_doc: APIOntologyDefinition, event: EventIngestRequest) -> APIOntologyEntry | None:
    for entry in api_doc.entries:
        if not entry.enabled:
            continue
        if entry.api_name != event.api_name:
            continue
        if entry.event_match.source_system != event.source_system:
            continue
        if entry.event_match.http_method.upper() != event.http_method.upper():
            continue
        if entry.event_match.route_template != event.route_template:
            continue
        return entry
    return None


def _extract_candidates(
    normalized_fields: dict[str, Any],
    api_entry: APIOntologyEntry,
    policy: PolicyProfileDefinition,
    memory_entries: dict[str, Any],
) -> list[CandidateMemory]:
    candidates: list[CandidateMemory] = []
    classifier_sensitivity = _classifier_sensitivity(normalized_fields)
    tenant_override_sensitivity = _tenant_override_sensitivity(normalized_fields)
    precedence_score = policy.source_precedence.get(api_entry.source_precedence_key, 0)
    for memory_type in api_entry.candidate_memory_types:
        memory_entry = memory_entries.get(memory_type)
        if memory_entry is None or not memory_entry.enabled:
            continue
        for extractor_name in api_entry.extractors:
            extractor = EXTRACTOR_REGISTRY.get(extractor_name)
            if extractor is None:
                continue
            extracted = extractor(normalized_fields)
            if extracted is None:
                continue
            field_tags = extracted.get("field_sensitivity_tags", [])
            effective_sensitivity = _max_sensitivity(
                [
                    api_entry.sensitivity_hint,
                    extracted["sensitivity"],
                    classifier_sensitivity,
                    *field_tags,
                    *([tenant_override_sensitivity] if tenant_override_sensitivity else []),
                ]
            )
            candidates.append(
                CandidateMemory(
                    memory_type=memory_type,
                    canonical_key=extracted["canonical_key"],
                    confidence=min(1.0, max(api_entry.source_trust / 100, 0.5)),
                    sensitivity=effective_sensitivity,
                    field_sensitivity_tags=field_tags,
                    classifier_sensitivity=classifier_sensitivity,
                    value=extracted["value"],
                    relation_type=(api_entry.relation_templates or [None])[0],
                    extractor=extractor_name,
                    source_trust=api_entry.source_trust,
                    source_precedence_key=api_entry.source_precedence_key,
                    source_precedence_score=precedence_score,
                )
            )
    return candidates


def validate_candidate_set(
    candidates: list[CandidateMemory],
    memory_entries: dict[str, Any],
    policy: PolicyProfileDefinition,
) -> tuple[list[CandidateMemory], list[str], bool]:
    valid_candidates: list[CandidateMemory] = []
    reason_codes: list[str] = []
    blocked = False
    for candidate in candidates:
        memory_definition = memory_entries.get(candidate.memory_type)
        if memory_definition is None or not memory_definition.enabled:
            reason_codes.append("MODEL_INVALID_MEMORY_TYPE")
            continue
        if candidate.sensitivity in policy.sensitivity.hard_block_levels:
            blocked = True
            reason_codes.append("SENSITIVITY_BLOCKED")
            continue
        if SENSITIVITY_RANK[candidate.sensitivity] > SENSITIVITY_RANK[memory_definition.allowed_sensitivity]:
            blocked = True
            reason_codes.append("SENSITIVITY_ABOVE_MEMORY_CEILING")
            continue
        valid_candidates.append(candidate)
    return valid_candidates, sorted(set(reason_codes)), blocked


def _build_repeat_action(
    session: Session | None,
    event: EventIngestRequest,
    api_entry: APIOntologyEntry,
    policy: PolicyProfileDefinition,
    candidates: list[CandidateMemory],
) -> tuple[str, list[str], float]:
    if not candidates:
        return "OBSERVE", ["NO_CANDIDATES"], 0.0
    counter = None
    if session is not None:
        first_candidate = candidates[0]
        counter = session.scalar(
            select(SignalCounter).where(
                SignalCounter.signal_key
                == _signal_key(event, first_candidate.memory_type, first_candidate.canonical_key)
            )
        )
    repeat_score = 1.0 if api_entry.repeat_policy == "BYPASS" else compute_repeat_score(counter, policy)
    action = api_entry.default_action
    reason_codes = [f"API_DEFAULT_{api_entry.default_action}"]
    if api_entry.repeat_policy == "BYPASS":
        reason_codes.append("REPEAT_BYPASSED_FOR_EXPLICIT_WRITE")
    else:
        if repeat_score >= policy.frequency.thresholds.persist:
            action = "UPSERT"
            reason_codes.append("REPEAT_THRESHOLD_MET")
        elif repeat_score >= policy.frequency.thresholds.observe:
            action = "OBSERVE"
            reason_codes.append("REPEAT_OBSERVE_THRESHOLD_MET")
        elif action == "UPSERT":
            action = "OBSERVE"
            reason_codes.append("REPEAT_THRESHOLD_NOT_MET")
        else:
            reason_codes.append("OBSERVE_PENDING_REPEAT")
    return action, reason_codes, repeat_score


def _inference_llm_assist(result: InferenceResult, *, inference_id: str | None, reasoning_summary: str | None) -> LLMAssistSummary:
    return LLMAssistSummary(
        invoked=True,
        inference_id=inference_id,
        provider=result.provider,
        model_name=result.model_name,
        prompt_template_key=result.prompt_template_key,
        prompt_version=result.prompt_version,
        recommendation=result.recommendation,
        confidence=result.confidence,
        reasoning_summary=reasoning_summary,
    )


def evaluate_event(
    session: Session | None,
    event: EventIngestRequest,
    bundle: Mapping[str, ConfigDocument],
    snapshot: ConfigPublication | None,
) -> DecisionEnvelope:
    api_doc, memory_doc, policy = _bundle_to_definition(bundle)
    event_id = new_id("evt")
    memory_entries = {entry.memory_type: entry for entry in memory_doc.entries}
    api_entry = match_api_entry(api_doc, event)

    if api_entry is None:
        action = "OBSERVE" if any(token in event.api_name.lower() for token in ["read", "search"]) else "BLOCK"
        return DecisionEnvelope(
            config_snapshot_id=snapshot.id if snapshot else None,
            event_id=event_id,
            action=action,
            reason_codes=["UNKNOWN_API"],
            candidates=[],
        )

    normalized_fields = normalize_event_fields(event, api_entry.normalization_rules.primary_fact_source)
    normalized_envelope = build_normalized_envelope(event, normalized_fields)

    if api_entry.default_action == "FORGET" or api_entry.capability_family == "DELETE_FORGET":
        return DecisionEnvelope(
            config_snapshot_id=snapshot.id if snapshot else None,
            event_id=event_id,
            action="FORGET",
            reason_codes=["EXPLICIT_FORGET"],
            candidates=[],
        )

    classifier_sensitivity = _classifier_sensitivity(normalized_fields)
    if policy.model_inference.hard_rule_bypass and classifier_sensitivity in policy.sensitivity.hard_block_levels:
        return DecisionEnvelope(
            config_snapshot_id=snapshot.id if snapshot else None,
            event_id=event_id,
            action="BLOCK",
            reason_codes=["HARD_SENSITIVITY_BLOCK"],
            candidates=[],
        )

    deterministic_candidates = _extract_candidates(normalized_fields, api_entry, policy, memory_entries)
    validated_candidates, candidate_reasons, blocked = validate_candidate_set(
        deterministic_candidates,
        memory_entries,
        policy,
    )
    if blocked:
        return DecisionEnvelope(
            config_snapshot_id=snapshot.id if snapshot else None,
            event_id=event_id,
            action="BLOCK",
            reason_codes=candidate_reasons or ["SENSITIVITY_BLOCKED"],
            candidates=validated_candidates or deterministic_candidates,
        )

    if (
        policy.model_inference.explicit_write_bypass
        and api_entry.method_semantics == "WRITE"
        and api_entry.default_action == "UPSERT"
    ):
        action, reasons, repeat_score = _build_repeat_action(session, event, api_entry, policy, validated_candidates)
        return DecisionEnvelope(
            config_snapshot_id=snapshot.id if snapshot else None,
            event_id=event_id,
            action=action,
            reason_codes=["EXPLICIT_WRITE_BYPASS", *reasons],
            candidates=validated_candidates,
            repeat_score=repeat_score,
        )

    llm_active = policy.model_inference.enabled and api_entry.llm_usage_mode in {"ASSIST", "REQUIRE"}
    if llm_active:
        prompt_payload = filter_prompt_fields(
            normalized_envelope,
            api_entry.llm_allowed_field_paths,
            api_entry.llm_blocked_field_paths,
        )
        provider = get_inference_provider()
        inference_id: str | None = None
        try:
            inference_result = provider.infer(
                InferenceRequest(
                    event=event,
                    normalized_envelope=normalized_envelope,
                    prompt_payload=prompt_payload,
                    api_entry=api_entry,
                    eligible_memory_types=list(api_entry.candidate_memory_types),
                    base_candidates=validated_candidates,
                )
            )
        except Exception as exc:
            fallback_action, fallback_reasons, repeat_score = _build_repeat_action(
                session, event, api_entry, policy, validated_candidates
            )
            final_action = "OBSERVE" if api_entry.llm_usage_mode == "REQUIRE" else fallback_action
            reason_code = "MODEL_REQUIRED_FAILED" if api_entry.llm_usage_mode == "REQUIRE" else "MODEL_INVOCATION_FAILED"
            inference_id = None
            prompt_version = None
            if api_entry.prompt_template_key:
                try:
                    prompt_version = get_prompt_template(api_entry.prompt_template_key).version
                except ValueError:
                    prompt_version = "unknown"
            if session is not None and api_entry.prompt_template_key:
                inference_id = new_id("infer")
                session.add(
                    InferenceRun(
                        inference_id=inference_id,
                        source_event_id=event_id,
                        config_snapshot_id=snapshot.id if snapshot else None,
                        model_provider=provider.provider_name,
                        model_name=provider.model_name,
                        prompt_template_key=api_entry.prompt_template_key,
                        prompt_version=prompt_version or "unknown",
                        input_hash=build_inference_input_hash(
                            prompt_template_key=api_entry.prompt_template_key,
                            prompt_version=prompt_version or "unknown",
                            prompt_payload=prompt_payload,
                            api_name=event.api_name,
                            eligible_memory_types=list(api_entry.candidate_memory_types),
                        ),
                        llm_recommendation="OBSERVE",
                        llm_confidence=0.0,
                        llm_reasoning_summary=str(exc) if policy.model_inference.log_reasoning_summary else None,
                        candidate_jsonb=[],
                        final_action=final_action,
                    )
                )
            return DecisionEnvelope(
                config_snapshot_id=snapshot.id if snapshot else None,
                event_id=event_id,
                action=final_action,
                reason_codes=[reason_code, *fallback_reasons],
                candidates=validated_candidates,
                repeat_score=repeat_score,
                llm_assist=LLMAssistSummary(
                    invoked=True,
                    inference_id=inference_id,
                    provider=provider.provider_name,
                    model_name=provider.model_name,
                    prompt_template_key=api_entry.prompt_template_key,
                    prompt_version=prompt_version,
                    recommendation="OBSERVE",
                    confidence=0.0,
                    reasoning_summary=str(exc) if policy.model_inference.log_reasoning_summary else None,
                ),
            )

        provider_candidates, provider_reasons, provider_blocked = validate_candidate_set(
            inference_result.candidates,
            memory_entries,
            policy,
        )
        reasoning_summary = (
            inference_result.reasoning_summary if policy.model_inference.log_reasoning_summary else None
        )
        if provider_blocked:
            final_action = "BLOCK"
            reason_codes = ["MODEL_POLICY_BLOCK", *provider_reasons]
        elif inference_result.recommendation == "BLOCK":
            final_action = "BLOCK"
            reason_codes = ["MODEL_RECOMMENDED_BLOCK"]
        elif provider_reasons and not provider_candidates:
            final_action = "OBSERVE"
            reason_codes = (
                ["MODEL_REQUIRED_INVALID"] if api_entry.llm_usage_mode == "REQUIRE" else ["MODEL_INVALID_OUTPUT"]
            )
        elif inference_result.recommendation == "UPSERT" and provider_candidates:
            if inference_result.confidence < policy.model_inference.low_confidence_threshold:
                if policy.model_inference.allow_low_confidence_persist:
                    final_action = "UPSERT"
                    reason_codes = ["MODEL_LOW_CONFIDENCE_PERSISTED"]
                else:
                    final_action = "OBSERVE"
                    reason_codes = ["MODEL_LOW_CONFIDENCE_OBSERVED"]
            else:
                final_action = "UPSERT"
                reason_codes = ["MODEL_RECOMMENDED_UPSERT"]
        else:
            final_action = "OBSERVE"
            reason_codes = ["MODEL_RECOMMENDED_OBSERVE"]

        if session is not None:
            inference_id = new_id("infer")
            session.add(
                InferenceRun(
                    inference_id=inference_id,
                    source_event_id=event_id,
                    config_snapshot_id=snapshot.id if snapshot else None,
                    model_provider=inference_result.provider,
                    model_name=inference_result.model_name,
                    prompt_template_key=inference_result.prompt_template_key,
                    prompt_version=inference_result.prompt_version,
                    input_hash=inference_result.input_hash,
                    llm_recommendation=inference_result.recommendation,
                    llm_confidence=inference_result.confidence,
                    llm_reasoning_summary=reasoning_summary,
                    candidate_jsonb=[candidate.model_dump(mode="json") for candidate in inference_result.candidates],
                    final_action=final_action,
                )
            )

        return DecisionEnvelope(
            config_snapshot_id=snapshot.id if snapshot else None,
            event_id=event_id,
            action=final_action,
            reason_codes=reason_codes,
            candidates=provider_candidates,
            llm_assist=_inference_llm_assist(
                inference_result,
                inference_id=inference_id,
                reasoning_summary=reasoning_summary,
            ),
        )

    action, reason_codes, repeat_score = _build_repeat_action(session, event, api_entry, policy, validated_candidates)
    return DecisionEnvelope(
        config_snapshot_id=snapshot.id if snapshot else None,
        event_id=event_id,
        action=action,
        reason_codes=reason_codes,
        candidates=validated_candidates,
        repeat_score=repeat_score,
    )
