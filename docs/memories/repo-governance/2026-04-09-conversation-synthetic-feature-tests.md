# Synthetic feature tests are a repository workflow requirement

## Context

During repository setup, the team clarified that feature verification must not stop at unit-level checks or one-off manual validation. The request was to make synthetic testing a standing rule in the repository guidance.

## Decision

We will treat synthetic tests as mandatory coverage for every feature. Each feature change must add or update a synthetic test that verifies externally observable behavior, and feature work is not considered complete until that synthetic test passes or the missing harness is explicitly recorded as a blocker.

## Rationale

The product is spec-driven and centers on behavior that spans configuration, runtime policy resolution, persistence, rollback, auditability, and control-plane actions. Synthetic tests provide better evidence that implemented behavior still matches acceptance criteria across those boundaries than isolated implementation checks alone.

## Impacted Areas

- [Project AGENTS rules](../../../AGENTS.md)
- [Umbrella spec](../../specs/spec_1.0.md)
- future backend, worker, and web verification commands

## Follow-ups

- Add concrete synthetic test commands to `AGENTS.md` once runnable application surfaces land.
- Map future feature work to synthetic scenarios that align with documented acceptance criteria.
