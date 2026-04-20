# Relationship-aware API ontology and durable workflow intent memory

## Context

The repository previously modeled API Ontology as a flat event registry. During product discussion, the intended outcome was clarified: operators want to predefine relationships between APIs so the system can understand what broader task the user is trying to complete.

The motivating examples were related API families such as order registration, order retrieval, payment charge, and refund.

## Decision / Observation

The API Ontology needs to support two concerns that were previously conflated:

- per-event API semantics
- cross-API workflow relationships and intent inference

We decided to keep one `api-ontology` document per snapshot, but redesign the inside of that document as an API Ontology Package with:

- `modules[]`
- `workflows[]`

The runtime should persist:

- observed API event trace
- normal event-derived memory
- related API references as workflow context
- a separate durable active workflow intent memory in natural language

It must not persist unobserved related APIs as if they were executed facts.

## Rationale

This keeps the existing snapshot lifecycle stable while making the authoring model maintainable and expressive enough for grouped API relationships.

It also aligns the product more closely with the desired user-facing outcome: not only storing what happened, but storing what the user was trying to do.

## Impacted Specs / Decisions / Code Areas

- [Spec 1.0](../../specs/spec_1.0.md)
- [ADR 0005](../../decisions/0005-api-ontology-package-workflows-and-active-intent-memory.md)
- `src/memory_engine/control/schemas.py`
- `src/memory_engine/control/service.py`
- `src/memory_engine/runtime/policy.py`
- `src/memory_engine/runtime/service.py`
- `apps/web/src/components/workspace-sections.tsx`

## Follow-ups

- Add grouped master-detail API Ontology authoring in the control plane.
- Add workflow-aware synthetic and AI-assisted evaluation coverage.
