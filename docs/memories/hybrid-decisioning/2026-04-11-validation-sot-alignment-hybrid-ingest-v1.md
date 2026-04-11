# Hybrid ingest v1 SoT alignment

## Context

The first implementation pass for hybrid rule-plus-LLM ingestion shipped a breaking nested envelope on `POST /v1/events/ingest`. The architecture sections of the umbrella spec and ADR were already aligned, but several normative examples in the umbrella spec still showed the older flat payload and pre-update policy/config examples.

## Decision or Observation

- The umbrella spec must treat the nested request/response envelope as the normative ingest contract for v1 going forward.
- The old flat top-level payload shape using `structured_fields`, `request_summary`, and `response_summary` should remain visible only as a rejected legacy contract, not as a worked example.
- API Ontology examples should show selectors against `request.selected_fields` and `response.selected_fields`, while prompt field-path examples should target the normalized prompt envelope such as `$.normalized_fields.query`.
- The Policy Profile example should use the shipped model-governance fields `low_confidence_threshold` and `allow_low_confidence_persist` instead of the older `uncertainty_action` example.

## Rationale

Leaving the umbrella spec partially stale would create avoidable client and operator confusion around the only public breaking runtime endpoint in this slice. Aligning the examples with the implemented contract preserves the docs-first workflow and keeps the spec usable as an executable review aid rather than only a directional design document.

## Impacted Specs, Decisions, or Code Areas

- [Umbrella spec](../../specs/spec_1.0.md)
- [ADR 0003](../../decisions/0003-normalized-event-envelopes-and-hybrid-rule-llm-policy.md)
- `src/memory_engine/runtime/schemas.py`
- `src/memory_engine/control/schemas.py`
- `tests/unit/test_runtime_protection_and_forget.py`

## Follow-ups or Unresolved Questions

- Decide whether the umbrella spec should explicitly call out that `runtime.inference_runs.source_event_id` is an auditable logical link without a database foreign-key constraint, or leave that detail in implementation notes only.
- Decide whether the spec should hard-require runtime rejection of artifact references when the matched evidence-capture policy does not permit persistence, rather than the current passive omission behavior.
