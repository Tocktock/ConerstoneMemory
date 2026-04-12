# Compose verification and test database isolation

## Context

The repository now has both a live Docker Compose stack for operator-console smoke checks and destructive integration tests that reset database state. During local verification, the pytest harness pointed at the same PostgreSQL database used by the Compose stack.

## Decision

Integration tests must use a dedicated test database that is distinct from the live Compose application database. The default local test target is `memoryengine_test`, and the harness now fails fast if `MEMORYENGINE_TEST_DATABASE_URL` resolves to the application database.

We also added a read-only Compose verification script so local health, auth, and list endpoints can be checked without mutating runtime data.

## Rationale

The integration harness intentionally uses `drop_all()` and `create_all()` to reset state between tests. Sharing that database with the live Compose stack is unsafe because verification can destroy the runtime schema and produce misleading feature failures.

Separating the databases preserves the intended verification split:

- Compose verifies live UI and API availability.
- Integration tests verify lifecycle and synthetic memory behavior in isolation.

## Impacted Areas

- [Pytest harness](/Users/jiyong/playground/MemoryEngine/tests/conftest.py)
- [Compose read-only verifier](/Users/jiyong/playground/MemoryEngine/scripts/verify_compose_readonly.py)
- [README](/Users/jiyong/playground/MemoryEngine/README.md)
- [Synthetic feature test governance note](./2026-04-09-conversation-synthetic-feature-tests.md)

## Follow-ups

- Consider adding a dedicated `docker-compose.test.yaml` or disposable test Postgres service if the local test database needs stronger isolation.
- Strengthen live health checks so missing application tables fail operator-facing readiness, not just generic DB connectivity.
