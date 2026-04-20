# ADR 0003: Normalized event envelopes and hybrid rule-LLM policy decisions

Status: Accepted

## Context

The original v1 specification assumed normalized API events and deterministic policy evaluation, but the next refinement needs a stronger contract for two areas:

- runtime input should come from selected request/response facts, not from `api_name` alone
- a post-processing model should be able to assist with memory-worthiness and candidate extraction without becoming the final authority on persistence

Without a stricter design, the platform risks either underfitting real API behavior or over-trusting raw payloads and model output in ways that weaken auditability and safety.

## Decision

We will treat the runtime input as a normalized event envelope built from bounded request/response field selectors defined by API Ontology entries. Raw request/response payloads are optional evidence artifacts, not the default policy-layer input.

We will adopt a hybrid decision pipeline:

- rules first for hard safety, explicit forget/delete handling, and clear deterministic routing
- model second for memory-worthiness recommendation and candidate extraction when the ontology/policy allows or requires escalation
- rules last for final policy validation, sensitivity enforcement, ontology eligibility checks, and final action selection

The model may recommend; it may not directly persist memory without final policy approval.

Explicit writes, explicit forget/delete events, and hard-blocked sensitive events should bypass model invocation when the active API Ontology entry and Policy Profile say they should.

We will store inference traces as auditable runtime artifacts, including model identity, prompt version, confidence, recommendation summary, and final policy action.

## Alternatives Considered

- Keep `api_name` and ad hoc structured fields as the only ingress contract.
- Let the model make the final persistence decision.
- Pass full raw request/response bodies directly into model prompts by default.

These options were rejected because they either lose needed semantic context, weaken safety guarantees, or reduce the explainability of persistence decisions.

## Consequences

- API Ontology becomes responsible for event matching, field selection, redaction boundaries, and model-escalation eligibility boundaries.
- The Policy Profile must include model-governance and internal provider-routing rules in addition to frequency and sensitivity rules.
- Runtime auditability improves because model recommendations and final policy outcomes can be compared directly.
- Ingestion becomes more explicit about which parts of request/response data are safe and relevant.

## Links

- [Umbrella spec](../specs/spec_1.0.md)
