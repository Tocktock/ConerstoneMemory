from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from memory_engine.config.settings import get_settings


EXPECTED_TABLES = [
    ("control", "audit_log"),
    ("control", "config_documents"),
    ("control", "config_publications"),
    ("control", "validation_results"),
    ("runtime", "api_events"),
    ("runtime", "entities"),
    ("runtime", "entity_aliases"),
    ("runtime", "evidence"),
    ("runtime", "memories"),
    ("runtime", "relations"),
    ("runtime", "signal_counters"),
    ("ops", "jobs"),
    ("ops", "metrics_rollups"),
]


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
    with engine.begin() as connection:
        inspector = inspect(connection)
        present = [
            (schema, table)
            for schema, table in EXPECTED_TABLES
            if inspector.has_table(table, schema=schema)
        ]
        if len(present) == len(EXPECTED_TABLES):
            print("bootstrap_db: application schema already present")
            return
        if present:
            missing = [f"{schema}.{table}" for schema, table in EXPECTED_TABLES if (schema, table) not in present]
            raise SystemExit(
                "bootstrap_db: partial application schema detected; refusing automatic repair. "
                f"Missing tables: {', '.join(missing)}"
            )
        if inspector.has_table("alembic_version"):
            connection.execute(text("DROP TABLE alembic_version"))
            print("bootstrap_db: removed stale alembic version marker from an empty schema")
            return
        print("bootstrap_db: database is empty; continuing to Alembic migrations")


if __name__ == "__main__":
    main()
