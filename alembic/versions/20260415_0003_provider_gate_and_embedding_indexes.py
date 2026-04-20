from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector


revision = "20260415_0003"
down_revision = "20260411_0002"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, schema: str, table_name: str) -> bool:
    return inspector.has_table(table_name, schema=schema)


def _column_names(inspector: sa.Inspector, schema: str, table_name: str) -> set[str]:
    if not _has_table(inspector, schema, table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name, schema=schema)}


def _index_names(inspector: sa.Inspector, schema: str, table_name: str) -> set[str]:
    if not _has_table(inspector, schema, table_name):
        return set()
    return {index["name"] for index in inspector.get_indexes(table_name, schema=schema)}


def _legacy_embedding_model() -> tuple[str, str]:
    provider = os.getenv("MEMORYENGINE_EMBEDDING_PROVIDER", "hash")
    if provider == "ollama":
        return provider, os.getenv("MEMORYENGINE_OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b")
    if provider == "openai":
        return provider, os.getenv("MEMORYENGINE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    if provider == "disabled":
        return provider, "disabled"
    dimensions = os.getenv("MEMORYENGINE_EMBEDDING_DIMENSIONS", "8")
    return "hash", f"hash-{dimensions}"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "runtime", "memory_embeddings"):
        op.create_table(
            "memory_embeddings",
            sa.Column("memory_id", sa.String(length=64), nullable=False),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("model_name", sa.String(length=128), nullable=False),
            sa.Column("dimensions", sa.Integer(), nullable=False),
            sa.Column("embedding", Vector(), nullable=False),
            sa.Column("text_hash", sa.String(length=128), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["memory_id"], ["runtime.memories.memory_id"]),
            sa.PrimaryKeyConstraint("memory_id", "provider", "model_name"),
            schema="runtime",
        )

    embedding_indexes = _index_names(inspector, "runtime", "memory_embeddings")
    if "ix_runtime_memory_embeddings_provider_model" not in embedding_indexes:
        op.create_index(
            "ix_runtime_memory_embeddings_provider_model",
            "memory_embeddings",
            ["provider", "model_name"],
            unique=False,
            schema="runtime",
        )

    memory_columns = _column_names(inspector, "runtime", "memories")
    if "embedding" in memory_columns:
        provider, model_name = _legacy_embedding_model()
        bind.execute(
            sa.text(
                """
                INSERT INTO runtime.memory_embeddings (
                    memory_id,
                    provider,
                    model_name,
                    dimensions,
                    embedding,
                    text_hash,
                    created_at,
                    updated_at
                )
                SELECT
                    memory_id,
                    :provider,
                    :model_name,
                    8,
                    embedding,
                    md5(canonical_key),
                    created_at,
                    updated_at
                FROM runtime.memories
                WHERE embedding IS NOT NULL
                ON CONFLICT (memory_id, provider, model_name) DO NOTHING
                """
            ),
            {"provider": provider, "model_name": model_name},
        )
        op.drop_column("memories", "embedding", schema="runtime")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    memory_columns = _column_names(inspector, "runtime", "memories")

    if "embedding" not in memory_columns:
        op.add_column("memories", sa.Column("embedding", Vector(8), nullable=True), schema="runtime")
        op.execute(
            """
            UPDATE runtime.memories AS memories
            SET embedding = embeddings.embedding
            FROM runtime.memory_embeddings AS embeddings
            WHERE memories.memory_id = embeddings.memory_id
              AND embeddings.dimensions = 8
            """
        )

    if _has_table(inspector, "runtime", "memory_embeddings"):
        embedding_indexes = _index_names(inspector, "runtime", "memory_embeddings")
        if "ix_runtime_memory_embeddings_provider_model" in embedding_indexes:
            op.drop_index(
                "ix_runtime_memory_embeddings_provider_model",
                table_name="memory_embeddings",
                schema="runtime",
            )
        op.drop_table("memory_embeddings", schema="runtime")
