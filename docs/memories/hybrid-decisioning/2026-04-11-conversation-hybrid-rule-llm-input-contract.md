# Hybrid rule-LLM input contract refinement

## Context

We revisited the intended product flow for MemoryEngine v1 with a focus on future LLM-assisted runtime behavior. The original simplified description was:

1. information arrives from API request/response activity
2. a model decides whether the system should remember it
3. related information is found through API Ontology and Memory Ontology
4. memory is created and stored

The key clarification was that the project should evolve toward LLM assistance later, but keep a strong policy and audit backbone now.

## Decision or Observation

The refined direction is:

- treat ingestion as a normalized event envelope derived from selected request/response facts, not just `api_name`
- use both deterministic rules and an LLM, with rules acting before and after model invocation
- keep hard safety, explicit writes, and explicit forget/delete behavior as rule-governed paths that can bypass the model
- let the model assist with memory-worthiness and candidate extraction, but require final policy validation before persistence
- treat raw request/response bodies as optional redacted evidence artifacts rather than default model inputs

## Rationale

This keeps the system aligned with the product goal of controlled memory creation. It adds semantic flexibility without turning persistence into an opaque model-only behavior. It also reduces the chance that sensitive request/response payloads leak into prompts or durable storage without clear policy approval.

## Impacted Specs, Decisions, or Code Areas

- [Umbrella spec](../../specs/spec_1.0.md)
- [ADR 0003](../../decisions/0003-normalized-event-envelopes-and-hybrid-rule-llm-policy.md)
- future runtime event schema, policy evaluation, and worker inference tracing

## Follow-ups or Unresolved Questions

- Decide the exact normalized event envelope schema and whether request/response artifact refs should be first-class API fields.
- Decide whether the model should output only memory-worthiness or both memory-worthiness and candidate extraction.
- Define how prompt templates are versioned and how blocked field paths are enforced in prompt assembly.
- Add synthetic coverage once implementation work begins for model-bypass paths, model-assisted paths, and rule-versus-model disagreement handling.
