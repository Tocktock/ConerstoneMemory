from __future__ import annotations

import time

from memory_engine.config.settings import get_settings
from memory_engine.control.service import get_document_or_404, resolve_snapshot
from memory_engine.db.session import SessionLocal
from memory_engine.runtime.service import process_next_job


def _bundle_resolver(session, tenant_id: str | None):
    settings = get_settings()
    snapshot = resolve_snapshot(session, environment=settings.environment, tenant_id=tenant_id)
    if snapshot is None:
        raise RuntimeError("No active configuration snapshot available")
    bundle = {
        "api_ontology": get_document_or_404(session, snapshot.api_ontology_document_id),
        "memory_ontology": get_document_or_404(session, snapshot.memory_ontology_document_id),
        "policy_profile": get_document_or_404(session, snapshot.policy_profile_document_id),
    }
    return bundle, snapshot


def main() -> None:
    settings = get_settings()
    while True:
        with SessionLocal() as session:
            process_next_job(session, _bundle_resolver)
        time.sleep(settings.worker_poll_seconds)
