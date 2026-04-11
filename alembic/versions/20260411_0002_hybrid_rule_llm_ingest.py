from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260411_0002"
down_revision = "20260409_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_events", sa.Column("source_system", sa.String(length=255), nullable=True), schema="runtime")
    op.add_column("api_events", sa.Column("http_method", sa.String(length=16), nullable=True), schema="runtime")
    op.add_column("api_events", sa.Column("route_template", sa.String(length=255), nullable=True), schema="runtime")
    op.add_column("api_events", sa.Column("request_id", sa.String(length=255), nullable=True), schema="runtime")
    op.add_column("api_events", sa.Column("trace_id", sa.String(length=255), nullable=True), schema="runtime")
    op.add_column("api_events", sa.Column("source_channel", sa.String(length=255), nullable=True), schema="runtime")
    op.add_column("api_events", sa.Column("response_status", sa.Integer(), nullable=True), schema="runtime")
    op.add_column(
        "api_events",
        sa.Column("request_fields_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="runtime",
    )
    op.add_column(
        "api_events",
        sa.Column("response_fields_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="runtime",
    )
    op.add_column(
        "api_events",
        sa.Column("request_artifact_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="runtime",
    )
    op.add_column(
        "api_events",
        sa.Column("response_artifact_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        schema="runtime",
    )
    op.add_column("api_events", sa.Column("redaction_policy_version", sa.String(length=64), nullable=True), schema="runtime")

    op.execute(
        """
        UPDATE runtime.api_events
        SET
          source_system = COALESCE(source_system, 'legacy_source'),
          http_method = COALESCE(http_method, 'LEGACY'),
          route_template = COALESCE(route_template, 'legacy_route'),
          request_fields_jsonb = COALESCE(request_fields_jsonb, structured_fields_jsonb, '{}'::jsonb),
          response_fields_jsonb = COALESCE(response_fields_jsonb, '{}'::jsonb)
        """
    )

    op.alter_column("api_events", "source_system", nullable=False, schema="runtime")
    op.alter_column("api_events", "http_method", nullable=False, schema="runtime")
    op.alter_column("api_events", "route_template", nullable=False, schema="runtime")
    op.alter_column("api_events", "request_fields_jsonb", nullable=False, schema="runtime")
    op.alter_column("api_events", "response_fields_jsonb", nullable=False, schema="runtime")

    op.create_index("ix_runtime_api_events_source_system", "api_events", ["source_system"], unique=False, schema="runtime")
    op.create_index("ix_runtime_api_events_http_method", "api_events", ["http_method"], unique=False, schema="runtime")
    op.create_index("ix_runtime_api_events_route_template", "api_events", ["route_template"], unique=False, schema="runtime")
    op.create_index("ix_runtime_api_events_request_id", "api_events", ["request_id"], unique=False, schema="runtime")
    op.create_index("ix_runtime_api_events_trace_id", "api_events", ["trace_id"], unique=False, schema="runtime")
    op.create_index("ix_runtime_api_events_source_channel", "api_events", ["source_channel"], unique=False, schema="runtime")

    op.create_table(
        "inference_runs",
        sa.Column("inference_id", sa.String(length=64), nullable=False),
        sa.Column("source_event_id", sa.String(length=64), nullable=False),
        sa.Column("config_snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("model_provider", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("prompt_template_key", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("input_hash", sa.String(length=128), nullable=False),
        sa.Column("llm_recommendation", sa.String(length=32), nullable=False),
        sa.Column("llm_confidence", sa.Float(), nullable=False),
        sa.Column("llm_reasoning_summary", sa.Text(), nullable=True),
        sa.Column("candidate_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("final_action", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("inference_id"),
        schema="runtime",
    )
    op.create_index(
        "ix_runtime_inference_runs_source_event_id",
        "inference_runs",
        ["source_event_id"],
        unique=False,
        schema="runtime",
    )
    op.create_index(
        "ix_runtime_inference_runs_config_snapshot_id",
        "inference_runs",
        ["config_snapshot_id"],
        unique=False,
        schema="runtime",
    )


def downgrade() -> None:
    op.drop_index("ix_runtime_inference_runs_config_snapshot_id", table_name="inference_runs", schema="runtime")
    op.drop_index("ix_runtime_inference_runs_source_event_id", table_name="inference_runs", schema="runtime")
    op.drop_table("inference_runs", schema="runtime")

    op.drop_index("ix_runtime_api_events_source_channel", table_name="api_events", schema="runtime")
    op.drop_index("ix_runtime_api_events_trace_id", table_name="api_events", schema="runtime")
    op.drop_index("ix_runtime_api_events_request_id", table_name="api_events", schema="runtime")
    op.drop_index("ix_runtime_api_events_route_template", table_name="api_events", schema="runtime")
    op.drop_index("ix_runtime_api_events_http_method", table_name="api_events", schema="runtime")
    op.drop_index("ix_runtime_api_events_source_system", table_name="api_events", schema="runtime")

    op.drop_column("api_events", "redaction_policy_version", schema="runtime")
    op.drop_column("api_events", "response_artifact_jsonb", schema="runtime")
    op.drop_column("api_events", "request_artifact_jsonb", schema="runtime")
    op.drop_column("api_events", "response_fields_jsonb", schema="runtime")
    op.drop_column("api_events", "request_fields_jsonb", schema="runtime")
    op.drop_column("api_events", "response_status", schema="runtime")
    op.drop_column("api_events", "source_channel", schema="runtime")
    op.drop_column("api_events", "trace_id", schema="runtime")
    op.drop_column("api_events", "request_id", schema="runtime")
    op.drop_column("api_events", "route_template", schema="runtime")
    op.drop_column("api_events", "http_method", schema="runtime")
    op.drop_column("api_events", "source_system", schema="runtime")
