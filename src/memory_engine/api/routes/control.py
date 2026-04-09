from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from memory_engine.auth.security import AuthUser, get_current_user, require_roles
from memory_engine.control.schemas import (
    ApproveResponse,
    ConfigDocumentResponse,
    ConfigDocumentUpsertRequest,
    PublishRequest,
    PublicationResponse,
    RollbackRequest,
    SimulationRequest,
    SimulationResponse,
    ValidateRequest,
    ValidationIssue,
    ValidationResponse,
)
from memory_engine.control.service import (
    approve_document,
    get_document_or_404,
    list_audit_logs,
    list_documents,
    list_publications,
    list_validation_results,
    normalize_kind,
    publish_documents,
    rollback_publication,
    save_document,
    serialize_document,
    simulate,
    to_yaml,
    validate_documents,
)
from memory_engine.runtime.policy import evaluate_event
from memory_engine.runtime.schemas import EventIngestRequest
from memory_engine.db.session import get_session

router = APIRouter(prefix="/v1/control", tags=["control"])


def _save_document(
    *,
    kind: str,
    payload: ConfigDocumentUpsertRequest,
    session: Session,
    actor: AuthUser,
    document_id: str | None = None,
) -> ConfigDocumentResponse:
    try:
        return save_document(session, kind=kind, payload=payload, actor=actor, document_id=document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/configs", response_model=list[ConfigDocumentResponse])
def list_generic_configs(
    kind: str | None = Query(default=None),
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
) -> list[ConfigDocumentResponse]:
    return list_documents(session, kind)


@router.post("/configs", response_model=ConfigDocumentResponse)
def create_generic_config(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
    actor: AuthUser = Depends(require_roles("editor", "approver", "operator", "admin")),
) -> ConfigDocumentResponse:
    kind = payload.get("kind")
    if not kind:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="kind is required")
    request = ConfigDocumentUpsertRequest(
        name=payload.get("name"),
        scope=payload.get("scope", "global"),
        tenant_id=payload.get("tenant_id") or payload.get("tenant"),
        definition_yaml=payload.get("yaml"),
        definition_json=payload.get("definition_json"),
    )
    return _save_document(kind=kind, payload=request, session=session, actor=actor)


@router.get("/configs/{document_id}", response_model=ConfigDocumentResponse)
def get_config(
    document_id: str,
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
) -> ConfigDocumentResponse:
    return serialize_document(get_document_or_404(session, document_id))


@router.put("/configs/{document_id}", response_model=ConfigDocumentResponse)
def update_config(
    document_id: str,
    payload: ConfigDocumentUpsertRequest,
    session: Session = Depends(get_session),
    actor: AuthUser = Depends(require_roles("editor", "approver", "operator", "admin")),
) -> ConfigDocumentResponse:
    document = get_document_or_404(session, document_id)
    return _save_document(kind=document.kind, payload=payload, session=session, actor=actor, document_id=document_id)


@router.get("/configs/{document_id}/export")
def export_yaml(
    document_id: str,
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
) -> Response:
    document = get_document_or_404(session, document_id)
    return Response(content=to_yaml(document.definition_jsonb), media_type="application/yaml")


@router.post("/import", response_model=ConfigDocumentResponse)
def import_yaml(
    payload: dict[str, Any],
    session: Session = Depends(get_session),
    actor: AuthUser = Depends(require_roles("editor", "approver", "operator", "admin")),
) -> ConfigDocumentResponse:
    request = ConfigDocumentUpsertRequest(
        scope=payload.get("scope", "global"),
        tenant_id=payload.get("tenant_id"),
        definition_yaml=payload["yaml"],
    )
    return _save_document(kind=payload["kind"], payload=request, session=session, actor=actor)


def _list_documents_by_kind(kind: str, session: Session) -> list[ConfigDocumentResponse]:
    return list_documents(session, kind)


@router.get("/api-ontology", response_model=list[ConfigDocumentResponse])
def list_api_ontology(
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
) -> list[ConfigDocumentResponse]:
    return _list_documents_by_kind("api_ontology", session)


@router.post("/api-ontology", response_model=ConfigDocumentResponse)
def create_api_ontology(
    payload: ConfigDocumentUpsertRequest,
    session: Session = Depends(get_session),
    actor: AuthUser = Depends(require_roles("editor", "approver", "operator", "admin")),
) -> ConfigDocumentResponse:
    return _save_document(kind="api_ontology", payload=payload, session=session, actor=actor)


@router.get("/memory-ontology", response_model=list[ConfigDocumentResponse])
def list_memory_ontology(
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
) -> list[ConfigDocumentResponse]:
    return _list_documents_by_kind("memory_ontology", session)


@router.post("/memory-ontology", response_model=ConfigDocumentResponse)
def create_memory_ontology(
    payload: ConfigDocumentUpsertRequest,
    session: Session = Depends(get_session),
    actor: AuthUser = Depends(require_roles("editor", "approver", "operator", "admin")),
) -> ConfigDocumentResponse:
    return _save_document(kind="memory_ontology", payload=payload, session=session, actor=actor)


@router.get("/policy-profiles", response_model=list[ConfigDocumentResponse])
def list_policy_profiles(
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
) -> list[ConfigDocumentResponse]:
    return _list_documents_by_kind("policy_profile", session)


@router.post("/policy-profiles", response_model=ConfigDocumentResponse)
def create_policy_profile(
    payload: ConfigDocumentUpsertRequest,
    session: Session = Depends(get_session),
    actor: AuthUser = Depends(require_roles("editor", "approver", "operator", "admin")),
) -> ConfigDocumentResponse:
    return _save_document(kind="policy_profile", payload=payload, session=session, actor=actor)


@router.post("/configs/{document_id}/approve", response_model=ApproveResponse)
@router.post("/api-ontology/{document_id}/approve", response_model=ApproveResponse)
@router.post("/memory-ontology/{document_id}/approve", response_model=ApproveResponse)
@router.post("/policy-profiles/{document_id}/approve", response_model=ApproveResponse)
def approve(
    document_id: str,
    session: Session = Depends(get_session),
    actor: AuthUser = Depends(require_roles("approver", "admin")),
) -> ApproveResponse:
    try:
        document = approve_document(session, document_id, actor)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ApproveResponse(id=document.id, status=document.status, approved_by=actor.email)


@router.get("/validation", response_model=list[ValidationIssue])
def list_validations(
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
) -> list[ValidationIssue]:
    return list_validation_results(session)


@router.post("/validation", response_model=ValidationResponse)
@router.post("/validate", response_model=ValidationResponse)
def validate(
    payload: ValidateRequest | dict[str, Any],
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(require_roles("editor", "approver", "operator", "admin")),
) -> ValidationResponse:
    request = payload if isinstance(payload, ValidateRequest) else ValidateRequest(**payload)
    try:
        return validate_documents(session, request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/simulation", response_model=list[dict[str, Any]])
def list_simulations(_user: AuthUser = Depends(get_current_user)) -> list[dict[str, Any]]:
    return []


@router.post("/simulation", response_model=SimulationResponse)
@router.post("/simulate", response_model=SimulationResponse)
def simulate_config(
    payload: SimulationRequest | dict[str, Any],
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(require_roles("editor", "approver", "operator", "admin")),
) -> SimulationResponse:
    request = payload if isinstance(payload, SimulationRequest) else SimulationRequest(**payload)
    try:
        return simulate(
            session,
            request,
            evaluator=lambda sample_event, bundle: evaluate_event(
                None, EventIngestRequest(**sample_event), bundle, None
            ).model_dump(mode="json"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/publications", response_model=list[PublicationResponse])
def publications(
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
) -> list[PublicationResponse]:
    return list_publications(session)


@router.post("/publish", response_model=PublicationResponse)
def publish(
    payload: PublishRequest | dict[str, Any],
    session: Session = Depends(get_session),
    actor: AuthUser = Depends(require_roles("approver", "admin")),
) -> PublicationResponse:
    request = payload if isinstance(payload, PublishRequest) else PublishRequest(**payload)
    try:
        return publish_documents(session, request, actor)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/rollback", response_model=PublicationResponse)
def rollback(
    payload: RollbackRequest | dict[str, Any],
    session: Session = Depends(get_session),
    actor: AuthUser = Depends(require_roles("operator", "admin")),
) -> PublicationResponse:
    request = payload if isinstance(payload, RollbackRequest) else RollbackRequest(**payload)
    try:
        return rollback_publication(session, request, actor)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/audit-log")
def audit_log(
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return list_audit_logs(session)
