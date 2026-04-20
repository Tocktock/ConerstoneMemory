# ADR 0004: Provider-gated inference and per-model embedding indexes

Status: Accepted

## Context

The hybrid ingest slice currently uses a single synchronous stub inference provider and stores one fixed-dimension embedding vector directly on `runtime.memories`.

That shape is too narrow for the next runtime contract:

- internal inference provider choice must be policy-gated so Memory Engine can prefer Ollama or OpenAI without changing external APIs
- embeddings must be deterministic at startup, not selected per request
- different embedding models use different vector widths, so a single `runtime.memories.embedding` column cannot preserve provider/model provenance

## Decision

We will add an internal inference provider gate inside `PolicyProfile.model_inference`.

Published policy may choose among registered provider ids using ordered rules and a default provider. The provider registry itself remains environment configuration.

We will store embeddings in a dedicated `runtime.memory_embeddings` table keyed by `(memory_id, provider, model_name)` with provider/model provenance and native vector dimensions.

Runtime ingestion, embedding backfill, and vector retrieval will use the startup-selected embedding profile from settings. The inference provider gate will not control embeddings.

## Alternatives Considered

- Keep provider choice in environment settings only.
- Allow API Ontology or Memory Ontology to bind providers directly.
- Keep a single shared embedding dimension and project all providers into it.

These options were rejected because they either remove runtime policy control, push provider concerns into ontology documents, or lose fidelity across embedding models.

## Consequences

- `Policy Profile` validation must reject provider ids that are unknown to the environment registry or explicitly disabled.
- Runtime auditability improves because `InferenceRun` records now reflect the selected provider path.
- Retrieval and backfill logic must move from `runtime.memories.embedding` to the embedding index table.
- Environment setup must explicitly verify Ollama reachability and required models for the main synthetic gate.

## Links

- [Umbrella spec](../specs/spec_1.0.md)
- [ADR 0003](./0003-normalized-event-envelopes-and-hybrid-rule-llm-policy.md)
