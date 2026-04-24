# Conversation: control-plane UI redesign plan

## Context

The current MemoryEngine operator console is functional, but the user called out that the UI/UX quality is poor enough to justify a full redesign. The user provided dark and light dashboard references and clarified that the images are directional references, not strict requirements.

## Decision or observation

The redesign should move toward a dark, dense operations-console direction while preserving every existing control-plane function. The implementation should start with a written plan, then proceed through shared foundation and shell improvements before deeper route-by-route rewrites.

## Rationale

The biggest current issue is not a missing feature. It is weak hierarchy: shell chrome, cards, badges, metrics, expert tools, lifecycle actions, and diagnostics often share the same visual weight. Improving the shared foundation first reduces repeated page-level drift and makes later config/runtime/inspect work more coherent.

## Impacted specs, decisions, and code areas

- [Control Plane UI Redesign Plan](../../specs/control-plane-ui-redesign-plan.md)
- [Spec 1.0](../../specs/spec_1.0.md), sections 16.2, 16.3, and 16.4
- [Decision 0006](../../decisions/0006-control-plane-ui-foundation-primer-shadcn-tailwind.md)
- `apps/web/src/app/globals.css`
- `apps/web/src/components/ui.tsx`
- `apps/web/src/components/console-shell.tsx`
- `apps/web/src/components/login-form.tsx`
- `apps/web/src/components/workspace-sections.tsx`

## Follow-ups or unresolved questions

- Decide whether to add an icon dependency later. The first implementation slice avoids new production dependencies and uses the existing Next.js + React + Tailwind baseline.
- After the foundation slice, continue with route-specific rewrites for config authoring, simulation, rollback, and inspect surfaces.

## 2026-04-24 feedback update

The user reviewed the first redesign slice and called out two problems:

- There are still too many blocks and too much information on the page, making the UI/UX difficult even for trained users.
- Responsive behavior still does not feel properly handled.

The next implementation step should reduce cognitive load rather than add more polish. Config authoring pages should default to one primary task lane, move expert/diagnostic surfaces behind progressive disclosure, remove duplicated metric cards, and make mobile start with document selection plus primary actions instead of long visible panels.
