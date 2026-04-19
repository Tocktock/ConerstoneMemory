# Validation review pilot after shell hierarchy pass

## Context

After the shell-first control-plane foundation pass, the next product question was which route should pilot the first in-page workflow upgrade.

The control-plane UI audit already identified Validation as a better first candidate than the config authoring pages because it has one obvious operator job and lower information-architecture risk.

## Decision / Observation

Validation was chosen as the first route-level pilot for the new product direction.

The implementation keeps the existing backend contract and focuses on three UI-level changes:

- one shared in-page header pattern for product framing and actions
- one document-centric validation review flow instead of duplicated selectors
- clearer separation between current result summary, document health selection, checks, and blocking issues

The left-side document health list is now the primary selector for the page. The selected document controls both the current summary and the next validation run.

## Rationale

Validation is a safer proving ground than the config authoring pages because it does not immediately force decisions about raw source editing, diff placement, approval gates, or publication bundle layout.

The previous version of the page mixed two selection models:

- a top document selector
- a separate validation run list

That split made the page feel less product-like and increased the chance that the selected document and the displayed validation result would drift apart in operator perception.

By collapsing the page into one document-centric review flow first, the product gains a reusable pattern for:

- focused operator intent
- explicit page purpose
- summary-first interpretation
- cleaner empty-state treatment

## Impacted Specs / Decisions / Code Areas

- [Spec 1.0](../../specs/spec_1.0.md)
- [ADR 0006](../../decisions/0006-control-plane-ui-foundation-primer-shadcn-tailwind.md)
- [2026-04-18 control-plane UI audit](./2026-04-18-conversation-page-by-page-uiux-audit.md)
- `apps/web/src/components/ui.tsx`
- `apps/web/src/components/workspace-sections.tsx`

## Follow-ups

- Consider whether the new in-page header and empty-state patterns should replace ad hoc route headers in Simulation, Publication, and Inspect surfaces.
- If operators later need true per-document validation chronology instead of current health state, add that as a separate data-model and UI pass rather than overloading the current document health list.
