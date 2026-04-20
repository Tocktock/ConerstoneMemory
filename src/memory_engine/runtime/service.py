from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import hashlib
import math
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from memory_engine.config.settings import get_settings
from memory_engine.control.schemas import APIOntologyDefinition, MemoryOntologyDefinition, PolicyProfileDefinition, SENSITIVITY_RANK
from memory_engine.db.models import (
    ConfigDocument,
    ConfigPublication,
    Entity,
    EntityAlias,
    Evidence,
    Job,
    Memory,
    MemoryEmbedding,
    Relation,
    RuntimeApiEvent,
    SignalCounter,
    SignalObservation,
)
from memory_engine.id_utils import new_id, utcnow
from memory_engine.ops.metrics import increment_metric
from memory_engine.runtime.policy import evaluate_event, match_api_entry, normalize_event_fields
from memory_engine.runtime.protection import protect_payload, restore_payload
from memory_engine.runtime.schemas import DecisionEnvelope, EventIngestRequest, ForgetRequest, MemoryQueryRequest, QueryResult
from memory_engine.worker.embeddings import get_embedding_provider


def _get_or_create_entity(
    session: Session, *, tenant_id: str, entity_type: str, canonical_key: str, attributes: dict[str, Any]
) -> Entity:
    entity = session.scalar(
        select(Entity).where(
            Entity.tenant_id == tenant_id,
            Entity.entity_type == entity_type,
            Entity.canonical_key == canonical_key,
        )
    )
    if entity:
        entity.attributes_jsonb = {**entity.attributes_jsonb, **attributes}
        entity.updated_at = utcnow()
        return entity
    entity = Entity(
        entity_id=new_id("ent"),
        tenant_id=tenant_id,
        entity_type=entity_type,
        canonical_key=canonical_key,
        attributes_jsonb=attributes,
    )
    session.add(entity)
    session.flush()
    return entity


def _create_alias(session: Session, entity: Entity, alias: str | None, alias_type: str) -> None:
    if not alias:
        return
    existing = session.scalar(
        select(EntityAlias).where(EntityAlias.entity_id == entity.entity_id, EntityAlias.alias == alias)
    )
    if existing:
        return
    session.add(
        EntityAlias(
            id=new_id("alias"),
            entity_id=entity.entity_id,
            alias=alias,
            alias_type=alias_type,
            confidence=1.0,
        )
    )


def _signal_key(event: RuntimeApiEvent, candidate) -> str:
    return f"{event.user_id}:{candidate.memory_type}:{candidate.canonical_key}"


def _merge_payload(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if value is not None:
            merged[key] = value
    return merged


def _restored_memory_payload(memory: Memory) -> dict[str, Any]:
    return restore_payload(memory.value_jsonb, memory.protected_value_encrypted)


def _embedding_text(
    clear_payload: dict[str, Any],
    *,
    sensitivity: str,
    memory_definition,
    policy: PolicyProfileDefinition,
) -> str | None:
    if memory_definition.embed_mode == "DISABLED":
        return None
    candidates = [
        clear_payload.get("summary"),
        clear_payload.get("topic"),
        clear_payload.get("canonical_customer_id"),
        clear_payload.get("domain"),
        clear_payload.get("city"),
        clear_payload.get("country"),
    ]
    text = next((str(item) for item in candidates if item), None)
    if text is None:
        return None
    if sensitivity in {"S2_PERSONAL", "S3_CONFIDENTIAL", "S4_RESTRICTED"} and policy.embedding_rules.raw_sensitive_embedding_allowed:
        return None
    return text


def _memory_embedding_text(memory: Memory) -> str | None:
    clear_payload = _restored_memory_payload(memory)
    return next(
        (
            str(item)
            for item in [
                clear_payload.get("summary"),
                clear_payload.get("topic"),
                clear_payload.get("canonical_customer_id"),
                clear_payload.get("domain"),
                clear_payload.get("city"),
                clear_payload.get("country"),
            ]
            if item
        ),
        None,
    )


def _embedding_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _upsert_memory_embedding(
    session: Session,
    *,
    memory: Memory,
    embedding_text: str | None,
    provider,
) -> None:
    if not embedding_text:
        return
    vector = provider.embed(embedding_text)
    if vector is None:
        return
    existing = session.scalar(
        select(MemoryEmbedding).where(
            MemoryEmbedding.memory_id == memory.memory_id,
            MemoryEmbedding.provider == provider.provider_name,
            MemoryEmbedding.model_name == provider.model_name,
        )
    )
    if existing is None:
        session.add(
            MemoryEmbedding(
                memory_id=memory.memory_id,
                provider=provider.provider_name,
                model_name=provider.model_name,
                dimensions=len(vector),
                embedding=vector,
                text_hash=_embedding_text_hash(embedding_text),
            )
        )
        return
    existing.dimensions = len(vector)
    existing.embedding = vector
    existing.text_hash = _embedding_text_hash(embedding_text)
    existing.updated_at = utcnow()


def _is_typo_correction(existing_memory: Memory, candidate, policy: PolicyProfileDefinition) -> bool:
    if existing_memory.updated_at < utcnow() - timedelta(minutes=policy.conflict_windows.typo_correction_minutes):
        return False
    similarity = SequenceMatcher(None, existing_memory.canonical_key, candidate.canonical_key).ratio()
    return similarity >= 0.85


def _record_signal_observation(
    session: Session,
    *,
    event: RuntimeApiEvent,
    candidate,
    policy: PolicyProfileDefinition,
) -> None:
    signal_key = _signal_key(event, candidate)
    session.add(
        SignalObservation(
            observation_id=new_id("observation"),
            signal_key=signal_key,
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            memory_type=candidate.memory_type,
            canonical_object_key=candidate.canonical_key,
            session_id=event.session_id,
            source_key=candidate.source_precedence_key,
            observed_at=event.occurred_at,
        )
    )
    session.flush()
    cutoff = event.occurred_at - timedelta(days=30)
    observations = list(
        session.scalars(
            select(SignalObservation)
            .where(
                SignalObservation.signal_key == signal_key,
                SignalObservation.observed_at >= cutoff,
            )
            .order_by(SignalObservation.observed_at.desc())
        )
    )
    counter = session.get(SignalCounter, signal_key)
    if counter is None:
        counter = SignalCounter(
            signal_key=signal_key,
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            memory_type=candidate.memory_type,
            canonical_object_key=candidate.canonical_key,
        )
        session.add(counter)
    half_life = max(policy.frequency.half_life_days, 1)
    total = len(observations) or 1
    session_counts: dict[str, int] = {}
    for observation in observations:
        if observation.session_id:
            session_counts[observation.session_id] = session_counts.get(observation.session_id, 0) + 1
    counter.decayed_weight = sum(
        math.pow(0.5, max((event.occurred_at - observation.observed_at).total_seconds(), 0) / (half_life * 86400))
        for observation in observations
    )
    counter.unique_sessions_30d = len({item.session_id for item in observations if item.session_id})
    counter.unique_days_30d = len({item.observed_at.date() for item in observations})
    counter.source_diversity_30d = len({item.source_key for item in observations})
    counter.same_session_burst_ratio = (max(session_counts.values()) / total) if session_counts else 0.0
    counter.last_seen_at = event.occurred_at


def _record_resolution_metric(session: Session, resolution: str, memory_type: str) -> None:
    increment_metric(
        session,
        "memory_resolution_events",
        labels={"resolution": resolution, "memory_type": memory_type},
    )


def _memory_ontology(bundle: Mapping[str, ConfigDocument]) -> dict[str, Any]:
    definition = MemoryOntologyDefinition.model_validate(bundle["memory_ontology"].definition_jsonb)
    return {entry.memory_type: entry for entry in definition.entries}


def _policy_profile(bundle: Mapping[str, ConfigDocument]) -> PolicyProfileDefinition:
    return PolicyProfileDefinition.model_validate(bundle["policy_profile"].definition_jsonb)


def _attach_evidence(
    session: Session,
    *,
    linked_record_type: str,
    linked_record_id: str,
    event: RuntimeApiEvent,
    candidate,
    config_snapshot_id: str,
) -> None:
    session.add(
        Evidence(
            evidence_id=new_id("evidence"),
            linked_record_type=linked_record_type,
            linked_record_id=linked_record_id,
            source_event_id=event.event_id,
            api_name=event.api_name,
            source_trust=candidate.source_trust,
            extraction_method=candidate.extractor,
            config_snapshot_id=config_snapshot_id,
        )
    )


def _persist_workflow_intent_memory(
    session: Session,
    *,
    event: RuntimeApiEvent,
    envelope: DecisionEnvelope,
    ontology: dict[str, Any],
    policy: PolicyProfileDefinition,
    provider,
    subject: Entity,
) -> str | None:
    if (
        not envelope.workflow_key
        or not envelope.intent_summary
        or not envelope.intent_memory_type
        or not envelope.candidates
    ):
        return None

    memory_definition = ontology.get(envelope.intent_memory_type)
    if memory_definition is None or not memory_definition.enabled:
        return None
    if memory_definition.cardinality != "ONE_ACTIVE":
        return None

    primary_candidate = max(
        envelope.candidates,
        key=lambda candidate: (candidate.source_precedence_score, candidate.confidence),
    )
    intent_sensitivity = max(
        (candidate.sensitivity for candidate in envelope.candidates),
        key=lambda level: SENSITIVITY_RANK[level],
    )
    if SENSITIVITY_RANK[intent_sensitivity] > SENSITIVITY_RANK[memory_definition.allowed_sensitivity]:
        return None

    related_api_ids = sorted(set(envelope.related_api_ids))
    intent_payload = {
        "summary": envelope.intent_summary,
        "workflow_key": envelope.workflow_key,
        "observed_api_name": event.api_name,
        "related_api_ids": related_api_ids,
        "evidence_event_ids": [event.event_id],
    }

    same_memory = session.scalar(
        select(Memory)
        .where(
            Memory.tenant_id == event.tenant_id,
            Memory.user_id == event.user_id,
            Memory.memory_type == envelope.intent_memory_type,
            Memory.state == "active",
            Memory.canonical_key == envelope.workflow_key,
        )
        .order_by(desc(Memory.updated_at))
        .limit(1)
    )

    if same_memory is not None:
        prior_payload = _restored_memory_payload(same_memory)
        merged_payload = {
            **prior_payload,
            **intent_payload,
            "related_api_ids": sorted(
                set(prior_payload.get("related_api_ids", [])) | set(related_api_ids)
            ),
            "evidence_event_ids": sorted(
                set(prior_payload.get("evidence_event_ids", [])) | {event.event_id}
            ),
        }
        same_memory.value_jsonb, same_memory.protected_value_encrypted = protect_payload(
            merged_payload,
            intent_sensitivity,
        )
        same_memory.confidence = max(same_memory.confidence, primary_candidate.confidence)
        same_memory.importance = max(same_memory.importance, memory_definition.importance_default)
        same_memory.source_precedence_key = primary_candidate.source_precedence_key
        same_memory.source_precedence_score = max(
            same_memory.source_precedence_score,
            primary_candidate.source_precedence_score,
        )
        _attach_evidence(
            session,
            linked_record_type="memory",
            linked_record_id=same_memory.memory_id,
            event=event,
            candidate=primary_candidate,
            config_snapshot_id=envelope.config_snapshot_id or "",
        )
        _upsert_memory_embedding(
            session,
            memory=same_memory,
            embedding_text=_embedding_text(
                merged_payload,
                sensitivity=intent_sensitivity,
                memory_definition=memory_definition,
                policy=policy,
            ),
            provider=provider,
        )
        return same_memory.memory_id

    clear_payload, encrypted_payload = protect_payload(intent_payload, intent_sensitivity)
    intent_memory = Memory(
        memory_id=new_id("memory"),
        tenant_id=event.tenant_id,
        user_id=event.user_id,
        memory_type=envelope.intent_memory_type,
        subject_entity_id=subject.entity_id,
        object_entity_id=None,
        value_jsonb=clear_payload,
        protected_value_encrypted=encrypted_payload,
        canonical_key=envelope.workflow_key,
        state="active",
        confidence=primary_candidate.confidence,
        importance=memory_definition.importance_default,
        sensitivity=intent_sensitivity,
        ttl_days=memory_definition.default_ttl_days,
        source_precedence_key=primary_candidate.source_precedence_key,
        source_precedence_score=primary_candidate.source_precedence_score,
        supersedes=None,
        config_snapshot_id=envelope.config_snapshot_id or "",
    )
    session.add(intent_memory)
    session.flush()
    _attach_evidence(
        session,
        linked_record_type="memory",
        linked_record_id=intent_memory.memory_id,
        event=event,
        candidate=primary_candidate,
        config_snapshot_id=envelope.config_snapshot_id or "",
    )
    _upsert_memory_embedding(
        session,
        memory=intent_memory,
        embedding_text=_embedding_text(
            intent_payload,
            sensitivity=intent_sensitivity,
            memory_definition=memory_definition,
            policy=policy,
        ),
        provider=provider,
    )
    increment_metric(
        session,
        "memory_creation_counts",
        labels={"memory_type": envelope.intent_memory_type, "record_type": "memory"},
    )
    return intent_memory.memory_id


def persist_event_job(session: Session, event: RuntimeApiEvent, envelope: DecisionEnvelope, bundle: Mapping[str, ConfigDocument]) -> dict[str, Any]:
    ontology = _memory_ontology(bundle)
    policy = _policy_profile(bundle)
    provider = get_embedding_provider()
    subject = _get_or_create_entity(
        session,
        tenant_id=event.tenant_id,
        entity_type="User",
        canonical_key=event.user_id,
        attributes={"user_id": event.user_id},
    )

    for candidate in envelope.candidates:
        _record_signal_observation(session, event=event, candidate=candidate, policy=policy)

    if envelope.action == "FORGET":
        forget_memories(
            session,
            ForgetRequest(tenant_id=event.tenant_id, user_id=event.user_id),
            config_snapshot_id=envelope.config_snapshot_id or "",
        )
        return {"action": "FORGET"}

    if envelope.action != "UPSERT":
        return {"action": envelope.action, "candidates": len(envelope.candidates)}

    persisted: list[str] = []
    resolutions: list[dict[str, str]] = []
    for candidate in envelope.candidates:
        memory_definition = ontology[candidate.memory_type]
        supersedes_id = None
        clear_payload, encrypted_payload = protect_payload(candidate.value, candidate.sensitivity)
        object_entity = None
        if candidate.relation_type or memory_definition.object_type:
            object_entity = _get_or_create_entity(
                session,
                tenant_id=event.tenant_id,
                entity_type=memory_definition.object_type or memory_definition.value_type or "Value",
                canonical_key=candidate.canonical_key,
                attributes=clear_payload,
            )
            _create_alias(session, object_entity, clear_payload.get("customer"), "customer_name")
            _create_alias(session, object_entity, clear_payload.get("domain"), "domain")

        same_memory = session.scalar(
            select(Memory)
            .where(
                Memory.tenant_id == event.tenant_id,
                Memory.user_id == event.user_id,
                Memory.memory_type == candidate.memory_type,
                Memory.state == "active",
                Memory.canonical_key == candidate.canonical_key,
            )
            .order_by(desc(Memory.updated_at))
            .limit(1)
        )
        active_memory = session.scalar(
            select(Memory)
            .where(
                Memory.tenant_id == event.tenant_id,
                Memory.user_id == event.user_id,
                Memory.memory_type == candidate.memory_type,
                Memory.state == "active",
            )
            .order_by(desc(Memory.updated_at))
            .limit(1)
        )

        if memory_definition.cardinality == "ONE_ACTIVE":
            if same_memory is not None:
                prior_payload = _restored_memory_payload(same_memory)
                merged_payload = _merge_payload(prior_payload, candidate.value)
                resolution = "merge" if merged_payload != prior_payload else "duplicate"
                same_memory.value_jsonb, same_memory.protected_value_encrypted = protect_payload(
                    merged_payload,
                    candidate.sensitivity,
                )
                same_memory.confidence = max(same_memory.confidence, candidate.confidence)
                same_memory.importance = max(same_memory.importance, memory_definition.importance_default)
                same_memory.source_precedence_key = candidate.source_precedence_key
                same_memory.source_precedence_score = max(
                    same_memory.source_precedence_score,
                    candidate.source_precedence_score,
                )
                _attach_evidence(
                    session,
                    linked_record_type="memory",
                    linked_record_id=same_memory.memory_id,
                    event=event,
                    candidate=candidate,
                    config_snapshot_id=envelope.config_snapshot_id or "",
                )
                _upsert_memory_embedding(
                    session,
                    memory=same_memory,
                    embedding_text=_embedding_text(
                        merged_payload,
                        sensitivity=candidate.sensitivity,
                        memory_definition=memory_definition,
                        policy=policy,
                    ),
                    provider=provider,
                )
                _record_resolution_metric(session, resolution, candidate.memory_type)
                resolutions.append({"memory_type": candidate.memory_type, "resolution": resolution})
                persisted.append(same_memory.memory_id)
                continue

            supersedes_id = None
            if active_memory is not None:
                if (
                    candidate.source_precedence_score > active_memory.source_precedence_score
                    or candidate.source_precedence_key == active_memory.source_precedence_key
                    or _is_typo_correction(active_memory, candidate, policy)
                ):
                    active_memory.state = "superseded"
                    active_memory.valid_to = utcnow()
                    supersedes_id = active_memory.memory_id
                    _record_resolution_metric(session, "supersede", candidate.memory_type)
                    resolutions.append({"memory_type": candidate.memory_type, "resolution": "supersede"})
                elif candidate.source_precedence_score == active_memory.source_precedence_score:
                    active_memory.state = "conflicted"
                    active_memory.valid_to = utcnow()
                    _record_resolution_metric(session, "conflict", candidate.memory_type)
                    resolutions.append({"memory_type": candidate.memory_type, "resolution": "conflict"})
                    continue
                else:
                    _record_resolution_metric(session, "reject", candidate.memory_type)
                    resolutions.append({"memory_type": candidate.memory_type, "resolution": "reject"})
                    continue
        elif memory_definition.cardinality == "MANY_SCORED" and same_memory is not None:
            same_memory.confidence = min(1.0, same_memory.confidence + 0.1)
            same_memory.importance = min(1.0, same_memory.importance + 0.05)
            same_memory.source_precedence_key = candidate.source_precedence_key
            same_memory.source_precedence_score = max(
                same_memory.source_precedence_score,
                candidate.source_precedence_score,
            )
            _attach_evidence(
                session,
                linked_record_type="memory",
                linked_record_id=same_memory.memory_id,
                event=event,
                candidate=candidate,
                config_snapshot_id=envelope.config_snapshot_id or "",
            )
            _upsert_memory_embedding(
                session,
                memory=same_memory,
                embedding_text=_embedding_text(
                    _restored_memory_payload(same_memory),
                    sensitivity=same_memory.sensitivity,
                    memory_definition=memory_definition,
                    policy=policy,
                ),
                provider=provider,
            )
            _record_resolution_metric(session, "reinforce", candidate.memory_type)
            resolutions.append({"memory_type": candidate.memory_type, "resolution": "reinforce"})
            persisted.append(same_memory.memory_id)
            continue

        if memory_definition.memory_class == "relation" and object_entity is not None:
            relation = session.scalar(
                select(Relation).where(
                    Relation.tenant_id == event.tenant_id,
                    Relation.subject_entity_id == subject.entity_id,
                    Relation.object_entity_id == object_entity.entity_id,
                    Relation.relation_type == (candidate.relation_type or candidate.memory_type),
                    Relation.state == "active",
                )
            )
            if relation:
                relation.evidence_count += 1
                relation.strength = min(1.0, relation.strength + 0.1)
                relation.source_precedence_key = candidate.source_precedence_key
                relation.source_precedence_score = max(relation.source_precedence_score, candidate.source_precedence_score)
                _attach_evidence(
                    session,
                    linked_record_type="relation",
                    linked_record_id=relation.relation_id,
                    event=event,
                    candidate=candidate,
                    config_snapshot_id=envelope.config_snapshot_id or "",
                )
                _record_resolution_metric(session, "duplicate", candidate.memory_type)
                resolutions.append({"memory_type": candidate.memory_type, "resolution": "duplicate"})
                persisted.append(relation.relation_id)
                continue
            relation = Relation(
                relation_id=new_id("rel"),
                tenant_id=event.tenant_id,
                subject_entity_id=subject.entity_id,
                relation_type=candidate.relation_type or candidate.memory_type,
                object_entity_id=object_entity.entity_id,
                state="active",
                strength=candidate.confidence,
                evidence_count=1,
                source_precedence_key=candidate.source_precedence_key,
                source_precedence_score=candidate.source_precedence_score,
                config_snapshot_id=envelope.config_snapshot_id or "",
            )
            session.add(relation)
            session.flush()
            _attach_evidence(
                session,
                linked_record_type="relation",
                linked_record_id=relation.relation_id,
                event=event,
                candidate=candidate,
                config_snapshot_id=envelope.config_snapshot_id or "",
            )
            increment_metric(session, "memory_creation_counts", labels={"memory_type": candidate.memory_type, "record_type": "relation"})
            persisted.append(relation.relation_id)
            continue

        embedding_text = _embedding_text(
            clear_payload,
            sensitivity=candidate.sensitivity,
            memory_definition=memory_definition,
            policy=policy,
        )

        memory = Memory(
            memory_id=new_id("memory"),
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            memory_type=candidate.memory_type,
            subject_entity_id=subject.entity_id,
            object_entity_id=object_entity.entity_id if object_entity else None,
            value_jsonb=clear_payload,
            protected_value_encrypted=encrypted_payload,
            canonical_key=candidate.canonical_key,
            state="active",
            confidence=candidate.confidence,
            importance=memory_definition.importance_default,
            sensitivity=candidate.sensitivity,
            ttl_days=memory_definition.default_ttl_days,
            source_precedence_key=candidate.source_precedence_key,
            source_precedence_score=candidate.source_precedence_score,
            supersedes=supersedes_id if memory_definition.cardinality == "ONE_ACTIVE" else None,
            config_snapshot_id=envelope.config_snapshot_id or "",
        )
        session.add(memory)
        session.flush()
        _upsert_memory_embedding(
            session,
            memory=memory,
            embedding_text=embedding_text,
            provider=provider,
        )
        _attach_evidence(
            session,
            linked_record_type="memory",
            linked_record_id=memory.memory_id,
            event=event,
            candidate=candidate,
            config_snapshot_id=envelope.config_snapshot_id or "",
        )
        increment_metric(session, "memory_creation_counts", labels={"memory_type": candidate.memory_type, "record_type": "memory"})
        persisted.append(memory.memory_id)
    workflow_intent_memory_id = _persist_workflow_intent_memory(
        session,
        event=event,
        envelope=envelope,
        ontology=ontology,
        policy=policy,
        provider=provider,
        subject=subject,
    )
    if workflow_intent_memory_id:
        persisted.append(workflow_intent_memory_id)
    return {
        "action": envelope.action,
        "persisted": persisted,
        "resolutions": resolutions,
        "workflow_intent_memory_id": workflow_intent_memory_id,
    }


def ingest_event(
    session: Session,
    *,
    event_request: EventIngestRequest,
    bundle: Mapping[str, ConfigDocument],
    snapshot: ConfigPublication,
) -> tuple[RuntimeApiEvent, DecisionEnvelope, Job]:
    envelope = evaluate_event(session, event_request, bundle, snapshot)
    api_definition = APIOntologyDefinition.model_validate(bundle["api_ontology"].definition_jsonb)
    api_entry = match_api_entry(api_definition, event_request)
    capability_family = "UNKNOWN"
    normalized_fields: dict[str, Any] = {}
    request_artifact = None
    response_artifact = None
    occurred_at = event_request.occurred_at or utcnow()
    if api_entry is not None:
        capability_family = api_entry.capability_family
        normalized_fields = normalize_event_fields(event_request, api_entry.normalization_rules.primary_fact_source)
        if api_entry.evidence_capture_policy.request == "summary_plus_artifact_ref" and event_request.request.artifact_ref:
            request_artifact = event_request.request.artifact_ref.model_dump(mode="json")
        if api_entry.evidence_capture_policy.response == "summary_plus_artifact_ref" and event_request.response.artifact_ref:
            response_artifact = event_request.response.artifact_ref.model_dump(mode="json")
    event = RuntimeApiEvent(
        event_id=envelope.event_id,
        tenant_id=event_request.tenant_id,
        user_id=event_request.user_id,
        session_id=event_request.session_id,
        source_system=event_request.source_system,
        api_name=event_request.api_name,
        http_method=event_request.http_method.upper(),
        route_template=event_request.route_template,
        request_id=event_request.request_id,
        trace_id=event_request.trace_id,
        source_channel=event_request.source_channel,
        capability_family=capability_family,
        response_status=event_request.response.status_code,
        request_summary=event_request.request.summary,
        response_summary=event_request.response.summary,
        request_fields_jsonb=event_request.request.selected_fields,
        response_fields_jsonb=event_request.response.selected_fields,
        request_artifact_jsonb=request_artifact,
        response_artifact_jsonb=response_artifact,
        redaction_policy_version=event_request.redaction_policy_version,
        structured_fields_jsonb=normalized_fields,
        decision_jsonb=envelope.model_dump(mode="json"),
        config_snapshot_id=snapshot.id,
        status="decided",
        occurred_at=occurred_at,
    )
    job = Job(
        job_id=new_id("job"),
        job_type="persist_event",
        payload_jsonb={"event_id": event.event_id, "decision": envelope.model_dump(mode="json")},
        status="queued",
    )
    session.add(event)
    session.add(job)
    increment_metric(session, "decision_counts", labels={"action": envelope.action})
    if envelope.action == "BLOCK" and envelope.candidates:
        max_sensitivity = max(envelope.candidates, key=lambda item: SENSITIVITY_RANK[item.sensitivity]).sensitivity
        increment_metric(session, "blocked_counts_by_sensitivity", labels={"sensitivity": max_sensitivity})
    repeat_bucket = f"{int(envelope.repeat_score * 4)}/4"
    increment_metric(session, "repeat_score_distributions", labels={"bucket": repeat_bucket})
    if snapshot.scope in {"tenant", "emergency_override"} or normalized_fields.get("tenant_override_sensitivity"):
        increment_metric(session, "tenant_override_usage", labels={"scope": snapshot.scope})
    session.commit()
    session.refresh(event)
    session.refresh(job)
    return event, envelope, job


def process_job(session: Session, job: Job, bundle: Mapping[str, ConfigDocument]) -> Job:
    event = session.get(RuntimeApiEvent, job.payload_jsonb["event_id"])
    if event is None:
        raise ValueError(f"Event not found for job {job.job_id}")
    envelope = DecisionEnvelope.model_validate(job.payload_jsonb["decision"])
    result = persist_event_job(session, event, envelope, bundle)
    event.status = "processed"
    event.processed_at = utcnow()
    job.status = "completed"
    job.processed_at = utcnow()
    job.result_jsonb = result
    session.commit()
    session.refresh(job)
    return job


def _process_ttl_cleanup_job(session: Session, job: Job) -> dict[str, Any]:
    expired = 0
    memories = list(
        session.scalars(
            select(Memory).where(
                Memory.state == "active",
                Memory.ttl_days.is_not(None),
            )
        )
    )
    now = utcnow()
    for memory in memories:
        if memory.ttl_days is None:
            continue
        if memory.created_at <= now - timedelta(days=memory.ttl_days):
            memory.state = "deleted"
            memory.valid_to = now
            expired += 1
    if expired:
        increment_metric(session, "ttl_cleanup_events", labels={"expired": str(expired)})
    return {"expired": expired}


def _process_embedding_backfill_job(session: Session, job: Job) -> dict[str, Any]:
    provider = get_embedding_provider()
    updated = 0
    memories = list(session.scalars(select(Memory).where(Memory.state == "active")))
    for memory in memories:
        existing = session.scalar(
            select(MemoryEmbedding).where(
                MemoryEmbedding.memory_id == memory.memory_id,
                MemoryEmbedding.provider == provider.provider_name,
                MemoryEmbedding.model_name == provider.model_name,
            )
        )
        if existing is not None:
            continue
        text = _memory_embedding_text(memory)
        if not text:
            continue
        _upsert_memory_embedding(session, memory=memory, embedding_text=text, provider=provider)
        updated += 1
    return {"embedded": updated}


def _process_recompute_conflicts_job(session: Session, job: Job) -> dict[str, Any]:
    reconciled = 0
    active_memories = list(session.scalars(select(Memory).where(Memory.state == "active").order_by(Memory.updated_at.desc())))
    groups: dict[tuple[str, str, str], list[Memory]] = {}
    for memory in active_memories:
        groups.setdefault((memory.tenant_id, memory.user_id, memory.memory_type), []).append(memory)
    for group in groups.values():
        if len(group) <= 1:
            continue
        ordered = sorted(
            group,
            key=lambda item: (item.source_precedence_score, item.confidence, item.updated_at.timestamp()),
            reverse=True,
        )
        winner = ordered[0]
        for memory in ordered[1:]:
            if memory.state == "active":
                memory.state = "conflicted"
                memory.valid_to = utcnow()
                reconciled += 1
        winner.state = "active"
    if reconciled:
        increment_metric(session, "memory_resolution_events", labels={"resolution": "conflict_recompute", "memory_type": "__all__"}, value=float(reconciled))
    return {"reconciled": reconciled}


def _process_replay_snapshot_job(session: Session, job: Job) -> dict[str, Any]:
    snapshot_id = job.payload_jsonb.get("snapshot_id")
    query = select(RuntimeApiEvent)
    if snapshot_id:
        query = query.where(RuntimeApiEvent.config_snapshot_id == snapshot_id)
    count = len(list(session.scalars(query)))
    increment_metric(session, "replay_snapshot_events", labels={"snapshot_id": snapshot_id or "__all__"})
    return {"snapshot_id": snapshot_id, "matched_events": count}


def process_next_job(session: Session, bundle_resolver) -> Job | None:
    job = session.scalar(
        select(Job).where(Job.status == "queued").order_by(Job.created_at.asc()).limit(1)
    )
    if job is None:
        return None
    job.status = "running"
    job.attempts += 1
    job.locked_at = utcnow()
    session.commit()
    try:
        if job.job_type == "persist_event":
            event = session.get(RuntimeApiEvent, job.payload_jsonb["event_id"])
            if event is None:
                raise ValueError("Event missing")
            bundle, _snapshot = bundle_resolver(session, event.tenant_id)
            processed_job = process_job(session, job, bundle)
            return processed_job
        if job.job_type == "ttl_cleanup":
            result = _process_ttl_cleanup_job(session, job)
        elif job.job_type == "embedding_backfill":
            result = _process_embedding_backfill_job(session, job)
        elif job.job_type == "recompute_conflicts":
            result = _process_recompute_conflicts_job(session, job)
        elif job.job_type == "replay_snapshot":
            result = _process_replay_snapshot_job(session, job)
        else:
            raise ValueError(f"Unsupported job type: {job.job_type}")
        job.status = "completed"
        job.processed_at = utcnow()
        job.result_jsonb = result
        session.commit()
        session.refresh(job)
        return job
    except Exception as exc:
        job.status = "failed"
        job.error_text = str(exc)
        job.processed_at = utcnow()
        session.commit()
        session.refresh(job)
        return job


def forget_memories(session: Session, request: ForgetRequest, config_snapshot_id: str) -> dict[str, int]:
    memory_query = select(Memory).where(Memory.tenant_id == request.tenant_id, Memory.user_id == request.user_id)
    if request.memory_type:
        memory_query = memory_query.where(Memory.memory_type == request.memory_type)
    if request.canonical_key:
        memory_query = memory_query.where(Memory.canonical_key == request.canonical_key)
    memories = list(session.scalars(memory_query))
    for memory in memories:
        memory.state = "deleted"
        memory.valid_to = utcnow()

    relation_count = 0
    subject = session.scalar(
        select(Entity).where(
            Entity.tenant_id == request.tenant_id,
            Entity.entity_type == "User",
            Entity.canonical_key == request.user_id,
        )
    )
    if request.relation_type and subject is not None:
        relation_query = select(Relation).where(
            Relation.tenant_id == request.tenant_id,
            Relation.subject_entity_id == subject.entity_id,
            Relation.relation_type == request.relation_type,
        )
        if request.canonical_key:
            object_entity = session.scalar(
                select(Entity).where(
                    Entity.tenant_id == request.tenant_id,
                    Entity.canonical_key == request.canonical_key,
                )
            )
            if object_entity is not None:
                relation_query = relation_query.where(Relation.object_entity_id == object_entity.entity_id)
        relations = list(
            session.scalars(relation_query)
        )
        for relation in relations:
            relation.state = "deleted"
        relation_count = len(relations)
    session.commit()
    return {"memories": len(memories), "relations": relation_count, "config_snapshot_id": config_snapshot_id}


def _recency_score(timestamp: datetime) -> float:
    age_days = max((utcnow() - timestamp).days, 0)
    return max(0.0, 1 - min(age_days / 365, 1.0))


def _cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if left is None or right is None:
        return 0.0
    left_values = list(left)
    right_values = list(right)
    if len(left_values) == 0 or len(right_values) == 0:
        return 0.0
    numerator = sum(a * b for a, b in zip(left_values, right_values, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left_values)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right_values)) or 1.0
    return max(0.0, min(numerator / (left_norm * right_norm), 1.0))


def _snapshot_context(session: Session, snapshot_id: str | None) -> tuple[str, str]:
    if not snapshot_id:
        return "", get_settings().environment
    snapshot = session.get(ConfigPublication, snapshot_id)
    if snapshot is None:
        return "", get_settings().environment
    return snapshot.scope, snapshot.environment


def query_memories(session: Session, request: MemoryQueryRequest) -> list[QueryResult]:
    results: list[QueryResult] = []
    provider = get_embedding_provider()
    subject_entity = session.scalar(
        select(Entity).where(
            Entity.tenant_id == request.tenant_id,
            Entity.entity_type == "User",
            Entity.canonical_key == request.user_id,
        )
    )
    exact_query = select(Memory).where(
        Memory.tenant_id == request.tenant_id,
        Memory.user_id == request.user_id,
        Memory.state == "active",
    )
    if request.memory_type:
        exact_query = exact_query.where(Memory.memory_type == request.memory_type)
    exact_matches = list(session.scalars(exact_query.order_by(desc(Memory.importance)).limit(request.top_k)))
    for memory in exact_matches:
        evidence_count = session.scalar(
            select(func.count(Evidence.evidence_id)).where(
                Evidence.linked_record_type == "memory", Evidence.linked_record_id == memory.memory_id
            )
        ) or 0
        recency = _recency_score(memory.updated_at)
        scope, environment = _snapshot_context(session, memory.config_snapshot_id)
        results.append(
            QueryResult(
                record_type="memory",
                record_id=memory.memory_id,
                memory_type=memory.memory_type,
                title=memory.value_jsonb.get("summary") or memory.value_jsonb.get("topic") or memory.canonical_key,
                state=memory.state,
                confidence=memory.confidence,
                importance=memory.importance,
                sensitivity=memory.sensitivity,
                config_snapshot_id=memory.config_snapshot_id,
                evidence_count=evidence_count,
                tenant_id=memory.tenant_id,
                scope=scope,
                environment=environment,
                semantic_relevance=1.0,
                recency_score=recency,
                final_score=100.0 + (memory.confidence * 0.25) + (memory.importance * 0.2) + (recency * 0.1),
                payload=_restored_memory_payload(memory),
            )
        )

    relation_query = (
        select(Relation, Entity)
        .join(Entity, Relation.object_entity_id == Entity.entity_id)
        .where(Relation.tenant_id == request.tenant_id, Relation.state == "active")
        .limit(request.top_k)
    )
    if subject_entity is not None:
        relation_query = relation_query.where(Relation.subject_entity_id == subject_entity.entity_id)
    if request.memory_type:
        relation_query = relation_query.where(Relation.relation_type == request.memory_type)
    for relation, entity in session.execute(relation_query):
        recency = _recency_score(relation.updated_at)
        scope, environment = _snapshot_context(session, relation.config_snapshot_id)
        results.append(
            QueryResult(
                record_type="relation",
                record_id=relation.relation_id,
                memory_type=relation.relation_type,
                title=entity.canonical_key,
                state=relation.state,
                confidence=relation.strength,
                importance=relation.strength,
                sensitivity="S2_PERSONAL",
                config_snapshot_id=relation.config_snapshot_id,
                evidence_count=relation.evidence_count,
                tenant_id=relation.tenant_id,
                scope=scope,
                environment=environment,
                semantic_relevance=0.6,
                recency_score=recency,
                final_score=10.0 + (0.45 * 0.6) + (0.25 * relation.strength) + (0.20 * relation.strength) + (0.10 * recency),
                payload=entity.attributes_jsonb,
            )
        )

    if request.query_text:
        query_vector = provider.embed(request.query_text)
        if query_vector:
            vector_query = (
                select(Memory, MemoryEmbedding)
                .where(
                    Memory.tenant_id == request.tenant_id,
                    Memory.user_id == request.user_id,
                    Memory.state == "active",
                )
                .join(
                    MemoryEmbedding,
                    (
                        (MemoryEmbedding.memory_id == Memory.memory_id)
                        & (MemoryEmbedding.provider == provider.provider_name)
                        & (MemoryEmbedding.model_name == provider.model_name)
                    ),
                )
                .order_by(MemoryEmbedding.embedding.cosine_distance(query_vector))
                .limit(request.top_k)
            )
            if request.memory_type:
                vector_query = vector_query.where(Memory.memory_type == request.memory_type)
            for memory, embedding_row in session.execute(vector_query):
                recency = _recency_score(memory.updated_at)
                semantic = _cosine_similarity(embedding_row.embedding, query_vector)
                scope, environment = _snapshot_context(session, memory.config_snapshot_id)
                results.append(
                    QueryResult(
                        record_type="memory",
                        record_id=memory.memory_id,
                        memory_type=memory.memory_type,
                        title=memory.value_jsonb.get("summary") or memory.canonical_key,
                        state=memory.state,
                        confidence=memory.confidence,
                        importance=memory.importance,
                        sensitivity=memory.sensitivity,
                        config_snapshot_id=memory.config_snapshot_id,
                        evidence_count=0,
                        tenant_id=memory.tenant_id,
                        scope=scope,
                        environment=environment,
                        semantic_relevance=semantic,
                        recency_score=recency,
                        final_score=(0.45 * semantic)
                        + (0.25 * memory.confidence)
                        + (0.20 * memory.importance)
                        + (0.10 * recency),
                        payload=_restored_memory_payload(memory),
                    )
                )

    deduped: dict[tuple[str, str], QueryResult] = {}
    for result in sorted(results, key=lambda item: item.final_score, reverse=True):
        deduped.setdefault((result.record_type, result.record_id), result)
    final_results = list(deduped.values())[: request.top_k]
    increment_metric(session, "retrieval_requests", labels={"tenant_id": request.tenant_id})
    for result in final_results:
        increment_metric(session, "retrieval_hits", labels={"memory_type": result.memory_type})
    return final_results


def list_user_memories(session: Session, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
    query = select(Memory).where(Memory.tenant_id == tenant_id, Memory.user_id == user_id).order_by(desc(Memory.updated_at))
    return [
        {
            "memory_id": memory.memory_id,
            "memory_type": memory.memory_type,
            "state": memory.state,
            "value": _restored_memory_payload(memory),
            "config_snapshot_id": memory.config_snapshot_id,
            "updated_at": memory.updated_at.isoformat(),
        }
        for memory in session.scalars(query)
    ]


def timeline(session: Session, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
    query = select(RuntimeApiEvent).where(
        RuntimeApiEvent.tenant_id == tenant_id, RuntimeApiEvent.user_id == user_id
    ).order_by(desc(RuntimeApiEvent.occurred_at))
    return [
        {
            "event_id": event.event_id,
            "api_name": event.api_name,
            "source_system": event.source_system,
            "http_method": event.http_method,
            "route_template": event.route_template,
            "status": event.status,
            "decision": event.decision_jsonb,
            "occurred_at": event.occurred_at.isoformat(),
            "config_snapshot_id": event.config_snapshot_id,
        }
        for event in session.scalars(query)
    ]


def decision_records(session: Session, *, tenant_id: str | None = None) -> list[dict[str, Any]]:
    query = select(RuntimeApiEvent).order_by(desc(RuntimeApiEvent.occurred_at))
    if tenant_id:
        query = query.where(RuntimeApiEvent.tenant_id == tenant_id)
    return [
        {
            "id": event.event_id,
            "title": event.api_name,
            "action": (event.decision_jsonb or {}).get("action", event.status),
            "status": "blocked" if (event.decision_jsonb or {}).get("action") == "BLOCK" else "accepted",
            "source_system": event.source_system,
            "http_method": event.http_method,
            "route_template": event.route_template,
            "inference_invoked": ((event.decision_jsonb or {}).get("llm_assist") or {}).get("invoked", False),
            "inference_provider": ((event.decision_jsonb or {}).get("llm_assist") or {}).get("provider"),
            "model_name": ((event.decision_jsonb or {}).get("llm_assist") or {}).get("model_name"),
            "prompt_template_key": ((event.decision_jsonb or {}).get("llm_assist") or {}).get("prompt_template_key"),
            "prompt_version": ((event.decision_jsonb or {}).get("llm_assist") or {}).get("prompt_version"),
            "model_recommendation": ((event.decision_jsonb or {}).get("llm_assist") or {}).get("recommendation"),
            "model_confidence": ((event.decision_jsonb or {}).get("llm_assist") or {}).get("confidence"),
            "reasoning_summary": ((event.decision_jsonb or {}).get("llm_assist") or {}).get("reasoning_summary"),
            "observed_entry_id": (event.decision_jsonb or {}).get("observed_entry_id"),
            "module_key": (event.decision_jsonb or {}).get("module_key"),
            "workflow_key": (event.decision_jsonb or {}).get("workflow_key"),
            "related_api_ids": (event.decision_jsonb or {}).get("related_api_ids", []),
            "intent_summary": (event.decision_jsonb or {}).get("intent_summary"),
            "scope": _snapshot_context(session, event.config_snapshot_id)[0],
            "tenant": event.tenant_id,
            "environment": _snapshot_context(session, event.config_snapshot_id)[1],
            "reason_code": ",".join((event.decision_jsonb or {}).get("reason_codes", [])),
            "reason_codes": (event.decision_jsonb or {}).get("reason_codes", []),
            "config_snapshot_id": event.config_snapshot_id,
            "evidence": {"event_id": event.event_id, "api_name": event.api_name},
            "timestamp": event.occurred_at.isoformat(),
        }
        for event in session.scalars(query)
    ]
