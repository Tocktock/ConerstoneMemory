from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import math
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from memory_engine.control.schemas import MemoryOntologyDefinition, PolicyProfileDefinition
from memory_engine.db.models import (
    ConfigDocument,
    ConfigPublication,
    Entity,
    EntityAlias,
    Evidence,
    Job,
    Memory,
    Relation,
    RuntimeApiEvent,
    SignalCounter,
)
from memory_engine.id_utils import new_id, utcnow
from memory_engine.runtime.policy import evaluate_event
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


def _update_signal_counter(session: Session, event: RuntimeApiEvent, envelope: DecisionEnvelope) -> None:
    for candidate in envelope.candidates:
        signal_key = f"{event.user_id}:{candidate.memory_type}:{candidate.canonical_key}"
        counter = session.get(SignalCounter, signal_key)
        if counter is None:
            counter = SignalCounter(
                signal_key=signal_key,
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                memory_type=candidate.memory_type,
                canonical_object_key=candidate.canonical_key,
                decayed_weight=0.0,
                unique_sessions_30d=0,
                unique_days_30d=0,
                source_diversity_30d=0,
                same_session_burst_ratio=0.0,
            )
            session.add(counter)
        counter.decayed_weight = min(counter.decayed_weight + 0.35, 1.0)
        counter.unique_sessions_30d += 1 if event.session_id else 0
        counter.unique_days_30d += 1
        counter.source_diversity_30d = min(counter.source_diversity_30d + 1, 10)
        counter.same_session_burst_ratio = 0.0
        counter.last_seen_at = utcnow()


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

    _update_signal_counter(session, event, envelope)

    if envelope.action == "FORGET":
        forget_memories(
            session,
            ForgetRequest(tenant_id=event.tenant_id, user_id=event.user_id),
            config_snapshot_id=envelope.config_snapshot_id or "",
        )
        return {"action": "FORGET"}

    if envelope.action != "UPSERT":
        return {"action": envelope.action, "candidates": len(envelope.candidates)}

    persisted = []
    for candidate in envelope.candidates:
        memory_definition = ontology[candidate.memory_type]
        object_entity = None
        if candidate.relation_type or memory_definition.object_type:
            object_entity = _get_or_create_entity(
                session,
                tenant_id=event.tenant_id,
                entity_type=memory_definition.object_type or memory_definition.value_type or "Value",
                canonical_key=candidate.canonical_key,
                attributes=candidate.value,
            )
            _create_alias(session, object_entity, candidate.value.get("customer"), "customer_name")
            _create_alias(session, object_entity, candidate.value.get("domain"), "domain")

        existing_memory = session.scalar(
            select(Memory)
            .where(
                Memory.tenant_id == event.tenant_id,
                Memory.user_id == event.user_id,
                Memory.memory_type == candidate.memory_type,
                Memory.state == "active",
            )
            .order_by(desc(Memory.created_at))
            .limit(1)
        )

        if memory_definition.cardinality == "ONE_ACTIVE":
            if existing_memory and existing_memory.canonical_key == candidate.canonical_key:
                _attach_evidence(
                    session,
                    linked_record_type="memory",
                    linked_record_id=existing_memory.memory_id,
                    event=event,
                    candidate=candidate,
                    config_snapshot_id=envelope.config_snapshot_id or "",
                )
                persisted.append(existing_memory.memory_id)
                continue
            if existing_memory:
                if candidate.confidence >= existing_memory.confidence:
                    existing_memory.state = "superseded"
                    existing_memory.valid_to = utcnow()
                else:
                    existing_memory.state = "conflicted"
                    continue

        if memory_definition.cardinality == "MANY_SCORED" and existing_memory and existing_memory.canonical_key == candidate.canonical_key:
            existing_memory.confidence = min(1.0, existing_memory.confidence + 0.1)
            existing_memory.importance = min(1.0, existing_memory.importance + 0.05)
            _attach_evidence(
                session,
                linked_record_type="memory",
                linked_record_id=existing_memory.memory_id,
                event=event,
                candidate=candidate,
                config_snapshot_id=envelope.config_snapshot_id or "",
            )
            persisted.append(existing_memory.memory_id)
            continue

        if memory_definition.memory_class == "relation" and object_entity:
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
                _attach_evidence(
                    session,
                    linked_record_type="relation",
                    linked_record_id=relation.relation_id,
                    event=event,
                    candidate=candidate,
                    config_snapshot_id=envelope.config_snapshot_id or "",
                )
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
            persisted.append(relation.relation_id)
            continue

        embedding = None
        if (
            candidate.sensitivity in {"S0_PUBLIC", "S1_INTERNAL"}
            or (
                candidate.memory_type in policy.sensitivity.memory_type_allow_ceiling
                and not policy.embedding_rules.raw_sensitive_embedding_allowed
            )
        ):
            summary = candidate.value.get("summary") or candidate.value.get("topic") or candidate.value.get("address")
            if summary:
                embedding = provider.embed(str(summary))

        memory = Memory(
            memory_id=new_id("memory"),
            tenant_id=event.tenant_id,
            user_id=event.user_id,
            memory_type=candidate.memory_type,
            subject_entity_id=subject.entity_id,
            object_entity_id=object_entity.entity_id if object_entity else None,
            value_jsonb=candidate.value,
            canonical_key=candidate.canonical_key,
            state="active",
            confidence=candidate.confidence,
            importance=memory_definition.importance_default,
            sensitivity=candidate.sensitivity,
            embedding=embedding,
            config_snapshot_id=envelope.config_snapshot_id or "",
        )
        session.add(memory)
        session.flush()
        _attach_evidence(
            session,
            linked_record_type="memory",
            linked_record_id=memory.memory_id,
            event=event,
            candidate=candidate,
            config_snapshot_id=envelope.config_snapshot_id or "",
        )
        persisted.append(memory.memory_id)
    return {"action": envelope.action, "persisted": persisted}


def ingest_event(
    session: Session,
    *,
    event_request: EventIngestRequest,
    bundle: Mapping[str, ConfigDocument],
    snapshot: ConfigPublication,
) -> tuple[RuntimeApiEvent, DecisionEnvelope, Job]:
    envelope = evaluate_event(session, event_request, bundle, snapshot)
    api_definition = bundle["api_ontology"].definition_jsonb
    capability_family = "UNKNOWN"
    for entry in api_definition.get("entries", []):
        if entry.get("api_name") == event_request.api_name:
            capability_family = entry.get("capability_family", "UNKNOWN")
            break
    event = RuntimeApiEvent(
        event_id=envelope.event_id,
        tenant_id=event_request.tenant_id,
        user_id=event_request.user_id,
        session_id=event_request.session_id,
        api_name=event_request.api_name,
        capability_family=capability_family,
        request_summary=event_request.request_summary,
        response_summary=event_request.response_summary,
        structured_fields_jsonb=event_request.structured_fields,
        decision_jsonb=envelope.model_dump(mode="json"),
        config_snapshot_id=snapshot.id,
        status="decided",
        occurred_at=event_request.occurred_at or utcnow(),
    )
    job = Job(
        job_id=new_id("job"),
        job_type="persist_event",
        payload_jsonb={"event_id": event.event_id, "decision": envelope.model_dump(mode="json")},
        status="queued",
    )
    session.add(event)
    session.add(job)
    session.commit()
    session.refresh(event)
    session.refresh(job)
    return event, envelope, job


def process_job(session: Session, job: Job, bundle: Mapping[str, ConfigDocument]) -> Job:
    event = session.get(RuntimeApiEvent, job.payload_jsonb["event_id"])
    if event is None:
        raise ValueError(f"Event not found for job {job.job_id}")
    envelope = DecisionEnvelope.model_validate(job.payload_jsonb["decision"])
    job.status = "running"
    job.attempts += 1
    job.locked_at = utcnow()
    session.commit()
    result = persist_event_job(session, event, envelope, bundle)
    event.status = "processed"
    event.processed_at = utcnow()
    job.status = "completed"
    job.processed_at = utcnow()
    job.result_jsonb = result
    session.commit()
    session.refresh(job)
    return job


def process_next_job(session: Session, bundle_resolver) -> Job | None:
    job = session.scalar(
        select(Job).where(Job.status == "queued").order_by(Job.created_at.asc()).limit(1)
    )
    if job is None:
        return None
    event = session.get(RuntimeApiEvent, job.payload_jsonb["event_id"])
    if event is None:
        job.status = "failed"
        job.error_text = "Event missing"
        session.commit()
        return job
    bundle, _snapshot = bundle_resolver(session, event.tenant_id)
    return process_job(session, job, bundle)


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
    if request.relation_type:
        relations = list(
            session.scalars(
                select(Relation).where(Relation.tenant_id == request.tenant_id, Relation.relation_type == request.relation_type)
            )
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
                semantic_relevance=1.0,
                recency_score=recency,
                final_score=1.0 + (memory.confidence * 0.25) + (memory.importance * 0.2) + (recency * 0.1),
                payload=memory.value_jsonb,
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
                semantic_relevance=0.6,
                recency_score=recency,
                final_score=(0.45 * 0.6) + (0.25 * relation.strength) + (0.20 * relation.strength) + (0.10 * recency),
                payload=entity.attributes_jsonb,
            )
        )

    if request.query_text:
        query_vector = provider.embed(request.query_text)
        if query_vector:
            vector_query = (
                select(Memory)
                .where(
                    Memory.tenant_id == request.tenant_id,
                    Memory.user_id == request.user_id,
                    Memory.state == "active",
                    Memory.embedding.is_not(None),
                )
                .order_by(Memory.embedding.cosine_distance(query_vector))
                .limit(request.top_k)
            )
            for memory in session.scalars(vector_query):
                recency = _recency_score(memory.updated_at)
                semantic = _cosine_similarity(memory.embedding, query_vector)
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
                        semantic_relevance=semantic,
                        recency_score=recency,
                        final_score=(0.45 * semantic)
                        + (0.25 * memory.confidence)
                        + (0.20 * memory.importance)
                        + (0.10 * recency),
                        payload=memory.value_jsonb,
                    )
                )

    deduped: dict[tuple[str, str], QueryResult] = {}
    for result in sorted(results, key=lambda item: item.final_score, reverse=True):
        deduped.setdefault((result.record_type, result.record_id), result)
    return list(deduped.values())[: request.top_k]


def list_user_memories(session: Session, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
    query = select(Memory).where(Memory.tenant_id == tenant_id, Memory.user_id == user_id).order_by(desc(Memory.updated_at))
    return [
        {
            "memory_id": memory.memory_id,
            "memory_type": memory.memory_type,
            "state": memory.state,
            "value": memory.value_jsonb,
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
            "scope": "",
            "tenant": event.tenant_id,
            "environment": "",
            "reason_code": ",".join((event.decision_jsonb or {}).get("reason_codes", [])),
            "config_snapshot_id": event.config_snapshot_id,
            "evidence": event.event_id,
            "timestamp": event.occurred_at.isoformat(),
        }
        for event in session.scalars(query)
    ]
