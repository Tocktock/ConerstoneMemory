# Control-plane UI/UX audit: page-by-page and component-by-component

## Context

The current operator console is functional, but the product-level complaint is valid: it is not yet consistent enough, beautiful enough, or product-like enough.

This audit was produced from the live local stack, not from static screenshots alone.

- Product framing: make the v1 operator console feel like one deliberate product rather than a collection of admin surfaces.
- Scope: all currently shipped web routes under `apps/web/src/app`, plus shared shell and primitive components.
- Constraint: preserve the v1 identity of a dense operator console rather than turning it into a consumer-facing marketing UI.
- Spec anchor: [Spec 1.0](../../specs/spec_1.0.md), especially `16.2 Required Pages`, `16.3 Required UX Features`, and `16.4 UI Design Direction`.

## Evidence

- Local stack booted with `./run.sh up-detached`.
- Read-only verification passed with `.venv/bin/python scripts/verify_compose_readonly.py`.
- Live browser audit artifacts were captured under `output/playwright/uiux-audit/`.
- Representative route captures:
  - `output/playwright/uiux-audit/login-desktop.png`
  - `output/playwright/uiux-audit/login-mobile.png`
  - `output/playwright/uiux-audit/config-api-ontology-desktop-full.png`
  - `output/playwright/uiux-audit/config-api-ontology-mobile.png`
  - `output/playwright/uiux-audit/config-api-ontology-mobile-menu.png`
  - `output/playwright/uiux-audit/validation-desktop-full.png`
  - `output/playwright/uiux-audit/simulation-desktop-full.png`
  - `output/playwright/uiux-audit/publication-desktop-full.png`
  - `output/playwright/uiux-audit/rollback-desktop-full.png`
  - `output/playwright/uiux-audit/decision-explorer-desktop-full.png`
  - `output/playwright/uiux-audit/memory-browser-desktop-full.png`
  - `output/playwright/uiux-audit/audit-log-desktop-full.png`
  - `output/playwright/uiux-audit/audit-log-mobile.png`

## Decision / Observation

The console already has one shared palette, one type scale, and one shell, so the problem is not absence of styling. The problem is that nearly every surface uses the same visual weight, the same rounded card treatment, and the same badge language regardless of whether it is:

- navigation
- page chrome
- object status
- metrics
- destructive actions
- expert-only tooling
- empty state messaging

That flattens hierarchy and makes the product feel assembled rather than authored.

The most important product judgment is this:

**The next UI/UX pass should prioritize structural clarity and action hierarchy before visual polish.**

If that order is reversed, the console will look more decorated but still feel inconsistent.

## Product direction

The console should move toward five stable principles:

1. One page, one primary job.
   Every route needs one obvious primary action and one obvious reading order.

2. Dense does not mean flat.
   Primary regions, secondary diagnostics, and expert tooling need visibly different surface tiers.

3. Make state meaningful.
   Status chips should describe the active object or result, not act as a static legend.

4. Reveal complexity progressively.
   Structured authoring, raw source editing, revision diff, import, publication notes, bundle preview, and validation should not all compete at the same level on first render.

5. Empty states must teach.
   A blank result set should explain what to do next, not just leave a large dark void.

## Page-by-page audit

| Page | Current state | What breaks product feel | Improvement direction |
| --- | --- | --- | --- |
| Login | Clean split layout with product intro on the left and auth form on the right. | The left rail repeats information that the shell repeats later, and the right-side support card feels like utility copy instead of a product trust block. The page is competent, but not memorable. | Collapse duplicate backend messaging into one compact trust section. Give the left panel a clearer product story, operator value proposition, and environment context. Make the auth module feel like a deliberate gateway, not a generic form card. |
| API Ontology | Most powerful page, but also the most overloaded. Structured editor, raw source editor, diff, import, bundle preview, validation, and publication history all appear in one long stack. | Too many cards share identical weight. The action grid has weak semantic hierarchy. The page reads like a full database admin workbench instead of a guided authoring product. Mobile top chrome is crowded before the real task starts. | Split into progressive layers: overview, structured authoring, expert source, history. Keep one sticky action bar for save, validate, approve, publish. Move supporting diagnostics into a secondary rail or collapsible sections. |
| Memory Ontology | Simpler than API Ontology, but still inherits the same skeleton. | The raw source editor visually dominates the actual memory-model authoring task. Summary preview is low value compared with ontology entry management. | Introduce structured ontology sections as the primary path, keep raw source as expert mode, and demote revision diff and import into secondary tools. |
| Policy Profile | Functionally similar to Memory Ontology, but with denser policy content. | The page presents policy logic as a text wall. It feels like editing a config blob, not tuning a product policy system. | Group policy into semantic sections such as sensitivity, frequency, inference, and forget rules. Add human-readable summaries and consequences before exposing the raw source. |
| Validation | More focused than config pages. Metrics and selected run details are understandable. | The document select and run list duplicate each other. The call to action is detached from the selected document context. Empty issue panels feel inert. | Merge selection into one primary run history component. Promote current result summary and show why pass, warn, or fail matters. Use issues space for guided interpretation, not just a blank box. |
| Simulation | Weakest product surface in the runtime set. | The page shows a narrow form beside a very large empty area until the first run. It feels unfinished rather than intentionally calm. | Rebuild as a guided composer with presets, event editing, and a strong empty state. After a run, show a narrative result layout: before, after, reason codes, write delta, and policy override in one readable flow. |
| Publication | Serviceable and already close to a product review screen. | Filters, metrics, bundle picker, and history all compete for attention. Snapshot cards still read like storage objects more than operator events. | Turn history into a stronger timeline. Emphasize release notes, actor, affected bundle, and current active state. Make active versus historical snapshots visually clearer. |
| Rollback | Strongest page because it is focused on one irreversible-looking operation. | The left selection area wastes space when there are few snapshots. The destructive nature of rollback is under-communicated, and the CTA looks too similar to other primary actions. | Add explicit consequence framing, affected scope, and rollback safety notes. Differentiate destructive rollback styling from standard positive primary actions. |
| Decision Explorer | Filter-heavy inspect surface with no onboarding. | Zero results create a large dead slab. The experience feels database-first and gives no help when there is nothing to inspect yet. | Add a guided empty state with sample filters, example queries, and links to the pages that generate decisions. Use expandable result cards when data exists. |
| Memory Browser | Similar structure to Decision Explorer but with even weaker first-run guidance. | It defaults to an operator email query that can still return zero rows, so the page looks broken instead of empty-by-design. Metrics have no meaning without records. | Add explicit search guidance, sample identities, and a first-run explanation of what a valid tenant/user query looks like. Distinguish “no query yet” from “query returned no memory.” |
| Audit Log | Best data-heavy page in the current UI. The table already feels more product-like than several card-based pages. | The checksum column dominates the table. On mobile, the filter stack consumes the first screen before the operator reaches the data. The view is still more infra-facing than operator-facing. | Keep the dense table on desktop, but truncate hashes, move advanced values into expandable details, and add a mobile card layout or saved-filter summary above the data. |

## Component-by-component audit

| Component / area | Current issue | Evidence in code | Improvement direction |
| --- | --- | --- | --- |
| Global visual system | The palette is coherent, but almost every surface uses the same panel recipe, so hierarchy collapses. | `apps/web/src/app/globals.css` | Introduce surface tiers for shell, page chrome, primary work area, secondary diagnostics, and destructive flows. |
| Shell header | The mobile header mixes route title, initials, menu, sign-out, and static legend chips. Those legend chips do not represent current page state. | `apps/web/src/components/console-shell.tsx` | Replace the static chip legend with contextual page metadata. Move account actions into one account control. Reduce first-screen chrome on mobile. |
| Navigation shell | Navigation works but still feels like a generic side rail. The desktop shell and mobile drawer are visually similar to content cards rather than a distinct navigation system. | `apps/web/src/components/console-shell.tsx` | Give navigation a clearer product identity, stronger active-group emphasis, and cleaner desktop/mobile parity. |
| Buttons | Primary, secondary, and destructive actions are too similar in shape and layout. Action hierarchy is often learned by reading labels rather than scanning weight. | `apps/web/src/components/ui.tsx` | Define a stricter button hierarchy and use one clear primary CTA per page section. |
| Badges and chips | One badge component is being asked to represent status, identity, counts, and glossary chips. | `apps/web/src/components/ui.tsx`, `apps/web/src/components/console-shell.tsx` | Split into distinct status badges, metadata pills, and count chips with different semantics and density. |
| Cards and panels | Nested cards inside cards create a flat, repetitive interface. | `apps/web/src/components/ui.tsx`, `apps/web/src/components/workspace-sections.tsx` | Standardize when to use page sections, cards, inset panels, and diagnostic blocks. Not every grouping needs a full bordered container. |
| Metrics | Metric tiles are used even when the numbers are not the main decision point, especially on empty pages. | `apps/web/src/components/ui.tsx`, `apps/web/src/components/workspace-sections.tsx` | Use metrics only when they help operators compare or act. Remove decorative zero-metric rows from blank states. |
| Forms and long editors | Inputs are readable and touch-safe, but long forms have weak grouping, little wayfinding, and minimal progressive disclosure. | `apps/web/src/components/ui.tsx`, `apps/web/src/components/workspace-sections.tsx` | Add sub-navigation, grouped sections, sticky local anchors, and advanced-mode collapses for expert fields. |
| Raw source, diff, and import tools | Expert tools appear at the same visual priority as core authoring. | `apps/web/src/components/workspace-sections.tsx` | Treat raw editors, import tools, and diffs as expert panels, not co-equal first-screen content. |
| Empty / loading / error states | `StateCard` is generic, and several resultless pages render large empty areas instead of clear onboarding. | `apps/web/src/components/workspace-sections.tsx` | Introduce dedicated empty-state patterns with explanation, examples, and next steps per workspace. |
| Confirmation gates | Publish, archive, discard, and rollback confirmations are functionally correct but visually generic. | `apps/web/src/components/workspace-sections.tsx` | Add consequence framing, affected scope, and stronger destructive affordances for risky actions. |
| Data lists and tables | Validation, publication, inspect, and audit all use different density patterns with no shared list anatomy. | `apps/web/src/components/workspace-sections.tsx` | Standardize result-list structure, detail expansion, truncation rules, and mobile fallbacks. |

## Responsive observations

The responsive pass solved reachability better than before, but not product coherence.

- The mobile drawer itself is usable and understandable.
- The mobile page header is still too busy before content starts.
- Sign-out plus four status chips take space that should belong to the page task.
- Filter-heavy pages such as Audit Log, Decision Explorer, and Memory Browser push actual results too far below the fold.
- Dense authoring pages remain technically accessible on mobile, but still feel like desktop workbenches compressed into one column.

## Recommended sequence

### Phase 1: foundation

- redesign the shell header and account/navigation model
- replace the static status legend with contextual status presentation
- define button, badge, chip, metric, and surface tiers
- standardize empty, loading, and error states

### Phase 2: authoring pages

- refactor Config pages around one primary authoring path
- make raw source, revision diff, import, and history clearly secondary
- add local navigation and progressive disclosure for API Ontology specifically

### Phase 3: runtime pages

- rebuild Simulation around guided composition and result storytelling
- tighten Validation into one clear review flow
- strengthen Publication and Rollback consequence framing

### Phase 4: inspect pages

- redesign zero-result states for Decision Explorer and Memory Browser
- make Audit Log mobile-friendly and reduce checksum dominance
- standardize result card density across inspect surfaces

### Phase 5: responsive polish

- run a second browser pass on phone, tablet, laptop, and desktop widths
- explicitly verify first-screen task reachability and first meaningful action per route

## Rationale

This ordering improves product feel fastest because the biggest source of inconsistency is not page-specific styling. It is the repeated structural pattern of:

- too much equal-weight chrome
- too many same-looking cards
- too little distinction between primary work and expert tooling
- too little guidance when the system has no data yet

Fixing those system seams first will make later page-level polish cheaper and more consistent.

## Impacted specs / decisions / code areas

- [Spec 1.0](../../specs/spec_1.0.md)
- `apps/web/src/app/(auth)/login/page.tsx`
- `apps/web/src/app/globals.css`
- `apps/web/src/components/console-shell.tsx`
- `apps/web/src/components/ui.tsx`
- `apps/web/src/components/workspace-sections.tsx`
- `output/playwright/uiux-audit/`

## Follow-ups

- Decide whether raw YAML/JSON editing stays on the primary config pages or moves behind an explicit expert-mode entry point.
- Decide whether the static lifecycle glossary in the shell header should become contextual help or live elsewhere in the product.
- Convert this audit into an approved implementation plan before making large UI changes, because the config pages will need structural, not cosmetic, edits.
