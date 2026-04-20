# Provider-gated inference and deterministic embeddings conversation

## Context

We expanded the Memory Engine runtime contract beyond the first hybrid stub provider.

The new goal is to keep the external Memory Engine API provider-agnostic while letting the runtime choose internal inference providers through published policy and use a deterministic embedding profile selected at process startup.

## Decision or Observation

- Internal inference provider routing belongs inside `PolicyProfile.model_inference.provider_gate`.
- External callers such as Codex, Claude, Ollama, or other agents do not choose the internal provider through Memory Engine request payloads.
- Embedding provider choice is not policy-routed per request. It is deterministic at startup from environment settings.
- A single vector column on `runtime.memories` is not sufficient once test and production environments can use different embedding models. Embeddings need a separate provider/model keyed index table.
- The main local and test evaluation gate should use live Ollama rather than only mocked inference.
- The required local and test Ollama inference model is `gemma4:e4b`; the required local and test embedding model is `qwen3-embedding:0.6b`.

## Rationale

This keeps Memory Engine aligned with its role as a provider-agnostic memory service while still allowing runtime provider choice for model-assisted decisioning. Separating embeddings from policy routing prevents request-level nondeterminism and preserves provenance when environments use different models.

## Impacted Specs, Decisions, or Code Areas

- [Umbrella spec](../../specs/spec_1.0.md)
- [ADR 0004](../../decisions/0004-provider-gated-inference-and-per-model-embedding-indexes.md)
- `src/memory_engine/runtime/`
- `src/memory_engine/worker/`
- `src/memory_engine/db/`
- `tests/`

## Follow-ups or Unresolved Questions

- Keep concrete internal inference adapters limited to Ollama and OpenAI in the first cut.
- Revisit broader provider coverage after the policy gate and embedding table are stable.
