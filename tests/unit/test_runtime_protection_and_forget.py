from __future__ import annotations

from sqlalchemy import select

from memory_engine.db.models import Entity, Relation
from memory_engine.id_utils import new_id
from memory_engine.runtime.protection import protect_payload, restore_payload
from memory_engine.runtime.schemas import ForgetRequest
from memory_engine.runtime.service import forget_memories


def test_protect_payload_encrypts_sensitive_fields() -> None:
    clear_payload, encrypted_payload = protect_payload(
        {"address": "123 Seongsu-ro, Seongdong-gu, Seoul", "summary": "123 Seongsu-ro"},
        "S2_PERSONAL",
    )

    assert encrypted_payload is not None
    assert clear_payload == {"summary": "123 Seongsu-ro"}
    assert restore_payload(clear_payload, encrypted_payload)["address"] == "123 Seongsu-ro, Seongdong-gu, Seoul"


def test_forget_memories_only_deletes_relations_for_target_user(db_session) -> None:
    tenant_id = "tenant_test"
    user_one = Entity(
        entity_id=new_id("ent"),
        tenant_id=tenant_id,
        entity_type="User",
        canonical_key="user_one",
        attributes_jsonb={"user_id": "user_one"},
    )
    user_two = Entity(
        entity_id=new_id("ent"),
        tenant_id=tenant_id,
        entity_type="User",
        canonical_key="user_two",
        attributes_jsonb={"user_id": "user_two"},
    )
    customer = Entity(
        entity_id=new_id("ent"),
        tenant_id=tenant_id,
        entity_type="Customer",
        canonical_key="customer_abc",
        attributes_jsonb={"canonical_customer_id": "customer_abc"},
    )
    db_session.add_all([user_one, user_two, customer])
    db_session.flush()

    relation_one = Relation(
        relation_id=new_id("rel"),
        tenant_id=tenant_id,
        subject_entity_id=user_one.entity_id,
        relation_type="relationship.customer",
        object_entity_id=customer.entity_id,
        state="active",
        strength=0.9,
        evidence_count=1,
        config_snapshot_id="cfgsnap_test",
    )
    relation_two = Relation(
        relation_id=new_id("rel"),
        tenant_id=tenant_id,
        subject_entity_id=user_two.entity_id,
        relation_type="relationship.customer",
        object_entity_id=customer.entity_id,
        state="active",
        strength=0.9,
        evidence_count=1,
        config_snapshot_id="cfgsnap_test",
    )
    db_session.add_all([relation_one, relation_two])
    db_session.commit()

    result = forget_memories(
        db_session,
        ForgetRequest(
            tenant_id=tenant_id,
            user_id="user_one",
            relation_type="relationship.customer",
            canonical_key="customer_abc",
        ),
        config_snapshot_id="cfgsnap_test",
    )

    deleted_relation = db_session.scalar(select(Relation).where(Relation.relation_id == relation_one.relation_id))
    untouched_relation = db_session.scalar(select(Relation).where(Relation.relation_id == relation_two.relation_id))

    assert result["relations"] == 1
    assert deleted_relation is not None and deleted_relation.state == "deleted"
    assert untouched_relation is not None and untouched_relation.state == "active"


def test_old_ingest_payload_shape_is_rejected(client) -> None:
    login = client.post("/v1/auth/login", json={"email": "editor@memoryengine.local", "password": "editor"})
    token = login.json()["token"]
    response = client.post(
        "/v1/events/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "tenant_id": "tenant_test",
            "user_id": "user_test",
            "api_name": "profile.updateAddress",
            "structured_fields": {"address": "123 Seongsu-ro"},
            "request_summary": "legacy request",
            "response_summary": "legacy response",
        },
    )
    assert response.status_code == 422
