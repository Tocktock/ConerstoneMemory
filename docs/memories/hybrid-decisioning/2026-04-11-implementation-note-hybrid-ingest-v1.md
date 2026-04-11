# Hybrid ingest v1 implementation note

## Context

We implemented the first breaking runtime slice for hybrid rule-plus-LLM ingestion on `POST /v1/events/ingest`, including the normalized event envelope, config schema extensions, synchronous inference abstraction, runtime trace persistence, control-plane inspection updates, and synthetic end-to-end coverage.

## Decision or Observation

- The first-pass provider is a synchronous, deterministic stub that runs inside policy evaluation and is the default local and test provider.
- `runtime.inference_runs.source_event_id` is stored as a logical link to the runtime event id without a database foreign-key constraint. This avoids insert-order failures during the single-transaction ingest path while preserving auditable event linkage.
- The synthetic integration flow now verifies four branches in one scenario: explicit write bypass, model-assisted low-confidence persistence, hard safety block before model invocation, and deterministic forget.
- The test harness must run integration suites sequentially against the shared Postgres fixture. Parallel pytest processes can race while recreating schemas in the same database.

## Rationale

These choices preserve the product contract without forcing an external model dependency or asynchronous orchestration into the first shipping slice. The logical link for inference traces keeps auditability intact while avoiding fragile ORM ordering behavior in the synchronous transaction boundary. Recording the integration-test execution constraint avoids future false negatives caused by fixture races rather than product regressions.

## Impacted Specs, Decisions, or Code Areas

- [Umbrella spec](../../specs/spec_1.0.md)
- [ADR 0003](../../decisions/0003-normalized-event-envelopes-and-hybrid-rule-llm-policy.md)
- `src/memory_engine/runtime/`
- `src/memory_engine/control/`
- `tests/integration/test_synthetic_memory_flow.py`

## Follow-ups or Unresolved Questions

- Replace the stub provider with a real external inference service while keeping the same trace and policy-validation contract.
- Decide whether future decision explorer work should expose raw `inference_runs` as a dedicated operator page or keep the current embedded view.
- Tighten runtime enforcement around artifact-ref capture if operators need hard rejection instead of passive omission when config does not permit artifact persistence.
