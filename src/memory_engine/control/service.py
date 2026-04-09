from __future__ import annotations

import hashlib
import json
from typing import Any

import yaml
from pydantic import ValidationError
from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session

from memory_engine.auth.security import AuthUser
from memory_engine.control.schemas import (
    APIOntologyDefinition,
    ConfigDocumentResponse,
    ConfigDocumentUpsertRequest,
    DocumentKind,
    MemoryOntologyDefinition,
    PolicyProfileDefinition,
    PublishRequest,
    PublicationResponse,
    RollbackRequest,
    SimulationRequest,
    SimulationResponse,
    ValidateRequest,
    ValidationIssue,
    ValidationResponse,
    SENSITIVITY_RANK,
)
from memory_engine.db.models import AuditLog, ConfigDocument, ConfigPublication, ValidationResult
from memory_engine.id_utils import new_id, utcnow


KIND_ALIASES = {
    "api-ontology": "api_ontology",
    "memory-ontology": "memory_ontology",
    "policy-profile": "policy_profile",
    "api_ontology": "api_ontology",
    "memory_ontology": "memory_ontology",
    "policy_profile": "policy_profile",
}


def normalize_kind(kind: str) -> DocumentKind:
    normalized = KIND_ALIASES.get(kind)
    if normalized is None:
        raise ValueError(f"Unsupported kind: {kind}")
    return normalized  # type: ignore[return-value]


def to_yaml(definition: dict[str, Any]) -> str:
    return yaml.safe_dump(definition, sort_keys=False, allow_unicode=False)


def load_definition(payload: ConfigDocumentUpsertRequest) -> dict[str, Any]:
    if payload.definition_json is not None:
        return payload.definition_json
    assert payload.definition_yaml is not None
    parsed = yaml.safe_load(payload.definition_yaml) or {}
    if not isinstance(parsed, dict):
        raise ValueError("YAML definition must deserialize to an object")
    return parsed


def calculate_checksum(definition: dict[str, Any]) -> str:
    serialized = json.dumps(definition, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def document_name(kind: str, definition: dict[str, Any], fallback: str | None = None) -> str:
    return (
        fallback
        or definition.get("document_name")
        or definition.get("profile_name")
        or f"{kind.replace('_', ' ').title()} Document"
    )


def serialize_document(document: ConfigDocument) -> ConfigDocumentResponse:
    return ConfigDocumentResponse(
        id=document.id,
        kind=document.kind,
        name=document_name(document.kind, document.definition_jsonb),
        version=document.version,
        status=document.status,
        scope=document.scope,
        tenant_id=document.tenant_id,
        checksum=document.checksum,
        definition_json=document.definition_jsonb,
        definition_yaml=to_yaml(document.definition_jsonb),
        created_by=document.created_by,
        updated_at=(document.published_at or document.approved_at or document.created_at).isoformat(),
        approved_by=document.approved_by,
        published_by=document.published_by,
    )


def create_audit_log(
    session: Session,
    *,
    actor: str,
    role: str,
    action: str,
    target_kind: str,
    target_id: str,
    metadata: dict[str, Any],
) -> None:
    session.add(
        AuditLog(
            id=new_id("audit"),
            actor=actor,
            role=role,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            metadata_jsonb=metadata,
        )
    )


def _definition_model(kind: str):
    if kind == "api_ontology":
        return APIOntologyDefinition
    if kind == "memory_ontology":
        return MemoryOntologyDefinition
    return PolicyProfileDefinition


def _memory_types_from_definition(definition: dict[str, Any]) -> set[str]:
    entries = definition.get("entries", [])
    return {entry["memory_type"] for entry in entries if "memory_type" in entry}


def validate_definition(
    kind: str,
    definition: dict[str, Any],
    *,
    reference_memory_types: set[str] | None = None,
    policy_definition: dict[str, Any] | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    model = _definition_model(kind)
    try:
        parsed = model.model_validate(definition)
    except ValidationError as exc:
        for error in exc.errors():
            issues.append(
                ValidationIssue(
                    id=new_id("validation"),
                    severity="error",
                    path=".".join(str(part) for part in error["loc"]),
                    code=error["type"],
                    message=error["msg"],
                    document_id=None,
                )
            )
        return issues

    if kind == "api_ontology":
        memory_types = reference_memory_types or set()
        for entry in parsed.entries:
            for memory_type in entry.candidate_memory_types:
                if memory_types and memory_type not in memory_types:
                    issues.append(
                        ValidationIssue(
                            id=new_id("validation"),
                            severity="error",
                            path=f"entries.{entry.api_name}.candidate_memory_types",
                            code="reference.integrity",
                            message=f"Unknown memory_type reference: {memory_type}",
                            document_id=None,
                        )
                    )
    if kind == "memory_ontology" and policy_definition:
        ceilings = (
            PolicyProfileDefinition.model_validate(policy_definition)
            .sensitivity.memory_type_allow_ceiling
        )
        for entry in parsed.entries:
            ceiling = ceilings.get(entry.memory_type)
            if ceiling and SENSITIVITY_RANK[entry.allowed_sensitivity] > SENSITIVITY_RANK[ceiling]:
                issues.append(
                    ValidationIssue(
                        id=new_id("validation"),
                        severity="error",
                        path=f"entries.{entry.memory_type}.allowed_sensitivity",
                        code="sensitivity.ceiling",
                        message=(
                            f"{entry.memory_type} allows {entry.allowed_sensitivity} above policy ceiling {ceiling}"
                        ),
                        document_id=None,
                    )
                )
    return issues


def list_documents(session: Session, kind: str | None = None) -> list[ConfigDocumentResponse]:
    query: Select[tuple[ConfigDocument]] = select(ConfigDocument).order_by(
        ConfigDocument.kind, ConfigDocument.version.desc(), ConfigDocument.created_at.desc()
    )
    if kind:
        query = query.where(ConfigDocument.kind == normalize_kind(kind))
    return [serialize_document(row) for row in session.scalars(query)]


def get_document_or_404(session: Session, document_id: str) -> ConfigDocument:
    document = session.get(ConfigDocument, document_id)
    if document is None:
        raise ValueError(f"Config document not found: {document_id}")
    return document


def save_document(
    session: Session,
    *,
    kind: str,
    payload: ConfigDocumentUpsertRequest,
    actor: AuthUser,
    document_id: str | None = None,
) -> ConfigDocumentResponse:
    normalized_kind = normalize_kind(kind)
    definition = load_definition(payload)
    checksum = calculate_checksum(definition)

    if document_id is None:
        latest_version = session.scalar(
            select(ConfigDocument.version)
            .where(
                ConfigDocument.kind == normalized_kind,
                ConfigDocument.scope == payload.scope,
                ConfigDocument.tenant_id == payload.tenant_id,
            )
            .order_by(ConfigDocument.version.desc())
            .limit(1)
        )
        document = ConfigDocument(
            id=new_id("cfgdoc"),
            kind=normalized_kind,
            scope=payload.scope,
            tenant_id=payload.tenant_id,
            version=payload.version or ((latest_version or 0) + 1),
            status="draft",
            base_version=payload.base_version,
            definition_jsonb=definition,
            checksum=checksum,
            created_by=actor.email,
        )
        session.add(document)
        create_audit_log(
            session,
            actor=actor.email,
            role=actor.role,
            action="config.create",
            target_kind=normalized_kind,
            target_id=document.id,
            metadata={"scope": payload.scope, "tenant_id": payload.tenant_id},
        )
    else:
        document = get_document_or_404(session, document_id)
        if document.status == "published":
            raise ValueError("Published documents are immutable")
        document.definition_jsonb = definition
        document.checksum = checksum
        document.status = "draft"
        document.approved_by = None
        document.approved_at = None
        create_audit_log(
            session,
            actor=actor.email,
            role=actor.role,
            action="config.update",
            target_kind=normalized_kind,
            target_id=document.id,
            metadata={"scope": document.scope, "tenant_id": document.tenant_id},
        )

    session.commit()
    session.refresh(document)
    return serialize_document(document)


def approve_document(session: Session, document_id: str, actor: AuthUser) -> ConfigDocument:
    document = get_document_or_404(session, document_id)
    if document.status not in {"draft", "validated"}:
        raise ValueError("Only draft or validated documents can be approved")
    document.status = "approved"
    document.approved_by = actor.email
    document.approved_at = utcnow()
    create_audit_log(
        session,
        actor=actor.email,
        role=actor.role,
        action="config.approve",
        target_kind=document.kind,
        target_id=document.id,
        metadata={"scope": document.scope, "tenant_id": document.tenant_id},
    )
    session.commit()
    session.refresh(document)
    return document


def _resolve_validation_bundle(session: Session, request: ValidateRequest) -> dict[str, ConfigDocument]:
    bundle: dict[str, ConfigDocument] = {}
    ids = list(request.document_ids)
    if request.config_id:
        ids.append(request.config_id)
    for explicit_id in [
        request.api_ontology_document_id,
        request.memory_ontology_document_id,
        request.policy_profile_document_id,
    ]:
        if explicit_id:
            ids.append(explicit_id)
    for document_id in ids:
        document = get_document_or_404(session, document_id)
        bundle[document.kind] = document

    if set(bundle) != {"api_ontology", "memory_ontology", "policy_profile"}:
        active = get_active_publication(
            session, environment=request.environment, scope="global", tenant_id=request.tenant_id
        )
        if active:
            for kind, field in {
                "api_ontology": active.api_ontology_document_id,
                "memory_ontology": active.memory_ontology_document_id,
                "policy_profile": active.policy_profile_document_id,
            }.items():
                bundle.setdefault(kind, get_document_or_404(session, field))
    return bundle


def validate_documents(session: Session, request: ValidateRequest) -> ValidationResponse:
    bundle = _resolve_validation_bundle(session, request)
    issues: list[ValidationIssue] = []
    memory_types = set()
    policy_definition: dict[str, Any] | None = None

    memory_doc = bundle.get("memory_ontology")
    if memory_doc:
        memory_types = _memory_types_from_definition(memory_doc.definition_jsonb)
    policy_doc = bundle.get("policy_profile")
    if policy_doc:
        policy_definition = policy_doc.definition_jsonb

    for kind, document in bundle.items():
        document_issues = [
            issue.model_copy(update={"document_id": document.id})
            for issue in validate_definition(
                kind,
                document.definition_jsonb,
                reference_memory_types=memory_types,
                policy_definition=policy_definition,
            )
        ]
        issues.extend(document_issues)

    for document in bundle.values():
        session.execute(
            update(ValidationResult)
            .where(ValidationResult.config_document_id == document.id)
            .values(message=ValidationResult.message)
        )
        for issue in issues:
            if issue.document_id != document.id:
                continue
            session.add(
                ValidationResult(
                    id=issue.id,
                    config_document_id=document.id,
                    severity=issue.severity,
                    path=issue.path,
                    code=issue.code,
                    message=issue.message,
                )
            )
        if not any(issue.severity == "error" for issue in issues):
            document.status = "validated"
    session.commit()

    status = "fail" if any(issue.severity == "error" for issue in issues) else "pass"
    return ValidationResponse(
        status=status,
        validated_document_ids=[document.id for document in bundle.values()],
        issues=issues,
    )


def _snapshot_hash(documents: list[ConfigDocument], environment: str, scope: str, tenant_id: str | None) -> str:
    payload = {
        "documents": {document.kind: document.checksum for document in documents},
        "environment": environment,
        "scope": scope,
        "tenant_id": tenant_id,
    }
    return calculate_checksum(payload)


def get_active_publication(
    session: Session,
    *,
    environment: str,
    scope: str | None = None,
    tenant_id: str | None = None,
) -> ConfigPublication | None:
    query = select(ConfigPublication).where(
        ConfigPublication.environment == environment, ConfigPublication.is_active.is_(True)
    )
    if scope is not None:
        query = query.where(ConfigPublication.scope == scope)
    if tenant_id is not None:
        query = query.where(ConfigPublication.tenant_id == tenant_id)
    query = query.order_by(ConfigPublication.published_at.desc()).limit(1)
    return session.scalar(query)


def resolve_snapshot(
    session: Session,
    *,
    environment: str,
    tenant_id: str | None,
) -> ConfigPublication | None:
    precedence = [
        ("emergency_override", tenant_id),
        ("tenant", tenant_id),
        ("environment", None),
        ("global", None),
    ]
    for scope, scoped_tenant in precedence:
        snapshot = get_active_publication(session, environment=environment, scope=scope, tenant_id=scoped_tenant)
        if snapshot:
            return snapshot
    return None


def _resolve_publish_bundle(session: Session, request: PublishRequest) -> dict[str, ConfigDocument]:
    bundle: dict[str, ConfigDocument] = {}
    for document_id in [
        request.config_id,
        request.api_ontology_document_id,
        request.memory_ontology_document_id,
        request.policy_profile_document_id,
    ]:
        if document_id is None:
            continue
        document = get_document_or_404(session, document_id)
        bundle[document.kind] = document

    if set(bundle) != {"api_ontology", "memory_ontology", "policy_profile"}:
        active = get_active_publication(
            session, environment=request.environment, scope=request.scope, tenant_id=request.tenant_id
        )
        if active:
            bundle.setdefault("api_ontology", get_document_or_404(session, active.api_ontology_document_id))
            bundle.setdefault("memory_ontology", get_document_or_404(session, active.memory_ontology_document_id))
            bundle.setdefault("policy_profile", get_document_or_404(session, active.policy_profile_document_id))
    if set(bundle) != {"api_ontology", "memory_ontology", "policy_profile"}:
        raise ValueError("Publishing requires API ontology, memory ontology, and policy profile documents")
    return bundle


def publish_documents(session: Session, request: PublishRequest, actor: AuthUser) -> PublicationResponse:
    bundle = _resolve_publish_bundle(session, request)
    if any(document.status != "approved" for document in bundle.values()):
        raise ValueError("All documents must be approved before publish")

    validation = validate_documents(
        session,
        ValidateRequest(
            api_ontology_document_id=bundle["api_ontology"].id,
            memory_ontology_document_id=bundle["memory_ontology"].id,
            policy_profile_document_id=bundle["policy_profile"].id,
            environment=request.environment,
            tenant_id=request.tenant_id,
        ),
    )
    if validation.status == "fail":
        raise ValueError("Cannot publish documents with validation errors")

    prior_active = get_active_publication(
        session, environment=request.environment, scope=request.scope, tenant_id=request.tenant_id
    )
    if prior_active:
        prior_active.is_active = False

    publication = ConfigPublication(
        id=new_id("cfgsnap"),
        environment=request.environment,
        scope=request.scope,
        tenant_id=request.tenant_id,
        api_ontology_document_id=bundle["api_ontology"].id,
        memory_ontology_document_id=bundle["memory_ontology"].id,
        policy_profile_document_id=bundle["policy_profile"].id,
        snapshot_hash=_snapshot_hash(list(bundle.values()), request.environment, request.scope, request.tenant_id),
        is_active=True,
        published_by=actor.email,
        rollback_of=None,
    )
    session.add(publication)
    for document in bundle.values():
        document.status = "published"
        document.published_by = actor.email
        document.published_at = utcnow()
    create_audit_log(
        session,
        actor=actor.email,
        role=actor.role,
        action="config.publish",
        target_kind="config_snapshot",
        target_id=publication.id,
        metadata={
            "scope": request.scope,
            "tenant_id": request.tenant_id,
            "environment": request.environment,
            "release_notes": request.release_notes,
        },
    )
    session.commit()
    session.refresh(publication)
    return PublicationResponse.model_validate(publication, from_attributes=True)


def rollback_publication(session: Session, request: RollbackRequest, actor: AuthUser) -> PublicationResponse:
    target = session.get(ConfigPublication, request.snapshot_id)
    if target is None:
        raise ValueError(f"Snapshot not found: {request.snapshot_id}")

    active = get_active_publication(
        session, environment=target.environment, scope=target.scope, tenant_id=target.tenant_id
    )
    if active:
        active.is_active = False

    rollback = ConfigPublication(
        id=new_id("cfgsnap"),
        environment=target.environment,
        scope=target.scope,
        tenant_id=target.tenant_id,
        api_ontology_document_id=target.api_ontology_document_id,
        memory_ontology_document_id=target.memory_ontology_document_id,
        policy_profile_document_id=target.policy_profile_document_id,
        snapshot_hash=target.snapshot_hash,
        is_active=True,
        published_by=actor.email,
        rollback_of=target.id,
    )
    session.add(rollback)
    create_audit_log(
        session,
        actor=actor.email,
        role=actor.role,
        action="config.rollback",
        target_kind="config_snapshot",
        target_id=rollback.id,
        metadata={"rollback_of": target.id},
    )
    session.commit()
    session.refresh(rollback)
    return PublicationResponse.model_validate(rollback, from_attributes=True)


def list_publications(session: Session) -> list[PublicationResponse]:
    query = select(ConfigPublication).order_by(ConfigPublication.published_at.desc())
    return [PublicationResponse.model_validate(row, from_attributes=True) for row in session.scalars(query)]


def list_audit_logs(session: Session) -> list[dict[str, Any]]:
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    return [
        {
            "id": row.id,
            "actor": row.actor,
            "role": row.role,
            "action": row.action,
            "document_kind": row.target_kind,
            "document_version": row.metadata_jsonb.get("version", ""),
            "timestamp": row.created_at.isoformat(),
            "diff_ref": row.metadata_jsonb,
        }
        for row in session.scalars(query)
    ]


def list_validation_results(session: Session) -> list[ValidationIssue]:
    query = select(ValidationResult).order_by(ValidationResult.created_at.desc())
    return [
        ValidationIssue(
            id=row.id,
            severity=row.severity,
            path=row.path,
            code=row.code,
            message=row.message,
            document_id=row.config_document_id,
        )
        for row in session.scalars(query)
    ]


def simulate(
    session: Session,
    request: SimulationRequest,
    *,
    evaluator,
) -> SimulationResponse:
    active = resolve_snapshot(session, environment=request.environment, tenant_id=request.tenant_id)
    candidate_bundle = _resolve_validation_bundle(
        session,
        ValidateRequest(
            config_id=request.config_id,
            api_ontology_document_id=request.api_ontology_document_id,
            memory_ontology_document_id=request.memory_ontology_document_id,
            policy_profile_document_id=request.policy_profile_document_id,
            environment=request.environment,
            tenant_id=request.tenant_id,
        ),
    )
    active_bundle = None
    if active:
        active_bundle = {
            "api_ontology": get_document_or_404(session, active.api_ontology_document_id),
            "memory_ontology": get_document_or_404(session, active.memory_ontology_document_id),
            "policy_profile": get_document_or_404(session, active.policy_profile_document_id),
        }

    old_decision = evaluator(request.sample_event, active_bundle) if active_bundle else None
    new_decision = evaluator(request.sample_event, candidate_bundle)
    old_reasons = set((old_decision or {}).get("reason_codes", []))
    new_reasons = set(new_decision.get("reason_codes", []))
    old_candidates = {(candidate["memory_type"]) for candidate in (old_decision or {}).get("candidates", [])}
    new_candidates = {candidate["memory_type"] for candidate in new_decision.get("candidates", [])}

    return SimulationResponse(
        active_snapshot_id=active.id if active else None,
        candidate_snapshot_id=None,
        old_decision=old_decision,
        new_decision=new_decision,
        changed_reason_codes=sorted(old_reasons ^ new_reasons),
        changed_memory_candidates=sorted(old_candidates ^ new_candidates),
        expected_write_delta=int((new_decision.get("action") == "UPSERT")) - int(
            (old_decision or {}).get("action") == "UPSERT"
        ),
        expected_block_delta=int((new_decision.get("action") == "BLOCK")) - int(
            (old_decision or {}).get("action") == "BLOCK"
        ),
    )
