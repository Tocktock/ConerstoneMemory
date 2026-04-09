# MemoryEngine Repository Rules

These rules apply to `/Users/jiyong/playground/MemoryEngine` and refine the global AGENTS contract for this repository.

## Repository mission

- This repository implements the **Human-Configurable API-Driven Memory Platform v1**.
- Until a newer approved spec supersedes it, `/docs/specs/spec_1.0.md` is the primary product source of truth for v1 behavior, architecture, acceptance criteria, and safety invariants.
- This project uses **SPEC DRIVEN DEVELOPMENT**. Specs are not optional background material; they are the contract that implementation must follow.

## Documentation governance

1. `/docs` is the canonical documentation home for this repository.
2. Feature behavior, product rules, API behavior, schema expectations, and acceptance criteria must live under `/docs/specs/`.
3. Durable architecture decisions, technical invariants, and cross-cutting design rules must live under `/docs/decisions/`.
4. Conversations, implementation intent, rationale, tradeoffs, deprecated direction, debugging learnings, and traceability notes must live under `/docs/memories/`.
5. Files outside `/docs` may summarize or link, but they must not become shadow Sources of Truth.
6. If `/docs/decisions/` or `/docs/memories/` do not exist yet, create them in the same change that first needs them.

## Documentation precedence

- Current umbrella product specification: `/docs/specs/spec_1.0.md`
- Feature behavior and requirements: `/docs/specs/`
- Durable architecture decisions and technical rules: `/docs/decisions/`
- Traceability, conversation memory, rationale history, deprecations, and implementation intent: `/docs/memories/`

Until the spec is split into smaller feature-first documents, treat `/docs/specs/spec_1.0.md` as the umbrella source of truth for v1.

## Core working model

1. Update the spec before implementation when behavior is changing.
2. If the exact behavior is still being shaped, update the spec in the same change as the code.
3. Every non-trivial task should cite the exact spec section or approved spec delta it implements.
4. If code and spec disagree, resolve the disagreement in the spec instead of silently inventing behavior in code.
5. Do not hardcode business behavior that the product defines as operator-configurable ontology or policy data.
6. Prefer reversible, auditable changes that preserve publication, rollback, and traceability guarantees.

## Required workflow

1. Before implementing a feature, API, schema, policy rule, control-plane action, or retrieval behavior, create or update the relevant spec under `/docs/specs/`.
2. When a change introduces or modifies a durable technical rule, add or update a decision record under `/docs/decisions/`.
3. When a conversation or decision has likely future value, record it under `/docs/memories/` during the same workstream.
4. After implementation, update the touched spec and memory artifacts in the same change whenever behavior, intent, or rationale changed.
5. If a request is underspecified, clarify the spec instead of filling gaps with undocumented assumptions.
6. Every feature must have a synthetic test that exercises the feature through externally observable behavior instead of relying only on unit-level assertions or ad hoc manual checks.
7. Add or update the relevant synthetic test in the same change as the feature, and do not treat the feature as complete until that synthetic test passes or the missing harness is explicitly documented as a blocker.

## What must be memorized

Create or update a memory note under `/docs/memories/` when any of the following occurs:

- a product or technical decision changes implementation direction
- a conversation establishes scope, constraints, naming, priorities, or non-obvious assumptions
- a tradeoff is made between alternatives worth revisiting later
- a bug investigation produces root-cause knowledge that will help future work
- a migration, rollback, or deprecation path is chosen
- an operator-facing policy or ontology rule is clarified beyond what is already obvious in the spec
- a rejected idea should stay visible to prevent repeat debate

Do not create memory notes for trivial wording edits, mechanical refactors with no decision value, or facts already captured cleanly in the spec with no extra rationale.

## Memory note conventions

- Use feature-first folders under `/docs/memories/`.
- Use date-prefixed filenames: `YYYY-MM-DD-<type>-<slug>.md`.
- Suggested memory types: `conversation`, `decision-context`, `implementation-note`, `incident`, `migration`, `validation`.
- Each memory note should capture:
  - context
  - decision or observation
  - rationale
  - impacted specs, decisions, or code areas
  - follow-ups or unresolved questions
- Link memory notes to the relevant spec and decision record whenever possible.

## Decision record conventions

- Use numbered filenames: `000x-<slug>.md`.
- Create or update a decision record when the change establishes a durable rule, invariant, system boundary, or technology choice.
- Decision records should capture status, context, decision, alternatives considered, consequences, and links to related specs or memory notes.

## Config lifecycle guardrails

- Config work must respect the lifecycle `draft -> validated -> approved -> published -> archived`.
- Published config is immutable.
- Publish only with validation and simulation evidence.
- Rollback is a first-class operation and must affect future events without requiring redeploy.

## MemoryEngine v1 invariants

Until superseded by a newer approved spec, implementation must preserve these v1 invariants from `/docs/specs/spec_1.0.md`:

- PostgreSQL is the source of truth for configuration, memory state, audit history, and vector storage.
- API Ontology, Memory Ontology, and Policy Profiles are versioned product data, not hidden hardcoded behavior.
- Published configuration is immutable and must resolve through explicit config snapshots.
- Hard safety rules always override emergency, tenant, environment, and global policy layers.
- Every memory decision and persisted write must be traceable to both evidence and `config_snapshot_id`.
- Structured memory is the source of truth; vector retrieval is an aid.
- Tenant isolation, sensitivity ceilings, embedding redaction, and delete/forget semantics are mandatory.
- Publication and rollback must change behavior for future events without requiring backend redeploy.

## Implementation expectations

- Backend work should align with the Python + FastAPI service boundaries described in the spec.
- Frontend work should align with the Next.js + Tailwind CSS control plane described in the spec.
- API contract changes must update the spec and any generated or typed client strategy in the same change.
- Data model changes must preserve validation, simulation, publication, rollback, auditability, and tenant scoping.
- Acceptance criteria in `/docs/specs/spec_1.0.md` are the minimum shipping bar until replaced by newer approved docs.

## Repo checks

This repository is currently docs-first. Start with high-signal checks against the documentation source of truth:

- `rg --files docs`
- `rg -n "^## " docs/specs/spec_1.0.md`
- `rg -n "Acceptance Criteria|Observability and Audit|Security Rules" docs/specs/spec_1.0.md`

When runnable backend, frontend, or infra code lands, extend this section with concrete repo-local lint, test, typecheck, build, and synthetic test commands instead of generic placeholders.

Synthetic test commands should map back to documented feature acceptance criteria and cover the API, worker, and control-plane surfaces that the change affects.

## Verification expectations

- For policy or ontology changes, verify validation, simulation, publication, rollback, and audit behavior.
- For memory engine changes, verify deduplication, conflict resolution, supersession, sensitivity blocking, retrieval visibility, and delete/forget behavior.
- For API or schema changes, verify traceability fields, especially evidence linkage and `config_snapshot_id`.
- Prefer regression tests and checks that map directly to documented acceptance criteria.
- Every shipped feature must be covered by a synthetic test that verifies the feature end-to-end at the behavior level, not only through isolated implementation details.
- If a feature changes existing behavior, update the affected synthetic test as part of the same change and use that test as the primary verification evidence.
- If synthetic coverage is temporarily impossible, document the blocker, missing harness, and follow-up in the same workstream; the feature is not considered fully complete until synthetic coverage exists.

## Language and terminology

- Keep new docs in English by default unless bilingual content is explicitly needed.
- Use the product terminology defined by the spec consistently: `API Ontology`, `Memory Ontology`, `Policy Profile`, `Config Snapshot`, `Hard Safety Rules`, `Control Plane`, and `Memory Engine`.
- Keep specs normative and implementation memory notes factual.
