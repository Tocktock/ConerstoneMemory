# Repo bootstrap against the v1 umbrella spec

## Context

This repository began as a docs-first workspace with the v1 umbrella spec as the only product source of truth. The immediate task was to add the minimum durable documentation artifacts needed to support implementation work without inventing application behavior ahead of the spec.

## Observation

The repo needed three governance layers before application code:

- a decision record for the repo shape and infrastructure boundary
- a memory note for the implementation rationale and future traceability
- a minimal root README that points to the canonical spec instead of duplicating product rules

## Decision

We are treating `docs/specs/spec_1.0.md` as the contract and keeping all durable repository guidance in `docs/decisions/` and `docs/memories/`. The first ADR fixes the monorepo shape and PostgreSQL-backed job ledger choice so later implementation work does not drift into ad hoc infrastructure decisions.

## Rationale

This keeps the repository auditable and prevents the implementation from outrunning the spec. It also creates a clear place to record future technical decisions, rollout notes, and root-cause findings as the codebase grows.

## Impacted Areas

- [Umbrella spec](../../specs/spec_1.0.md)
- [ADR 0001](../../decisions/0001-repo-shape-and-postgres-job-ledger.md)
- future application scaffolding under `apps/`

## Follow-ups

- Add additional ADRs only when a durable rule or boundary is actually chosen.
- Keep future memory notes focused on non-obvious implementation intent, tradeoffs, or investigations.
