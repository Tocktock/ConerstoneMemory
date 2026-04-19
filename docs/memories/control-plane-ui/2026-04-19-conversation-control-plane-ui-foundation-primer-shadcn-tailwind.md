# Control-plane UI foundation decision: Primer + shadcn/ui + Tailwind CSS

## Context

This conversation followed the 2026-04-18 control-plane UI audit, which identified the main product gap as inconsistent structure and hierarchy across the operator console rather than isolated visual polish problems.

The immediate question was which frontend foundation should guide the next control-plane iteration so route-level redesign work does not continue to branch in inconsistent directions.

## Decision / Observation

The control plane will use:

- GitHub Primer as the design standard
- `shadcn/ui` as the shared UI foundation
- Tailwind CSS as the code-level consistency enforcement layer

The first implementation slice should establish shell hierarchy before page rewrites. That slice includes shared navigation, page chrome, action hierarchy, and common primitives because those seams determine how every route reads and behaves.

## Rationale

The 2026-04-18 audit concluded that the biggest UX problem is not that individual pages lack styling. The bigger issue is that too many screens inherit the same flat card weight, weak action hierarchy, and inconsistent shell/page relationships.

Starting with page rewrites would lock that unstable hierarchy into more routes and likely require a second cleanup pass once the shared shell and primitives are corrected.

Starting with shell hierarchy first is the lower-churn sequence because it:

- fixes the highest-leverage cross-page inconsistency first
- creates one shared foundation for later page rewrites
- makes route-level redesign cheaper because new pages can inherit the same structure and primitives

## Impacted Specs / Decisions / Code Areas

- [Spec 1.0](../../specs/spec_1.0.md)
- [ADR 0006](../../decisions/0006-control-plane-ui-foundation-primer-shadcn-tailwind.md)
- [2026-04-18 control-plane UI audit](./2026-04-18-conversation-page-by-page-uiux-audit.md)
- `apps/web/src/components/console-shell.tsx`
- `apps/web/src/components/ui.tsx`
- `apps/web/src/components/workspace-sections.tsx`

## Follow-ups

- Translate the Primer-aligned shell hierarchy into concrete shell and primitive implementation rules before broad page rewrites.
- Rework page routes after the shared shell and primitive layer is stable enough to prevent repeated UI churn.
- Add a stable frontend synthetic harness for unauthenticated and authenticated control-plane flows. This foundation pass used live browser verification because the repository does not yet provide a dedicated UI synthetic test target.
