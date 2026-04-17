# Responsive control-plane layout corrections

## Context

The operator console gained more dense authoring surfaces, especially in the API Ontology workspace. In the live UI, that density exposed a breakpoint problem: the shell and workspace grids both switched into desktop layouts too early, which caused intermediate widths to collapse into narrow, partially unreadable side rails.

The most visible failures were:

- a mobile/tablet experience that forced operators to scroll through the full navigation rail before reaching page content
- a small-laptop layout where the desktop sidebar introduced its own nested scrollbar
- an `xl` API Ontology editor layout that compressed metadata and module-detail panes into unusable widths

## Decision / Observation

The console should treat small laptops and tablets as compact layouts, not as full desktop layouts. The responsive fix therefore has two parts:

- move the full sidebar shell to larger breakpoints and use a compact mobile navigation pattern below that threshold
- delay nested multi-rail editor layouts until there is enough width for both the shell and the editor internals to remain legible
- scale shared form text, labels, and action heights for touch layouts so mobile editors do not keep desktop microcopy sizing or trigger iOS focus zoom
- make badge-adjacent publication, decision, memory, and audit surfaces shrink safely so text yields before pills or table columns collapse

We also clarified the v1 frontend spec so responsive control-plane behavior is explicit instead of implied.

## Rationale

This keeps the dense admin style required by the product while preventing the interface from degrading into clipped controls, stacked route slugs, or hidden primary content.

The change is not a visual redesign of the control plane. It is a usability correction so the existing operator workflows remain reachable and readable across supported viewport sizes.

## Impacted Specs / Decisions / Code Areas

- [Spec 1.0](../../specs/spec_1.0.md)
- `apps/web/src/components/console-shell.tsx`
- `apps/web/src/components/ui.tsx`
- `apps/web/src/components/workspace-sections.tsx`

## Follow-ups

- Add a repo-local browser synthetic harness for responsive console verification instead of relying on manual live-browser sweeps.
- Recheck each control-plane route against the same breakpoint set when new authoring panels are introduced.
