from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from memory_engine.config.settings import Settings, get_settings
from memory_engine.control.service import get_document_or_404, resolve_snapshot


def resolve_active_bundle(session: Session, settings: Settings, tenant_id: str | None):
    snapshot = resolve_snapshot(session, environment=settings.environment, tenant_id=tenant_id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active configuration snapshot is published for this scope",
        )
    bundle = {
        "api_ontology": get_document_or_404(session, snapshot.api_ontology_document_id),
        "memory_ontology": get_document_or_404(session, snapshot.memory_ontology_document_id),
        "policy_profile": get_document_or_404(session, snapshot.policy_profile_document_id),
    }
    return bundle, snapshot
