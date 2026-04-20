## Context

The API Ontology control-plane page had a responsive layout gap between the mobile stack and the ultra-wide desktop composition. On mid-sized screens, the document selector, structured authoring summary cards, and right-side diagnostics all promoted into multi-column layouts too early, which made the editor lanes noticeably cramped.

The conversation direction for this change was:

- keep the first summary component in a header-like position
- preserve the existing mobile behavior
- improve the mid-sized layout where cards and editors were becoming too narrow

## Decision or observation

Adjusted the API Ontology page breakpoints so that:

- the document selector rail stays stacked above the editor until a wider breakpoint
- the first structured-authoring summary card remains full-width through the mid-sized range
- the right-side diagnostics rail stays below the main editor until extra-wide screens
- the module map and detail editor can still sit side-by-side once the content lane has enough room

## Rationale

The earlier breakpoint promotion created a false desktop state: the page technically had multiple columns, but the working surfaces were too narrow for real authoring. Keeping the lead card and document selector in top-of-page positions longer preserves hierarchy, while delaying the diagnostic rail gives module and entry editing the width it needs.

## Impacted specs, decisions, or code areas

- Spec impact: none; this is a responsive presentation change, not a product behavior change
- Code: `/Users/jiyong/playground/MemoryEngine/apps/web/src/components/workspace-sections.tsx`
- Related memory: `/Users/jiyong/playground/MemoryEngine/docs/memories/control-plane-ui/2026-04-18-conversation-page-by-page-uiux-audit.md`

## Follow-ups or unresolved questions

- The frontend currently does not have a browser-based responsive layout harness, so verification for this change is manual browser inspection plus typechecking.
- If more responsive refinements are needed across the control plane, add a lightweight visual regression path for key breakpoints before further layout tuning.
