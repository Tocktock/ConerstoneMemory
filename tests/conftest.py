from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from memory_engine.api.app import create_app
from memory_engine.db.base import Base
from memory_engine.db.session import get_session


APP_DATABASE_URL = os.getenv(
    "MEMORYENGINE_DATABASE_URL",
    "postgresql+psycopg://memoryengine:memoryengine@localhost:5433/memoryengine",
)
TEST_DATABASE_URL = os.getenv(
    "MEMORYENGINE_TEST_DATABASE_URL",
    "postgresql+psycopg://memoryengine:memoryengine@localhost:5433/memoryengine_test",
)


def _quoted_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _assert_isolated_test_database() -> None:
    app_url = make_url(APP_DATABASE_URL)
    test_url = make_url(TEST_DATABASE_URL)
    if not test_url.database:
        raise RuntimeError("MEMORYENGINE_TEST_DATABASE_URL must include a database name")
    if (
        test_url.host,
        test_url.port,
        test_url.username,
        test_url.database,
    ) == (
        app_url.host,
        app_url.port,
        app_url.username,
        app_url.database,
    ):
        raise RuntimeError(
            "MEMORYENGINE_TEST_DATABASE_URL points to the application database. "
            "Use a dedicated test database such as memoryengine_test."
        )


def _ensure_test_database() -> None:
    _assert_isolated_test_database()
    test_url = make_url(TEST_DATABASE_URL)
    admin_url = test_url.set(database="postgres")
    admin_engine = create_engine(
        admin_url,
        future=True,
        pool_pre_ping=True,
        isolation_level="AUTOCOMMIT",
    )
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :database_name"),
                {"database_name": test_url.database},
            ).scalar()
            if not exists:
                connection.execute(text(f"CREATE DATABASE {_quoted_identifier(test_url.database)}"))
    finally:
        admin_engine.dispose()


def _reset_test_schemas(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        for schema in ("control", "runtime", "ops"):
            connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            connection.execute(text(f"CREATE SCHEMA {schema}"))
    Base.metadata.create_all(engine)


@pytest.fixture(scope="session")
def engine():
    _ensure_test_database()
    engine = create_engine(TEST_DATABASE_URL, future=True, pool_pre_ping=True)
    _reset_test_schemas(engine)
    yield engine
    _reset_test_schemas(engine)
    engine.dispose()


@pytest.fixture()
def db_session(engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    _reset_test_schemas(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
