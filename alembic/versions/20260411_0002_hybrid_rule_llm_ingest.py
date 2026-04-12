from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260411_0002"
down_revision = "20260409_0001"
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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    api_event_columns = _column_names(inspector, "runtime", "api_events")

    api_event_additions: list[tuple[str, sa.Column]] = [
        ("source_system", sa.Column("source_system", sa.String(length=255), nullable=True)),
        ("http_method", sa.Column("http_method", sa.String(length=16), nullable=True)),
        ("route_template", sa.Column("route_template", sa.String(length=255), nullable=True)),
        ("request_id", sa.Column("request_id", sa.String(length=255), nullable=True)),
        ("trace_id", sa.Column("trace_id", sa.String(length=255), nullable=True)),
        ("source_channel", sa.Column("source_channel", sa.String(length=255), nullable=True)),
        ("response_status", sa.Column("response_status", sa.Integer(), nullable=True)),
        (
            "request_fields_jsonb",
            sa.Column("request_fields_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        ),
        (
            "response_fields_jsonb",
            sa.Column("response_fields_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        ),
        (
            "request_artifact_jsonb",
            sa.Column("request_artifact_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        ),
        (
            "response_artifact_jsonb",
            sa.Column("response_artifact_jsonb", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        ),
        ("redaction_policy_version", sa.Column("redaction_policy_version", sa.String(length=64), nullable=True)),
    ]

    for column_name, column in api_event_additions:
        if column_name not in api_event_columns:
            op.add_column("api_events", column, schema="runtime")
            api_event_columns.add(column_name)

    if _has_table(inspector, "runtime", "api_events"):
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

        for column_name in ("source_system", "http_method", "route_template", "request_fields_jsonb", "response_fields_jsonb"):
            if column_name in api_event_columns:
                op.alter_column("api_events", column_name, nullable=False, schema="runtime")

    api_event_indexes = _index_names(inspector, "runtime", "api_events")
    for index_name, columns in (
        ("ix_runtime_api_events_source_system", ["source_system"]),
        ("ix_runtime_api_events_http_method", ["http_method"]),
        ("ix_runtime_api_events_route_template", ["route_template"]),
        ("ix_runtime_api_events_request_id", ["request_id"]),
        ("ix_runtime_api_events_trace_id", ["trace_id"]),
        ("ix_runtime_api_events_source_channel", ["source_channel"]),
    ):
        if index_name not in api_event_indexes:
            op.create_index(index_name, "api_events", columns, unique=False, schema="runtime")

    inference_runs_exists = _has_table(inspector, "runtime", "inference_runs")
    if not inference_runs_exists:
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

    inference_indexes = _index_names(inspector, "runtime", "inference_runs")
    for index_name, columns in (
        ("ix_runtime_inference_runs_source_event_id", ["source_event_id"]),
        ("ix_runtime_inference_runs_config_snapshot_id", ["config_snapshot_id"]),
    ):
        if index_name not in inference_indexes:
            op.create_index(index_name, "inference_runs", columns, unique=False, schema="runtime")


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
