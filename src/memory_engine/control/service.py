from __future__ import annotations

import hashlib
import json
from typing import Any

import yaml
from pydantic import ValidationError
from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session

from memory_engine.auth.security import AuthUser
from memory_engine.config.settings import get_settings
from memory_engine.control.api_package import collect_api_ontology_compile_issues
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
from memory_engine.ops.metrics import increment_metric
from memory_engine.runtime.extractors import EXTRACTOR_REGISTRY
from memory_engine.runtime.prompts import get_prompt_template


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


def apply_document_name(kind: str, definition: dict[str, Any], name: str | None) -> dict[str, Any]:
    if not name:
        return definition
    updated = dict(definition)
    if kind == "policy_profile":
        updated["profile_name"] = name
    else:
        updated["document_name"] = name
    return updated


def serialize_document(document: ConfigDocument) -> ConfigDocumentResponse:
    return ConfigDocumentResponse(
        id=document.id,
        kind=document.kind,
        name=document_name(document.kind, document.definition_jsonb),
        version=document.version,
        status=document.status,
        scope=document.scope,
        tenant_id=document.tenant_id,
        base_version=document.base_version,
        checksum=document.checksum,
        definition_json=document.definition_jsonb,
        definition_yaml=to_yaml(document.definition_jsonb),
        created_by=document.created_by,
        created_at=document.created_at.isoformat(),
        updated_at=(document.published_at or document.approved_at or document.created_at).isoformat(),
        approved_at=document.approved_at.isoformat() if document.approved_at else None,
        approved_by=document.approved_by,
        published_by=document.published_by,
        published_at=document.published_at.isoformat() if document.published_at else None,
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
    payload = {
        "environment": get_settings().environment,
        **metadata,
    }
    session.add(
        AuditLog(
            id=new_id("audit"),
            actor=actor,
            role=role,
            action=action,
            target_kind=target_kind,
            target_id=target_id,
            metadata_jsonb=payload,
        )
    )


def _publication_response(session: Session, publication: ConfigPublication) -> PublicationResponse:
    api_doc = get_document_or_404(session, publication.api_ontology_document_id)
    memory_doc = get_document_or_404(session, publication.memory_ontology_document_id)
    policy_doc = get_document_or_404(session, publication.policy_profile_document_id)
    return PublicationResponse(
        id=publication.id,
        environment=publication.environment,
        scope=publication.scope,
        tenant_id=publication.tenant_id,
        snapshot_hash=publication.snapshot_hash,
        is_active=publication.is_active,
        release_notes=publication.release_notes,
        published_by=publication.published_by,
        published_at=publication.published_at,
        rollback_of=publication.rollback_of,
        api_ontology_document_id=api_doc.id,
        memory_ontology_document_id=memory_doc.id,
        policy_profile_document_id=policy_doc.id,
        api_ontology_document_name=document_name(api_doc.kind, api_doc.definition_jsonb),
        memory_ontology_document_name=document_name(memory_doc.kind, memory_doc.definition_jsonb),
        policy_profile_document_name=document_name(policy_doc.kind, policy_doc.definition_jsonb),
        api_ontology_document_version=api_doc.version,
        memory_ontology_document_version=memory_doc.version,
        policy_profile_document_version=policy_doc.version,
    )


def _ensure_bundle_scope(bundle: dict[str, ConfigDocument], *, scope: str, tenant_id: str | None) -> None:
    for document in bundle.values():
        if document.scope != scope:
            raise ValueError(
                f"Document {document.id} has scope {document.scope}; publish scope must match the selected documents"
            )
        if document.tenant_id != tenant_id:
            raise ValueError(
                f"Document {document.id} has tenant_id {document.tenant_id!r}; publish tenant_id must match"
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
        precedence_keys = set()
        if policy_definition:
            precedence_keys = set(PolicyProfileDefinition.model_validate(policy_definition).source_precedence)
        for issue in collect_api_ontology_compile_issues(parsed):
            issues.append(
                ValidationIssue(
                    id=new_id("validation"),
                    severity="error",
                    path=issue.path,
                    code=issue.code,
                    message=issue.message,
                    document_id=None,
                )
            )
        modules = parsed.modules or []
        if not modules and parsed.entries:
            modules = [
                type("LegacyModule", (), {"module_key": "legacy.default", "entries": parsed.entries})()
            ]
        for module in modules:
            for entry in module.entries:
                entry_path = f"modules.{module.module_key}.entries.{entry.entry_id or entry.api_name}"
                for memory_type in entry.candidate_memory_types:
                    if memory_types and memory_type not in memory_types:
                        issues.append(
                            ValidationIssue(
                                id=new_id("validation"),
                                severity="error",
                                path=f"{entry_path}.candidate_memory_types",
                                code="reference.integrity",
                                message=f"Unknown memory_type reference: {memory_type}",
                                document_id=None,
                            )
                        )
                for extractor_name in entry.extractors:
                    if extractor_name not in EXTRACTOR_REGISTRY:
                        issues.append(
                            ValidationIssue(
                                id=new_id("validation"),
                                severity="error",
                                path=f"{entry_path}.extractors",
                                code="extractor.unknown",
                                message=f"Unknown extractor: {extractor_name}",
                                document_id=None,
                            )
                        )
                if precedence_keys and entry.source_precedence_key not in precedence_keys:
                    issues.append(
                        ValidationIssue(
                            id=new_id("validation"),
                            severity="error",
                            path=f"{entry_path}.source_precedence_key",
                            code="precedence.unknown",
                            message=f"Unknown source_precedence_key: {entry.source_precedence_key}",
                            document_id=None,
                        )
                    )
                if entry.llm_usage_mode != "DISABLED" and entry.prompt_template_key:
                    try:
                        get_prompt_template(entry.prompt_template_key)
                    except ValueError:
                        issues.append(
                            ValidationIssue(
                                id=new_id("validation"),
                                severity="error",
                                path=f"{entry_path}.prompt_template_key",
                                code="prompt_template.unknown",
                                message=f"Unknown prompt_template_key: {entry.prompt_template_key}",
                                document_id=None,
                            )
                        )
        for workflow in parsed.workflows:
            if memory_types and workflow.intent_memory_type not in memory_types:
                issues.append(
                    ValidationIssue(
                        id=new_id("validation"),
                        severity="error",
                        path=f"workflows.{workflow.workflow_key}.intent_memory_type",
                        code="reference.integrity",
                        message=f"Unknown memory_type reference: {workflow.intent_memory_type}",
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
    if kind == "policy_profile":
        settings = get_settings()
        registry = settings.inference_provider_registry or {}
        referenced_providers = {parsed.model_inference.provider_gate.default_provider}
        for rule in parsed.model_inference.provider_gate.rules:
            referenced_providers.update(rule.provider_order)
            for memory_type in rule.memory_types:
                if reference_memory_types and memory_type not in reference_memory_types:
                    issues.append(
                        ValidationIssue(
                            id=new_id("validation"),
                            severity="error",
                            path="model_inference.provider_gate.rules.memory_types",
                            code="memory_type.unknown",
                            message=f"Unknown memory_type reference in provider gate: {memory_type}",
                            document_id=None,
                        )
                    )
        for provider_id in sorted(referenced_providers):
            provider_config = registry.get(provider_id)
            if provider_config is None:
                issues.append(
                    ValidationIssue(
                        id=new_id("validation"),
                        severity="error",
                        path="model_inference.provider_gate",
                        code="inference_provider.unknown",
                        message=f"Unknown inference provider id: {provider_id}",
                        document_id=None,
                    )
                )
            elif not provider_config.enabled:
                issues.append(
                    ValidationIssue(
                        id=new_id("validation"),
                        severity="error",
                        path="model_inference.provider_gate",
                        code="inference_provider.disabled",
                        message=f"Inference provider is disabled in settings: {provider_id}",
                        document_id=None,
                    )
                )
    return issues


def list_documents(
    session: Session,
    kind: str | None = None,
    *,
    scope: str | None = None,
    tenant_id: str | None = None,
    status: str | None = None,
) -> list[ConfigDocumentResponse]:
    query: Select[tuple[ConfigDocument]] = select(ConfigDocument).order_by(
        ConfigDocument.kind, ConfigDocument.version.desc(), ConfigDocument.created_at.desc()
    )
    if kind:
        query = query.where(ConfigDocument.kind == normalize_kind(kind))
    if scope:
        query = query.where(ConfigDocument.scope == scope)
    if tenant_id:
        query = query.where(ConfigDocument.tenant_id == tenant_id)
    if status:
        query = query.where(ConfigDocument.status == status)
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
    definition = apply_document_name(normalized_kind, load_definition(payload), payload.name)
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
            metadata={
                "scope": payload.scope,
                "tenant_id": payload.tenant_id,
                "version": document.version,
                "after_checksum": checksum,
            },
        )
    else:
        document = get_document_or_404(session, document_id)
        if document.status == "archived":
            raise ValueError("Archived documents are immutable")

        if document.status in {"approved", "published"}:
            latest_version = session.scalar(
                select(ConfigDocument.version)
                .where(
                    ConfigDocument.kind == normalized_kind,
                    ConfigDocument.scope == document.scope,
                    ConfigDocument.tenant_id == document.tenant_id,
                )
                .order_by(ConfigDocument.version.desc())
                .limit(1)
            )
            next_document = ConfigDocument(
                id=new_id("cfgdoc"),
                kind=normalized_kind,
                scope=document.scope,
                tenant_id=document.tenant_id,
                version=(latest_version or document.version) + 1,
                status="draft",
                base_version=document.version,
                definition_jsonb=definition,
                checksum=checksum,
                created_by=actor.email,
            )
            session.add(next_document)
            create_audit_log(
                session,
                actor=actor.email,
                role=actor.role,
                action="config.revise",
                target_kind=normalized_kind,
                target_id=next_document.id,
                metadata={
                    "scope": next_document.scope,
                    "tenant_id": next_document.tenant_id,
                    "version": next_document.version,
                    "base_version": document.version,
                    "before_checksum": document.checksum,
                    "after_checksum": checksum,
                },
            )
            document = next_document
        else:
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
                metadata={
                    "scope": document.scope,
                    "tenant_id": document.tenant_id,
                    "version": document.version,
                    "after_checksum": checksum,
                },
            )

    session.commit()
    session.refresh(document)
    return serialize_document(document)


def approve_document(session: Session, document_id: str, actor: AuthUser) -> ConfigDocument:
    document = get_document_or_404(session, document_id)
    if document.status != "validated":
        raise ValueError("Only validated documents can be approved")
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
        metadata={
            "scope": document.scope,
            "tenant_id": document.tenant_id,
            "version": document.version,
            "checksum": document.checksum,
        },
    )
    session.commit()
    session.refresh(document)
    return document


def archive_document(session: Session, document_id: str, actor: AuthUser) -> ConfigDocument:
    document = get_document_or_404(session, document_id)
    if document.status == "archived":
        return document
    active_reference = session.scalar(
        select(ConfigPublication).where(
            ConfigPublication.is_active.is_(True),
            (
                (ConfigPublication.api_ontology_document_id == document.id)
                | (ConfigPublication.memory_ontology_document_id == document.id)
                | (ConfigPublication.policy_profile_document_id == document.id)
            ),
        )
    )
    if active_reference is not None:
        raise ValueError("Active snapshot documents cannot be archived")
    document.status = "archived"
    create_audit_log(
        session,
        actor=actor.email,
        role=actor.role,
        action="config.archive",
        target_kind=document.kind,
        target_id=document.id,
        metadata={
            "scope": document.scope,
            "tenant_id": document.tenant_id,
            "version": document.version,
            "checksum": document.checksum,
        },
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
        active = resolve_snapshot(session, environment=request.environment, tenant_id=request.tenant_id)
        if active is not None:
            for kind, field in {
                "api_ontology": active.api_ontology_document_id,
                "memory_ontology": active.memory_ontology_document_id,
                "policy_profile": active.policy_profile_document_id,
            }.items():
                bundle.setdefault(kind, get_document_or_404(session, field))
    return bundle


def validate_documents(
    session: Session,
    request: ValidateRequest,
    actor: AuthUser | None = None,
) -> ValidationResponse:
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

    for document in bundle.values():
        session.execute(delete(ValidationResult).where(ValidationResult.config_document_id == document.id))

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
        persisted_issues = document_issues or [
            ValidationIssue(
                id=new_id("validation"),
                severity="info",
                path="$",
                code="validation.pass",
                message="No validation issues detected.",
                document_id=document.id,
            )
        ]
        issues.extend(persisted_issues)
        for issue in persisted_issues:
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
        if actor is not None:
            document_issues = [issue for issue in persisted_issues if issue.severity != "info"]
            document_status = (
                "fail"
                if any(issue.severity == "error" for issue in document_issues)
                else "warn"
                if any(issue.severity == "warn" for issue in document_issues)
                else "pass"
            )
            create_audit_log(
                session,
                actor=actor.email,
                role=actor.role,
                action="config.validate",
                target_kind=document.kind,
                target_id=document.id,
                metadata={
                    "scope": document.scope,
                    "tenant_id": document.tenant_id,
                    "environment": request.environment,
                    "version": document.version,
                    "checksum": document.checksum,
                    "validation_status": document_status,
                    "issue_count": len(document_issues),
                },
            )
        has_document_error = any(issue.severity == "error" and issue.document_id == document.id for issue in issues)
        if not has_document_error and document.status not in {"published", "archived"}:
            document.status = "validated"
    session.commit()

    if any(issue.severity == "error" for issue in issues):
        status = "fail"
        increment_metric(session, "config_validation_failures", labels={"environment": request.environment})
        session.commit()
    elif any(issue.severity == "warn" for issue in issues):
        status = "warn"
    else:
        status = "pass"
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


def find_matching_publication(
    session: Session,
    *,
    environment: str,
    api_ontology_document_id: str,
    memory_ontology_document_id: str,
    policy_profile_document_id: str,
    tenant_id: str | None = None,
) -> ConfigPublication | None:
    query = (
        select(ConfigPublication)
        .where(ConfigPublication.environment == environment)
        .where(ConfigPublication.api_ontology_document_id == api_ontology_document_id)
        .where(ConfigPublication.memory_ontology_document_id == memory_ontology_document_id)
        .where(ConfigPublication.policy_profile_document_id == policy_profile_document_id)
    )
    if tenant_id is None:
        query = query.where(ConfigPublication.scope == "global").where(ConfigPublication.tenant_id.is_(None))
    else:
        query = query.where(
            (
                (ConfigPublication.scope == "tenant") & (ConfigPublication.tenant_id == tenant_id)
            )
            | ((ConfigPublication.scope == "global") & ConfigPublication.tenant_id.is_(None))
        )
    query = query.order_by(ConfigPublication.is_active.desc(), ConfigPublication.published_at.desc()).limit(1)
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
    _ensure_bundle_scope(bundle, scope=request.scope, tenant_id=request.tenant_id)
    if any(document.status not in {"approved", "published"} for document in bundle.values()):
        raise ValueError("All documents must be approved or previously published before publish")

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
        release_notes=request.release_notes,
        is_active=True,
        published_by=actor.email,
        rollback_of=None,
    )
    session.add(publication)
    for document in bundle.values():
        if document.status != "published":
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
            "snapshot_hash": publication.snapshot_hash,
            "documents": {
                kind: {"id": document.id, "version": document.version, "checksum": document.checksum}
                for kind, document in bundle.items()
            },
        },
    )
    increment_metric(
        session,
        "config_publish_events",
        labels={
            "environment": request.environment,
            "scope": request.scope,
            "tenant_id": request.tenant_id or "__global__",
        },
    )
    session.commit()
    session.refresh(publication)
    return _publication_response(session, publication)


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
        release_notes=f"Rollback to snapshot {target.id}",
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
        metadata={
            "rollback_of": target.id,
            "scope": target.scope,
            "tenant_id": target.tenant_id,
            "environment": target.environment,
            "snapshot_hash": target.snapshot_hash,
        },
    )
    increment_metric(
        session,
        "config_rollback_events",
        labels={
            "environment": target.environment,
            "scope": target.scope,
            "tenant_id": target.tenant_id or "__global__",
        },
    )
    session.commit()
    session.refresh(rollback)
    return _publication_response(session, rollback)


def list_publications(
    session: Session,
    *,
    environment: str | None = None,
    scope: str | None = None,
    tenant_id: str | None = None,
    is_active: bool | None = None,
) -> list[PublicationResponse]:
    query = select(ConfigPublication).order_by(ConfigPublication.published_at.desc())
    if environment is not None:
        query = query.where(ConfigPublication.environment == environment)
    if scope is not None:
        query = query.where(ConfigPublication.scope == scope)
    if tenant_id is not None:
        query = query.where(ConfigPublication.tenant_id == tenant_id)
    if is_active is not None:
        query = query.where(ConfigPublication.is_active.is_(is_active))
    return [_publication_response(session, row) for row in session.scalars(query)]


def list_audit_logs(
    session: Session,
    *,
    action: str | None = None,
    target_kind: str | None = None,
    scope: str | None = None,
    tenant_id: str | None = None,
) -> list[dict[str, Any]]:
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action is not None:
        query = query.where(AuditLog.action == action)
    if target_kind is not None:
        query = query.where(AuditLog.target_kind == target_kind)
    return [
        {
            "id": row.id,
            "actor": row.actor,
            "role": row.role,
            "action": row.action,
            "document_kind": row.target_kind,
            "document_id": row.target_id,
            "scope": row.metadata_jsonb.get("scope"),
            "tenant_id": row.metadata_jsonb.get("tenant_id"),
            "environment": row.metadata_jsonb.get("environment"),
            "document_version": row.metadata_jsonb.get("version", ""),
            "before_checksum": row.metadata_jsonb.get("before_checksum"),
            "after_checksum": row.metadata_jsonb.get("after_checksum"),
            "snapshot_hash": row.metadata_jsonb.get("snapshot_hash"),
            "rollback_of": row.metadata_jsonb.get("rollback_of"),
            "timestamp": row.created_at.isoformat(),
            "diff_ref": row.metadata_jsonb,
        }
        for row in session.scalars(query)
        if (scope is None or row.metadata_jsonb.get("scope") == scope)
        and (tenant_id is None or row.metadata_jsonb.get("tenant_id") == tenant_id)
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
    candidate_snapshot = find_matching_publication(
        session,
        environment=request.environment,
        api_ontology_document_id=candidate_bundle["api_ontology"].id,
        memory_ontology_document_id=candidate_bundle["memory_ontology"].id,
        policy_profile_document_id=candidate_bundle["policy_profile"].id,
        tenant_id=request.tenant_id,
    )
    active_bundle = None
    if active:
        active_bundle = {
            "api_ontology": get_document_or_404(session, active.api_ontology_document_id),
            "memory_ontology": get_document_or_404(session, active.memory_ontology_document_id),
            "policy_profile": get_document_or_404(session, active.policy_profile_document_id),
        }

    old_decision = evaluator(request.sample_event, active_bundle, active) if active_bundle else None
    new_decision = evaluator(request.sample_event, candidate_bundle, candidate_snapshot)
    old_reasons = set((old_decision or {}).get("reason_codes", []))
    new_reasons = set(new_decision.get("reason_codes", []))
    old_candidates = {(candidate["memory_type"]) for candidate in (old_decision or {}).get("candidates", [])}
    new_candidates = {candidate["memory_type"] for candidate in new_decision.get("candidates", [])}

    return SimulationResponse(
        active_snapshot_id=active.id if active else None,
        candidate_snapshot_id=candidate_snapshot.id if candidate_snapshot else None,
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
