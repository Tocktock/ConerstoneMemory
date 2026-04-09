# ADR 0001: Monorepo scaffold with PostgreSQL-backed job ledger

Status: Accepted

## Context

The repository currently starts as a docs-first workspace with the umbrella v1 specification in [docs/specs/spec_1.0.md](../specs/spec_1.0.md). The spec requires a single Docker Compose stack with PostgreSQL, an API service, a worker service, and a web operator console. It also makes PostgreSQL the source of truth for configuration, memory state, audit history, and vector storage.

The first implementation pass needs a durable repo shape that can support the control plane, runtime ingestion, retrieval, and operator UI without introducing unnecessary infrastructure complexity.

## Decision

We will organize the codebase as a single monorepo with three application surfaces:

- `apps/api` for the FastAPI control-plane and runtime HTTP API
- `apps/worker` for asynchronous processing, embedding, replay, and cleanup jobs
- `apps/web` for the Next.js operator console

We will use PostgreSQL as the only durable state store in v1 and use a PostgreSQL-backed job table as the worker queue and execution ledger. We will not introduce Redis, Kafka, or a second database-backed queue in v1.

We will keep the OpenAPI schema as the backend contract source and generate the web client from it rather than hand-maintaining a separate request/response model layer.

## Alternatives Considered

- A split-repository setup with separate API, worker, and web codebases.
- An external queue such as Redis or Kafka for background processing.
- A manually maintained frontend API layer instead of generated client code.

These options were rejected for v1 because they add operational surface area before the core product behavior is stable.

## Consequences

- The initial implementation can stay aligned to the spec with a small number of moving parts.
- Background processing will be simple to operate and trace because queue state and execution history remain in PostgreSQL.
- The worker can evolve without changing the durable storage model or adding new infrastructure.
- Future scaling changes can introduce a separate queue later if the spec or load profile justifies it.

## Links

- [Umbrella spec](../specs/spec_1.0.md)
- [Initial implementation memory](../memories/repo-bootstrap/2026-04-09-implementation-note.md)
