# ADR 0002: Precedence binding, signal observations, and sensitive payload protection

Status: Accepted

## Context

The v1 spec requires operator-authored configuration to drive runtime behavior, including precedence-based conflict handling, repeat scoring, and sensitivity-aware persistence. The initial schema and runtime pass needed explicit hooks for binding API Ontology source precedence into Policy Profile precedence tables, for materializing repeat-signal observations, and for keeping sensitive structured payloads protected at rest.

## Decision

We will treat `source_precedence_key` as the explicit binding from each API Ontology entry into the Policy Profile `source_precedence` table. Runtime conflict handling will resolve precedence through that binding rather than relying on a freeform trust score.

We will also materialize per-signal observations as first-class runtime data so repeat scoring can be derived from observation windows instead of from a single mutable counter. The materialized observation rows will back the summarized counters used by policy evaluation.

Sensitive structured payloads at `S2+` will be stored in protected encrypted form, while only coarse summaries and canonical lookup keys remain in cleartext for retrieval and auditability.

## Alternatives Considered

- Keeping precedence implicit in `source_trust` values.
- Deriving repeat score only from aggregate counters without observation rows.
- Leaving `S2+` payloads unencrypted and relying on redaction only at query time.

These options were rejected because they make the runtime harder to validate, harder to audit, and weaker on sensitive-data protection.

## Consequences

- Conflict handling remains operator-configurable and auditable through the policy profile.
- Repeat scoring can be recomputed from durable observations instead of inferred from lossy aggregates.
- Sensitive payloads stay protected at rest without removing the metadata needed for retrieval, deduplication, and audit traceability.

## Links

- [Umbrella spec](../specs/spec_1.0.md)
- [Implementation memory](../memories/runtime-policy/2026-04-09-decision-context-precedence-binding-sensitive-storage-and-signal-observations.md)
