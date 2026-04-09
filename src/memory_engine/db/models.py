from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from memory_engine.db.base import Base
from memory_engine.id_utils import utcnow


class ConfigDocument(Base):
    __tablename__ = "config_documents"
    __table_args__ = {"schema": "control"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    scope: Mapped[str] = mapped_column(String(32), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    base_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    definition_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConfigPublication(Base):
    __tablename__ = "config_publications"
    __table_args__ = {"schema": "control"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    environment: Mapped[str] = mapped_column(String(32), index=True)
    scope: Mapped[str] = mapped_column(String(32), index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    api_ontology_document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("control.config_documents.id"), nullable=False
    )
    memory_ontology_document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("control.config_documents.id"), nullable=False
    )
    policy_profile_document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("control.config_documents.id"), nullable=False
    )
    snapshot_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    published_by: Mapped[str] = mapped_column(String(255), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    rollback_of: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("control.config_publications.id"), nullable=True
    )


class ValidationResult(Base):
    __tablename__ = "validation_results"
    __table_args__ = {"schema": "control"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    config_document_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("control.config_documents.id"), nullable=False, index=True
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "control"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RuntimeApiEvent(Base):
    __tablename__ = "api_events"
    __table_args__ = {"schema": "runtime"}

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    api_name: Mapped[str] = mapped_column(String(255), index=True)
    capability_family: Mapped[str] = mapped_column(String(64), nullable=False)
    request_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_fields_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False)
    decision_jsonb: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    config_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SignalCounter(Base):
    __tablename__ = "signal_counters"
    __table_args__ = {"schema": "runtime"}

    signal_key: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    memory_type: Mapped[str] = mapped_column(String(128), index=True)
    canonical_object_key: Mapped[str] = mapped_column(String(255), index=True)
    decayed_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unique_sessions_30d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_days_30d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_diversity_30d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    same_session_burst_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("tenant_id", "entity_type", "canonical_key", name="uq_entity_canonical_key"),
        {"schema": "runtime"},
    )

    entity_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    canonical_key: Mapped[str] = mapped_column(String(255), index=True)
    attributes_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = {"schema": "runtime"}

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("runtime.entities.entity_id"), nullable=False)
    alias: Mapped[str] = mapped_column(String(255), index=True)
    alias_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = {"schema": "runtime"}

    memory_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    memory_type: Mapped[str] = mapped_column(String(128), index=True)
    subject_entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("runtime.entities.entity_id"), nullable=False)
    object_entity_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("runtime.entities.entity_id"), nullable=True
    )
    value_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    canonical_key: Mapped[str] = mapped_column(String(255), index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sensitivity: Mapped[str] = mapped_column(String(32), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(8), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supersedes: Mapped[str | None] = mapped_column(String(64), ForeignKey("runtime.memories.memory_id"), nullable=True)
    config_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Relation(Base):
    __tablename__ = "relations"
    __table_args__ = {"schema": "runtime"}

    relation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    subject_entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("runtime.entities.entity_id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(128), index=True)
    object_entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("runtime.entities.entity_id"), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = {"schema": "runtime"}

    evidence_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    linked_record_type: Mapped[str] = mapped_column(String(64), nullable=False)
    linked_record_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_event_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("runtime.api_events.event_id"), nullable=False, index=True
    )
    api_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_trust: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    extraction_method: Mapped[str] = mapped_column(String(128), nullable=False)
    config_snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = {"schema": "ops"}

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result_jsonb: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MetricRollup(Base):
    __tablename__ = "metrics_rollups"
    __table_args__ = {"schema": "ops"}

    metric_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    bucket_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    labels_jsonb: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

