# 0005 API Ontology Package, Workflow Relationships, and Active Intent Memory

- Status: Accepted
- Date: 2026-04-16

## Context

The original v1 API Ontology model is a flat list of per-event API entries. That model works for event matching and per-event memory extraction, but it does not scale well when operators need to explain how many APIs relate to one broader user task.

Examples such as order registration, order retrieval, payment charge, and refund require:

- maintainable authoring structure
- explicit API-to-API relationship modeling
- durable user-intent memory derived from those relationships

The existing snapshot lifecycle should remain stable. The project already assumes one `api_ontology_document_id`, one `memory_ontology_document_id`, and one `policy_profile_document_id` per published snapshot.

## Decision

We will keep one published `api-ontology` config document per snapshot, but redesign its internal schema into an **API Ontology Package** with two authoring layers:

- `modules[]` for grouped API authoring
- `workflows[]` for relationship-aware intent inference

The package compiles into runtime indexes used by event matching and workflow resolution.

Workflow participation may produce a durable active intent memory, but only when a real observed event is persisted. Related APIs are stored as references/context only and are never persisted as synthetic executed events.

The first implementation keeps workflow membership unambiguous by requiring one owning workflow per API entry in the compiled package.

## Alternatives Considered

### Keep the flat `entries[]` model

Rejected because it does not express API families or user-task relationships cleanly and becomes hard to maintain at realistic API surface area.

### Create a second top-level workflow config document

Rejected for the first implementation because it would expand the snapshot lifecycle, validation, publication, rollback, and UI bundle model beyond the existing three-document contract.

### Make each API module a separate config document

Rejected for the first implementation because it would complicate publication and cross-module validation more than necessary.

## Consequences

- Validation must compile the API ontology package and reject duplicate, dangling, and ambiguous references.
- Runtime event evaluation must resolve module and workflow context after API match.
- Decision traces and inspect surfaces must expose workflow context.
- Memory persistence must support workflow intent memory as a first-class durable memory pattern.
- The control plane API Ontology editor should move toward grouped master-detail authoring, with raw YAML/JSON kept as expert mode.

## Related

- [Spec 1.0](../specs/spec_1.0.md)
