from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from memory_engine.api.deps import resolve_active_bundle
from memory_engine.auth.security import AuthUser, get_current_user, require_roles
from memory_engine.config.settings import get_settings
from memory_engine.db.session import get_session
from memory_engine.runtime.schemas import EventIngestRequest, ForgetRequest, MemoryQueryRequest
from memory_engine.runtime.service import (
    decision_records,
    forget_memories,
    ingest_event,
    list_user_memories,
    query_memories,
    timeline,
)

router = APIRouter(tags=["runtime"])


@router.post("/v1/events/ingest")
def ingest(
    payload: EventIngestRequest,
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(require_roles("editor", "approver", "operator", "admin")),
):
    bundle, snapshot = resolve_active_bundle(session=session, settings=get_settings(), tenant_id=payload.tenant_id)
    event, decision, job = ingest_event(session, event_request=payload, bundle=bundle, snapshot=snapshot)
    return {
        "event_id": event.event_id,
        "job_id": job.job_id,
        "decision": decision.model_dump(mode="json"),
    }


@router.get("/v1/memory/query")
def query_memories_get(
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    memory_type: str | None = Query(default=None),
    query_text: str | None = Query(default=None),
    top_k: int = Query(default=10),
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
):
    return query_memories(
        session,
        MemoryQueryRequest(
            tenant_id=tenant_id,
            user_id=user_id,
            memory_type=memory_type,
            query_text=query_text,
            top_k=top_k,
        ),
    )


@router.post("/v1/memory/query")
def query_memories_post(
    payload: MemoryQueryRequest,
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
):
    return query_memories(session, payload)


@router.post("/v1/memory/forget")
def forget(
    payload: ForgetRequest,
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(require_roles("operator", "admin")),
):
    _bundle, snapshot = resolve_active_bundle(session=session, settings=get_settings(), tenant_id=payload.tenant_id)
    return forget_memories(session, payload, config_snapshot_id=snapshot.id)


@router.get("/v1/memory/users/{user_id}")
def user_memories(
    user_id: str,
    tenant_id: str = Query(...),
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
):
    return list_user_memories(session, tenant_id, user_id)


@router.get("/v1/memory/users/{user_id}/timeline")
def user_timeline(
    user_id: str,
    tenant_id: str = Query(...),
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
):
    return timeline(session, tenant_id, user_id)


@router.get("/v1/memory/decisions")
def decisions(
    tenant: str | None = Query(default=None),
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
):
    return decision_records(session, tenant_id=tenant)


@router.get("/v1/audit/logs")
def audit_alias(
    session: Session = Depends(get_session),
    _user: AuthUser = Depends(get_current_user),
):
    from memory_engine.control.service import list_audit_logs

    return list_audit_logs(session)
