# Control Plane UI Redesign Plan

Status: Draft for implementation
Date: 2026-04-24
Spec anchor: [spec_1.0.md](./spec_1.0.md), especially sections 16.2, 16.3, and 16.4.

## Goal

Redesign the MemoryEngine operator console so the current functionality remains intact while the interface becomes easier to scan, safer to operate, and more coherent across desktop, tablet, and phone widths.

This is a product UI/UX redesign, not a new feature surface. The redesign must preserve the required control-plane jobs:

- author API Ontology, Memory Ontology, and Policy Profile documents
- edit structured config and raw YAML/JSON
- inspect revision diff
- import and export config source
- validate, approve, publish, archive, and roll back config
- run sample-event simulation
- inspect decisions, memories, and audit logs

## Reference Interpretation

The provided references should guide mood and direction, not exact layout cloning.

The chosen direction is:

- dark operations console, not a light marketing admin page
- restrained neutral palette with one blue-cyan accent for primary action
- high contrast text and state markers without neon glow
- stable left navigation on wide screens
- compact top context bar and primary action zone
- editor/workbench composition for config pages
- status and audit surfaces that feel operational rather than decorative

The redesign must avoid:

- large generic dashboard cards that all have the same visual weight
- first-screen chrome that pushes the actual task below the fold
- mobile layouts that require reading all filters before reaching the result
- hiding safety-critical lifecycle actions behind decorative UI
- weakening raw source, diff, import/export, validation, publication, or rollback features

## Functional Preservation Matrix

| Area | Required preserved behavior | UX direction |
| --- | --- | --- |
| Login | Live backend authentication, visible request errors, seeded local role hints | Treat as a deliberate operator gateway with environment trust context |
| Shell | Route switching, session display, sign out, backend boundary display | Reduce static badges, make page context and active section easier to scan |
| API Ontology | Document selection, metadata edit, structured package editor, modules, entries, workflows, raw source, diff, import/export, validation, approval, publish, archive | Primary structured authoring lane with secondary expert tools and diagnostics |
| Memory Ontology | Document selection, metadata, raw source, diff, import/export, lifecycle actions | Promote memory model comprehension before raw source editing |
| Policy Profile | Document selection, metadata, raw source, diff, import/export, lifecycle actions | Group policy consequences around safety, frequency, inference, and forget rules |
| Validation | Config selection, validation run, check details, warnings/failures | One focused document health review flow |
| Simulation | Config document selection, sample event selection, run result, before/after decision, reason codes, memory candidates | Guided composer with result story after execution |
| Publication | Snapshot list, active/history state, bundle contents, release notes | Timeline-style release review with active snapshot emphasis |
| Rollback | Snapshot selection, confirmation, future-behavior rollback | Strong consequence framing and distinct destructive affordance |
| Decision Explorer | Filters, decision records, evidence, policy, result | Search-first inspect surface with useful empty and zero-result states |
| Memory Browser | Tenant/user/type filters, memory records, evidence, sensitivity, active state | Distinguish no query, no result, and real result states |
| Audit Log | Scope/tenant/environment filters, action filters, search, event records | Dense desktop table and mobile-friendly event cards/details |

## Design System Direction

### Surface tiers

Use explicit surface roles instead of one generic card style:

- `shell`: navigation and global context
- `topbar`: current workspace, primary route context, account actions
- `workspace`: main editable/readable content
- `rail`: secondary diagnostics, bundle status, validation, history
- `inset`: grouped fields inside a larger workspace
- `danger`: destructive or irreversible-looking actions

### Typography

- Keep a software-console sans stack; do not introduce serif or marketing display treatment.
- Use tabular numbers for metrics, versions, timestamps, and counts.
- Reduce all-caps label dominance where labels compete with real content.
- Keep line lengths readable in explanatory blocks, but avoid explanatory text that replaces actual controls.

### Color

- Keep a dark charcoal/navy console base.
- Use one primary blue-cyan accent for the main action and selected navigation.
- Use green, amber, and red only for semantic status.
- Avoid broad blue/purple gradients and decorative glow.

### Interaction

- Buttons must have clear hover, focus, disabled, and pressed states.
- Loading states should resemble the target layout, not generic centered text.
- Empty states should explain the next operator action.
- Confirmation gates must describe consequence and affected scope.

## Responsive Rules

The UI must be verified at these widths:

- 390px phone
- 768px tablet
- 1024px laptop
- 1440px desktop

Responsive requirements:

- the primary task or primary action must be visible without scrolling through a full navigation rail first
- mobile shell must not spend the first viewport on static status chips
- filter-heavy inspect pages must show a concise filter summary before advanced controls
- multi-panel authoring must stack before fields become unreadable
- tables must degrade to readable cards or horizontally constrained rows where needed
- sticky action bars must not cover form fields or confirmation controls

## Implementation Sequence

### Phase 1: Foundation and shell

1. Replace generic panel/card hierarchy with explicit surface tiers.
2. Tighten global color tokens, shadows, focus rings, transitions, and numeric typography.
3. Redesign console shell around a quieter sidebar and compact topbar.
4. Replace static route/status badges with contextual workspace state.
5. Improve loading and backend-unavailable states.

### Phase 2: Shared workspace primitives

1. Add reusable workspace layout primitives for main lane plus context rail.
2. Split badge semantics into status, metadata, and count variants.
3. Improve metrics so they are used only where they support decisions.
4. Add consistent empty, error, and confirmation patterns.

### Phase 3: Config authoring pages

1. Keep structured editing primary for API Ontology.
2. Demote raw YAML/JSON, import, and diff into expert or secondary zones.
3. Preserve lifecycle actions near the selected document context.
4. Add stronger bundle status and validation result rails.

### Phase 4: Runtime and inspect pages

1. Rebuild Simulation as composer plus result story.
2. Tighten Validation around document health.
3. Convert Publication to an active/history timeline.
4. Strengthen Rollback consequence framing.
5. Improve Decision Explorer, Memory Browser, and Audit Log empty/mobile states.

### Phase 5: Browser verification and hardening

1. Run typecheck and web tests.
2. Build the Next.js app.
3. Inspect all routes in a browser at the required responsive widths.
4. Capture screenshots for desktop and mobile evidence.
5. Update this plan or memory notes if implementation constraints change the sequence.

## First Implementation Slice

This workstream starts with Phase 1 and the highest-leverage parts of Phase 2:

- global tokens and surface tiers
- shared primitive styling
- console shell and mobile header
- login gateway polish
- safer state/empty/error presentation defaults

This slice intentionally does not remove any route or backend action. Route-specific deep rewrites continue after the shared foundation is stable.

## Feedback Correction: Reduce Cognitive Load

The first implementation slice improved visual consistency but still exposed too many blocks, panels, metrics, and diagnostic tools at once. The next slice must optimize for first-time operator comprehension before visual richness.

Revised direction:

- Default pages should expose one primary task lane.
- Secondary tools must use progressive disclosure, not permanent side rails.
- Expert raw source, revision diff, import, bundle diagnostics, validation details, and publication history must stay reachable but should be collapsed by default on config authoring pages.
- Duplicate metadata should be removed. If a value appears in the header, do not repeat it as a metric card immediately below.
- Mobile pages must show the selected task and primary action before long document lists, diagnostics, or navigation detail.
- Navigation and page headers should use fewer blocks. Context should be conveyed through concise text and state, not repeated cards.

Additional responsive acceptance:

- At 390px, config authoring starts with page context, document selector, lifecycle actions, and the editor lane; expert tools appear below a collapsed control.
- At 768px, the page should remain single-column until there is enough width for reliable two-column editing.
- At desktop widths, permanent side rails are allowed only when they reduce work. They must not duplicate information already present in the main lane.
- Every collapsed section must have a clear label so existing functionality remains discoverable.

## Acceptance Criteria

- The route set remains unchanged.
- Existing config lifecycle actions remain reachable.
- Existing validation, simulation, publication, rollback, decision, memory, and audit flows remain reachable.
- Default config authoring pages show fewer blocks before the primary editor.
- Expert and diagnostic tools remain reachable through progressive disclosure.
- `npm run typecheck` passes.
- `npm run test:web` passes.
- `npm run build` passes or the blocker is documented with exact output.
- The local app can be opened in a browser and inspected at phone and desktop widths.
