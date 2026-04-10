# Precedence binding and sensitive payload protection in the v1 pass

## Context

The spec-conformance pass required a minimal documentation update to close the remaining implementation hooks without expanding the product surface beyond what v1 already promised.

## Observation

The important gaps were not new product concepts. They were missing normative bindings and shape details:

- API Ontology entries needed an explicit `source_precedence_key` link into Policy Profile precedence tables.
- Config publication metadata needed to preserve the scope, tenant, and release notes for a real snapshot history.
- `S2+` payload handling needed to say plainly that the full structured value is protected at rest, not just vaguely "stronger protected".
- Repeat-score work needed a durable observation model so the runtime can recompute windows and burst effects without depending on a single mutable total.

## Decision

We are keeping the spec change small and normative. The spec now names the missing bindings and storage requirements, while the ADR records the rationale for the implementation-specific choices around precedence binding, materialized observations, and protected payload storage.

## Rationale

This avoids broadening the spec unnecessarily while still giving implementation a stable contract. It also keeps auditability intact: operators can inspect precedence, publication history, and memory behavior without exposing raw sensitive strings in cleartext.

## Impacted Areas

- [Umbrella spec](../../specs/spec_1.0.md)
- [ADR 0002](../../decisions/0002-runtime-precedence-binding-signal-observations-and-sensitive-payload-protection.md)
- future control-plane, runtime, and worker implementation work

## Follow-ups

- Keep future docs changes narrowly tied to missing hooks, not implementation details already covered by code.
- Preserve the distinction between cleartext metadata and encrypted structured payloads in later spec updates.
