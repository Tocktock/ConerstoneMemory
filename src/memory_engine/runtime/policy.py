from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from memory_engine.control.schemas import (
    APIOntologyDefinition,
    MemoryOntologyDefinition,
    PolicyProfileDefinition,
    SENSITIVITY_RANK,
)
from memory_engine.db.models import ConfigDocument, ConfigPublication, SignalCounter
from memory_engine.id_utils import new_id
from memory_engine.runtime.extractors import EXTRACTOR_REGISTRY
from memory_engine.runtime.schemas import CandidateMemory, DecisionEnvelope, EventIngestRequest


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


def _extract_candidates(
    event: EventIngestRequest,
    api_entry,
    policy: PolicyProfileDefinition,
    memory_entries: dict[str, Any],
) -> list[CandidateMemory]:
    candidates: list[CandidateMemory] = []
    classifier_sensitivity = _classifier_sensitivity(event.structured_fields)
    tenant_override_sensitivity = _tenant_override_sensitivity(event.structured_fields)
    precedence_score = policy.source_precedence.get(api_entry.source_precedence_key, 0)
    for memory_type in api_entry.candidate_memory_types:
        memory_entry = memory_entries.get(memory_type)
        if memory_entry is None or not memory_entry.enabled:
            continue
        for extractor_name in api_entry.extractors:
            extractor = EXTRACTOR_REGISTRY.get(extractor_name)
            if extractor is None:
                continue
            extracted = extractor(event.structured_fields)
            if extracted is None:
                continue
            field_tags = extracted.get("field_sensitivity_tags", [])
            effective_sensitivity = _max_sensitivity(
                [
                    api_entry.sensitivity_hint,
                    extracted["sensitivity"],
                    classifier_sensitivity,
                    *field_tags,
                    *( [tenant_override_sensitivity] if tenant_override_sensitivity else [] ),
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


def evaluate_event(
    session: Session | None,
    event: EventIngestRequest,
    bundle: Mapping[str, ConfigDocument],
    snapshot: ConfigPublication | None,
) -> DecisionEnvelope:
    api_doc, memory_doc, policy = _bundle_to_definition(bundle)
    memory_entries = {entry.memory_type: entry for entry in memory_doc.entries}
    api_entry = next((entry for entry in api_doc.entries if entry.api_name == event.api_name and entry.enabled), None)

    if api_entry is None:
        action = "OBSERVE" if any(token in event.api_name.lower() for token in ["read", "search"]) else "BLOCK"
        return DecisionEnvelope(
            config_snapshot_id=snapshot.id if snapshot else None,
            event_id=new_id("evt"),
            action=action,
            reason_codes=["UNKNOWN_API"],
            candidates=[],
        )

    if api_entry.default_action == "FORGET" or api_entry.capability_family == "DELETE_FORGET":
        return DecisionEnvelope(
            config_snapshot_id=snapshot.id if snapshot else None,
            event_id=new_id("evt"),
            action="FORGET",
            reason_codes=["EXPLICIT_FORGET"],
            candidates=[],
        )

    candidates = _extract_candidates(event, api_entry, policy, memory_entries)
    if not candidates:
        return DecisionEnvelope(
            config_snapshot_id=snapshot.id if snapshot else None,
            event_id=new_id("evt"),
            action="OBSERVE",
            reason_codes=["NO_CANDIDATES"],
            candidates=[],
        )

    if any(
        SENSITIVITY_RANK[candidate.sensitivity] >= SENSITIVITY_RANK["S3_CONFIDENTIAL"]
        or candidate.sensitivity in policy.sensitivity.hard_block_levels
        for candidate in candidates
    ):
        return DecisionEnvelope(
            config_snapshot_id=snapshot.id if snapshot else None,
            event_id=new_id("evt"),
            action="BLOCK",
            reason_codes=["SENSITIVITY_BLOCKED"],
            candidates=candidates,
        )

    for candidate in candidates:
        memory_definition = memory_entries[candidate.memory_type]
        if SENSITIVITY_RANK[candidate.sensitivity] > SENSITIVITY_RANK[memory_definition.allowed_sensitivity]:
            return DecisionEnvelope(
                config_snapshot_id=snapshot.id if snapshot else None,
                event_id=new_id("evt"),
                action="BLOCK",
                reason_codes=["SENSITIVITY_ABOVE_MEMORY_CEILING"],
                candidates=candidates,
            )

    counter = None
    first_candidate = candidates[0]
    if session is not None:
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

    reason_codes.append("SENSITIVITY_ALLOWED")
    return DecisionEnvelope(
        config_snapshot_id=snapshot.id if snapshot else None,
        event_id=new_id("evt"),
        action=action,
        reason_codes=reason_codes,
        candidates=candidates,
        repeat_score=repeat_score,
    )
