# MemoryEngine

Docs-first repository for the Human-Configurable API-Driven Memory Platform v1.

Primary source of truth:

- [Umbrella spec](docs/specs/spec_1.0.md)

Governance and traceability:

- [Architecture decisions](docs/decisions/0001-repo-shape-and-postgres-job-ledger.md)
- [Implementation memories](docs/memories/repo-bootstrap/2026-04-09-implementation-note.md)

Application code is intentionally not described here. Use the spec and the docs under `docs/` as the contract.

Local run:

- `./run.sh` starts the full Docker Compose stack and prints the local URLs.
- `./run.sh logs api` tails one service.
- `./run.sh down` stops the stack.

Verification:

- `.venv/bin/python scripts/verify_compose_readonly.py` checks the live Compose web and API surfaces without mutating runtime data.
- Integration tests use `MEMORYENGINE_TEST_DATABASE_URL` and default to `postgresql+psycopg://memoryengine:memoryengine@localhost:5433/memoryengine_test`.
- Keep the test database separate from the Compose application database; the test harness intentionally drops and recreates schemas.
