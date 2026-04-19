# 0006 Control-plane UI foundation: GitHub Primer, shadcn/ui, and Tailwind CSS

- Status: Accepted
- Date: 2026-04-19

## Context

The v1 control plane already has a functional shared shell and route set, but the current UI direction is under-specified at the foundation level. The existing frontend spec requires a Next.js operator console with Tailwind CSS, and the 2026-04-18 control-plane audit concluded that the main UX weakness is structural inconsistency rather than lack of isolated page styling.

Without an explicit foundation decision, route work risks drifting in three ways:

- shell hierarchy and page chrome may continue to evolve differently across pages
- shared primitives may fork into one-off local components instead of a reusable console foundation
- Tailwind may be used as a styling convenience instead of a consistency enforcement layer

The repository therefore needs one durable rule that separates:

- the design standard operators should recognize
- the shared component foundation engineers should build on
- the code-level mechanism that keeps the UI consistent over time

## Decision

The control-plane UI foundation is defined as follows:

- GitHub Primer is the design standard for information hierarchy, navigation structure, forms, tables, overlays, and state communication.
- `shadcn/ui` is the shared React UI foundation for control-plane primitives and composed operator workflows.
- Tailwind CSS remains the code-level consistency enforcement layer for layout, spacing, typography, color, responsive behavior, and state styling.

Primer sets the product interaction and visual standard, but it does not require a direct Primer React dependency. `shadcn/ui` is the implementation-facing component foundation because it is composable, repo-friendly, and compatible with the existing Next.js and Tailwind baseline.

The first implementation slice under this decision is the shell hierarchy and shared primitives layer before route-by-route page rewrites.

## Alternatives Considered

### Keep the current bespoke component direction

Rejected because the current route set already shows hierarchy drift across shell, page chrome, badges, cards, and action treatment. Keeping the foundation implicit would preserve that drift.

### Adopt Primer React as the runtime component dependency

Rejected for the first implementation because the product needs Primer as a durable design standard, not a mandatory third-party runtime dependency. That would add unnecessary coupling where design guidance is the real requirement.

### Rewrite pages individually before standardizing the shell

Rejected because the audit shows the shell, navigation, and page-level hierarchy are the highest-leverage consistency problems. Rewriting pages first would multiply churn and force later rework when the shared foundation changes.

## Consequences

- The frontend spec must state Primer, `shadcn/ui`, and Tailwind CSS as distinct but complementary roles.
- Shared control-plane primitives should converge on `shadcn/ui`-aligned composition instead of growing separate page-local UI patterns.
- Shell hierarchy, navigation, page chrome, and action tiers become the first migration target before deeper page rewrites.
- Tailwind CSS remains mandatory as the consistency layer, which limits style drift and keeps responsive behavior grounded in shared utilities and tokens.

## Related

- [Spec 1.0](../specs/spec_1.0.md)
- [2026-04-18 control-plane UI audit](../memories/control-plane-ui/2026-04-18-conversation-page-by-page-uiux-audit.md)
