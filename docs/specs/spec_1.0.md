## Solution

# Final Specification Sheet

## Human-Configurable API-Driven Memory Platform v1

This specification defines a **human-configurable, API-driven memory platform** whose core behavior is controlled by **manually authored API Ontology, Memory Ontology, and Policy Profiles**. The runtime still has the same four logical engines—**API Ontology Registry, Memory Ontology, Memory Policy Layer, and Memory Engine**—but v1 now makes an operator-facing **Ontology & Policy Control Plane** mandatory, because ontology and policy are first-class product data, not hardcoded behavior.

The implementation baseline for v1 is **PostgreSQL 18.3**, **pgvector 0.8.2**, **Python 3.14.4**, **FastAPI 0.135.3**, **Next.js 16.2.3**, **Tailwind CSS 4.2.2**, and **Docker Compose 5.1.1**. Docker Compose is explicitly designed to define and run a multi-container application stack from a single YAML configuration file. For the frontend container runtime, use a supported Node.js line; **Node.js 24.14.1** is the latest LTS release as of April 9, 2026. ([PostgreSQL][1])

The product should keep **structured memory** and **vector memory** inside PostgreSQL, using **pgvector** so vectors live next to the rest of the memory state instead of requiring a second database. pgvector is built specifically for vector similarity search in Postgres and supports both exact and approximate nearest-neighbor retrieval. ([GitHub][2])

---

## 1. Product Objective

The system shall accept user API events, interpret them through a **human-authored API Ontology**, evaluate them with a **human-authored Policy Profile**, and persist only the memories that are both **useful** and **allowed** by a **human-authored Memory Ontology**.

The primary purpose of v1 is not “automatic memory discovery at all costs.” The primary purpose is **controlled memory creation**.

The product must optimize for:

* operator control
* explainability
* safe defaults
* deterministic conflict handling
* tenant isolation
* easy rollback without code redeploy

---

## 2. Product Thesis

### 2.1 Core Thesis

**Policy is configuration, not code.**
Operators must be able to change how memory works by editing versioned definitions rather than redeploying the backend.

### 2.2 What “human-configurable” means in v1

Humans must be able to:

* manually define what an API means
* manually define what kinds of memories exist
* manually define frequency thresholds
* manually define sensitivity ceilings
* manually define deduplication and conflict rules
* simulate the effect of a rule change before publish
* publish and roll back configuration safely

### 2.3 What humans must not be allowed to do

Humans must **not** be allowed to bypass hard platform safety rules. For example:

* secrets and credentials remain blocked
* prohibited sensitivity classes remain blocked
* unsafe embedding of raw restricted content remains blocked

---

## 3. Scope

### 3.1 In Scope for v1

v1 covers:

* explicit profile memories
* explicit preference memories
* user-to-customer relationship memories
* repeated interest/topic memories
* versioned API ontology definitions
* versioned memory ontology definitions
* versioned policy profiles
* tenant-level overrides
* simulation, publication, rollback, and audit
* hybrid retrieval using exact lookup + relation lookup + vector search

### 3.2 Out of Scope for v1

v1 excludes:

* arbitrary executable code inside ontology definitions
* autonomous ontology generation without human review
* full free-form knowledge graph reasoning
* high-risk secret storage
* medical, financial, or legal sensitive inference persistence by default
* separate graph database adoption

---

## 4. System Principles

1. **Config-as-data**
   Ontologies and policy are stored as versioned documents in PostgreSQL.

2. **Human-in-the-loop first**
   Every important semantic rule can be manually inspected, edited, tested, and published.

3. **Runtime determinism**
   Every decision must record the exact config snapshot used.

4. **Hard safety over soft policy**
   Non-overridable safety rules always win.

5. **Structured truth over vector-only memory**
   Facts, relations, and version history are the source of truth; embeddings are a retrieval aid.

6. **Rollback without redeploy**
   Publishing a previous config snapshot must revert behavior for new events immediately.

---

## 5. High-Level Architecture

### 5.1 Runtime Components

The runtime consists of four logical components:

1. **API Ontology Registry**
   Maps API events to semantic meaning.

2. **Memory Ontology**
   Defines what memories can exist and how they behave.

3. **Memory Policy Layer**
   Uses the ontologies plus policy parameters to decide block / observe / session / upsert / forget.

4. **Memory Engine**
   Normalizes, resolves, deduplicates, versions, stores, retrieves, and forgets memory.

### 5.2 Operator-Facing Component

A fifth surface is required operationally:

5. **Ontology & Policy Control Plane**
   Lets humans author, validate, simulate, publish, and roll back API Ontology, Memory Ontology, and Policy Profiles.

This is not a separate “business engine.” It is the operational shell around the first three config-driven components.

---

## 6. Technology Baseline

### 6.1 Deployment Model

The entire stack shall run with a single Docker Compose project. A single `docker compose up -d` should bring up the database, API service, worker, and web application in one application stack. Docker’s documentation defines Compose as a tool for controlling a whole application stack through one YAML file, including services, networks, and volumes. ([Docker Documentation][3])

### 6.2 Selected Stack

* **Database:** PostgreSQL 18.3
* **Vector extension:** pgvector 0.8.2
* **Backend runtime:** Python 3.14.4
* **Backend framework:** FastAPI 0.135.3
* **Frontend framework:** Next.js 16.2.3
* **Frontend styling:** Tailwind CSS 4.2.2
* **Orchestration:** Docker Compose 5.1.1
* **Recommended frontend runtime line:** Node.js 24.14.1 LTS ([PostgreSQL][1])

### 6.3 Implementation Direction

The backend shall expose REST APIs via FastAPI. The frontend shall be a Next.js admin console styled with Tailwind CSS. FastAPI should expose OpenAPI, and the frontend should consume either direct typed models or a generated TypeScript client to reduce contract drift; FastAPI documents a TypeScript client-generation flow from the OpenAPI schema, and Next.js includes built-in TypeScript support. ([FastAPI][4])

---

## 7. Control Plane: Human-Configurable Ontology and Policy

This is the most important part of the v1 design.

### 7.1 Source of Truth

The source of truth for configuration shall be PostgreSQL, not code files on disk.

Configuration families:

* **API Ontology Documents**
* **Memory Ontology Documents**
* **Policy Profile Documents**

### 7.2 Authoring Methods

Operators must be able to manage these documents through:

* a web UI
* a REST admin API
* YAML/JSON import/export

### 7.3 Lifecycle

Each configuration document must move through this state model:

* `draft`
* `validated`
* `approved`
* `published`
* `archived`

`published` documents must be immutable.

### 7.4 Scope Hierarchy

Configurations must support multiple scopes:

* `global`
* `environment` (`dev`, `staging`, `prod`)
* `tenant`
* `emergency_override`

### 7.5 Precedence Order

The runtime must resolve policy in the following order:

1. hard platform safety rules
2. emergency override
3. tenant override
4. environment override
5. global published config
6. default runtime fallback

API Ontology `source_precedence_key` values must bind to Policy Profile `source_precedence` entries, and precedence-based conflict handling must use the resolved precedence score after hard safety rules and scope resolution.

### 7.6 Publication Model

A publication creates an immutable **Config Snapshot** containing:

* API Ontology revision id
* Memory Ontology revision id
* Policy Profile revision id
* hash/checksum
* environment
* scope
* tenant_id nullable
* published timestamp
* publisher
* release notes

Every memory decision must store `config_snapshot_id`.

### 7.7 Validation

Before publication, the system must validate:

* schema validity
* enum validity
* reference integrity
* candidate memory type existence
* extraction strategy validity
* sensitivity ceiling compatibility
* conflict strategy compatibility with cardinality
* policy threshold range validity

### 7.8 Simulation

Operators must be able to run a dry-run simulation on sample or historical events and see:

* old decision
* new decision
* changed reason codes
* changed memory candidates
* expected write delta
* expected block delta

### 7.9 Rollback

Rollback must be a first-class operation:

* select prior published snapshot
* activate it without code deploy
* invalidate runtime cache
* apply only to future events
* keep audit trace of the rollback action

---

## 8. API Ontology Registry Specification

### 8.1 Purpose

The API Ontology Registry translates an API event into semantic meaning.

It answers:

* What kind of event is this?
* Is this event likely to create memory?
* What memory types are eligible?
* Which extractor profile should run?
* Which dedup and conflict hints apply?

### 8.2 Required Fields

Each API ontology entry shall include:

* `api_name`
* `enabled`
* `capability_family`
* `method_semantics`
* `domain`
* `description`
* `candidate_memory_types`
* `default_action`
* `repeat_policy`
* `sensitivity_hint`
* `source_trust`
* `source_precedence_key`
* `extractors`
* `relation_templates`
* `dedup_strategy_hint`
* `conflict_strategy_hint`
* `tenant_override_allowed`
* `notes`

### 8.3 Capability Families

At minimum, v1 supports:

* `PROFILE_WRITE`
* `PREFERENCE_SET`
* `RELATION_WRITE`
* `ENTITY_UPSERT`
* `CONTENT_READ`
* `SEARCH_READ`
* `DELETE_FORGET`
* `UNKNOWN`

### 8.4 Default Actions

Supported default actions:

* `BLOCK`
* `OBSERVE`
* `SESSION`
* `UPSERT`
* `FORGET`

### 8.5 Example: API Ontology Entry

```yaml
api_name: profile.updateAddress
enabled: true
capability_family: PROFILE_WRITE
method_semantics: WRITE
domain: profile
description: User explicitly updates their primary address
candidate_memory_types:
  - profile.primary_address
default_action: UPSERT
repeat_policy: BYPASS
sensitivity_hint: S2_PERSONAL
source_trust: 100
source_precedence_key: explicit_user_write
extractors:
  - address_parser
relation_templates:
  - USER_HAS_PRIMARY_ADDRESS
dedup_strategy_hint: EXACT_SLOT
conflict_strategy_hint: SUPERSEDE_BY_PRECEDENCE
tenant_override_allowed: true
notes: Explicit user write. Should bypass frequency gate.
```

### 8.6 Example: Low-Trust Read API

```yaml
api_name: search.webSearch
enabled: true
capability_family: SEARCH_READ
method_semantics: READ
domain: search
description: General web search request
candidate_memory_types:
  - interest.topic
default_action: OBSERVE
repeat_policy: REQUIRED
sensitivity_hint: S1_INTERNAL
source_trust: 30
source_precedence_key: weak_free_text_inference
extractors:
  - topic_extractor
relation_templates: []
dedup_strategy_hint: TOPIC_SCORE
conflict_strategy_hint: NO_DIRECT_CONFLICT
tenant_override_allowed: true
notes: Never persist on one-off events.
```

---

## 9. Memory Ontology Specification

### 9.1 Purpose

The Memory Ontology defines what memories are valid and how each memory type behaves.

It answers:

* What is this memory?
* Can there be one active value or many?
* How do we identify duplicates?
* How do we resolve conflicts?
* What sensitivity is allowed?
* How do we embed it?
* How do we retrieve it?

### 9.2 Required Fields

Each memory ontology entry shall include:

* `memory_type`
* `enabled`
* `memory_class`
* `subject_type`
* `object_type` or `value_type`
* `cardinality`
* `identity_strategy`
* `merge_strategy`
* `conflict_strategy`
* `allowed_sensitivity`
* `embed_mode`
* `default_ttl_days`
* `retrieval_mode`
* `importance_default`
* `tenant_override_allowed`
* `notes`

### 9.3 Memory Classes

v1 supports:

* `fact`
* `relation`
* `interest`
* `preference`

### 9.4 Cardinality Modes

v1 supports:

* `ONE_ACTIVE`
* `MANY_UNIQUE_BY_OBJECT`
* `MANY_SCORED`
* `MANY_VERSIONED`

### 9.5 Example: Primary Address

```yaml
memory_type: profile.primary_address
enabled: true
memory_class: fact
subject_type: User
object_type: Address
cardinality: ONE_ACTIVE
identity_strategy: user_id + slot(primary)
merge_strategy: MERGE_ATTRIBUTES_WHEN_EQUAL
conflict_strategy: SUPERSEDE_BY_PRECEDENCE
allowed_sensitivity: S2_PERSONAL
embed_mode: COARSE_SUMMARY_ONLY
default_ttl_days: null
retrieval_mode: EXACT_THEN_VECTOR
importance_default: 0.95
tenant_override_allowed: true
notes: Only one active primary address may exist.
```

### 9.6 Example: Customer Relationship

```yaml
memory_type: relationship.customer
enabled: true
memory_class: relation
subject_type: User
object_type: Customer
cardinality: MANY_UNIQUE_BY_OBJECT
identity_strategy: user_id + canonical_customer_id
merge_strategy: EVIDENCE_MERGE
conflict_strategy: DEDUP_BY_CANONICAL_OBJECT
allowed_sensitivity: S2_PERSONAL
embed_mode: SUMMARY
default_ttl_days: null
retrieval_mode: RELATION_THEN_VECTOR
importance_default: 0.85
tenant_override_allowed: true
notes: Multiple customers allowed, duplicates prohibited.
```

### 9.7 Example: Topic Interest

```yaml
memory_type: interest.topic
enabled: true
memory_class: interest
subject_type: User
object_type: Topic
cardinality: MANY_SCORED
identity_strategy: user_id + canonical_topic_id
merge_strategy: REINFORCE_SCORE
conflict_strategy: NO_DIRECT_CONFLICT
allowed_sensitivity: S1_INTERNAL
embed_mode: SUMMARY
default_ttl_days: 180
retrieval_mode: VECTOR_PLUS_FILTER
importance_default: 0.60
tenant_override_allowed: true
notes: Created only after repeat threshold is satisfied.
```

---

## 10. Policy Profile Specification

This is the missing piece that becomes essential once humans must control frequency, sensitivity, and conflict logic.

### 10.1 Purpose

A Policy Profile is a versioned ruleset consumed by the Memory Policy Layer.

API Ontology entries resolve their conflict precedence through the Policy Profile `source_precedence` table, using `source_precedence_key` as the binding.

It defines:

* frequency weights
* repeat thresholds
* burst penalties
* sensitivity classification policy
* precedence scores by source
* typo-correction windows
* forget behavior
* embedding redaction policy

### 10.2 Required Policy Sections

* `frequency`
* `sensitivity`
* `source_precedence`
* `conflict_windows`
* `embedding_rules`
* `forget_rules`

### 10.3 Example: Policy Profile

```yaml
profile_name: default-v1
frequency:
  half_life_days: 14
  weights:
    decayed_weight: 0.45
    unique_sessions_30d: 0.25
    unique_days_30d: 0.20
    source_diversity_30d: 0.10
  thresholds:
    persist: 0.70
    observe: 0.40
  burst_penalty:
    enabled: true
    penalty_value: 0.25
    same_session_ratio_threshold: 0.80
sensitivity:
  hard_block_levels:
    - S4_RESTRICTED
    - S3_CONFIDENTIAL
  memory_type_allow_ceiling:
    interest.topic: S1_INTERNAL
    profile.primary_address: S2_PERSONAL
    relationship.customer: S2_PERSONAL
source_precedence:
  explicit_user_write: 100
  system_of_record_sync: 90
  structured_business_write: 80
  repeated_behavioral_signal: 50
  weak_free_text_inference: 30
conflict_windows:
  typo_correction_minutes: 5
embedding_rules:
  raw_sensitive_embedding_allowed: false
  redact_address_detail: true
forget_rules:
  tombstone_on_delete: true
  remove_from_retrieval: true
```

---

## 11. Memory Policy Layer Specification

### 11.1 Inputs

The Policy Layer consumes:

* normalized API event
* active config snapshot
* prior counters
* optional prior memory lookup
* tenant context

### 11.2 Subcomponents

* **Event Normalizer**
* **Candidate Extractor**
* **Sensitivity Evaluator**
* **Frequency Analyzer**
* **Decision Engine**

### 11.3 Output

The Policy Layer must output a decision envelope:

```json
{
  "config_snapshot_id": "cfgsnap_2026_04_09_001",
  "event_id": "evt_001",
  "action": "UPSERT",
  "reason_codes": [
    "API_DEFAULT_UPSERT",
    "SENSITIVITY_ALLOWED",
    "REPEAT_BYPASSED_FOR_EXPLICIT_WRITE"
  ],
  "candidates": [
    {
      "memory_type": "profile.primary_address",
      "confidence": 0.98,
      "sensitivity": "S2_PERSONAL"
    }
  ]
}
```

### 11.4 Frequency Calculation

Frequency must be calculated by **semantic signal key**, not raw API count.

Example signal keys:

* `u123:interest.topic:real_estate_tax`
* `u123:relationship.customer:customer_abc`
* `u123:profile.primary_address:primary`

Recommended v1 score:

```text
repeat_score =
  0.45 * norm(decayed_weight)
+ 0.25 * norm(unique_sessions_30d)
+ 0.20 * norm(unique_days_30d)
+ 0.10 * norm(source_diversity_30d)
- burst_penalty
```

This formula is not hardcoded forever. Its weights and thresholds must come from the active Policy Profile.

### 11.5 Sensitivity Calculation

Effective sensitivity must be:

```text
effective_sensitivity = max(
  api_ontology.sensitivity_hint,
  extracted_field_tags,
  classifier_result,
  tenant_override
)
```

### 11.6 Hard Rules

The Policy Layer must enforce:

* `S4_RESTRICTED` => always `BLOCK`
* `S3_CONFIDENTIAL` => `BLOCK` in v1 unless an explicit future product decision changes this
* explicit delete/forget APIs => always `FORGET`
* unknown write APIs => never long-term persist until classified
* unknown read/search APIs => at most `OBSERVE`

---

## 12. Conflict, Duplicate, and Supersession Rules

This section directly addresses the earlier product concern.

### 12.1 Design Principle

Deduplication and conflict resolution must be **memory-type-specific**, not universal.

When a rule uses precedence to choose between competing values, the runtime must compare the precedence score resolved from the API Ontology `source_precedence_key` binding rather than the raw trust hint.

### 12.2 Resolution Modes

* `DUPLICATE`
* `MERGE`
* `SUPERSEDE`
* `CONFLICT`
* `REJECT`

### 12.3 Standard Rules

1. Same identity key + same normalized value
   => `DUPLICATE`

2. Same identity key + new attributes only
   => `MERGE`

3. `ONE_ACTIVE` memory + different value + higher precedence
   => `SUPERSEDE`

4. Same slot + incompatible values + similar precedence
   => `CONFLICT`

5. `MANY_UNIQUE_BY_OBJECT` + same canonical object
   => `DUPLICATE` with evidence merge

6. `MANY_SCORED` interest type
   => reinforce score, not duplicate

### 12.4 Operator-Tunable Inputs

Humans must be able to configure:

* precedence table
* alias confidence threshold
* typo correction window
* canonicalization rules by field type
* conflict escalation threshold
* tenant-specific stricter rules

### 12.5 Example: Address Update

* Old memory: primary address = A
* New event: explicit update to primary address = B
* Memory type: `ONE_ACTIVE`
* Source precedence: explicit user write = high
  Result: A becomes `superseded`, B becomes `active`

### 12.6 Example: Customer Alias Merge

* Event 1: `ABC Corp`
* Event 2: `ABC Corporation`
* Shared anchor: same verified domain
  Result: same canonical customer entity, one active relation, evidence merged

---

## 13. Memory Engine Specification

### 13.1 Responsibilities

The Memory Engine shall:

* canonicalize values
* resolve entities
* deduplicate candidates
* resolve conflicts
* version memories
* persist memory/evidence/relations
* create embeddings
* retrieve relevant memories
* forget or tombstone memories

### 13.2 Storage Principle

The system shall store:

* **facts and preferences** as structured records
* **relations** as structured edges
* **evidence** as immutable event references
* **embeddings** as retrieval indexes in PostgreSQL via pgvector

### 13.3 Retrieval Strategy

The retrieval planner must use:

1. exact slot lookup
2. relation lookup
3. vector lookup
4. reranking

### 13.4 Reranking

Suggested score:

```text
final_score =
  0.45 * semantic_relevance
+ 0.25 * confidence
+ 0.20 * importance
+ 0.10 * recency
```

`ONE_ACTIVE` exact slot matches should override generic ranking.

---

## 14. PostgreSQL Data Model

### 14.1 Database Schemas

Use separate logical schemas:

* `control`
* `runtime`
* `ops`

### 14.2 Control Schema Tables

`control.config_documents`

* id
* kind (`api_ontology`, `memory_ontology`, `policy_profile`)
* scope
* tenant_id nullable
* version
* status
* base_version nullable
* definition_jsonb
* checksum
* created_by
* approved_by nullable
* published_by nullable
* created_at
* approved_at nullable
* published_at nullable

`control.config_publications`

* id
* environment
* scope
* tenant_id nullable
* api_ontology_document_id
* memory_ontology_document_id
* policy_profile_document_id
* snapshot_hash
* is_active
* published_by
* published_at
* release_notes
* rollback_of nullable

`control.validation_results`

* id
* config_document_id
* severity
* path
* code
* message
* created_at

`control.audit_log`

* id
* actor
* action
* target_kind
* target_id
* metadata_jsonb
* created_at

### 14.3 Runtime Schema Tables

`runtime.api_events`

* event_id
* tenant_id
* user_id
* session_id
* api_name
* capability_family
* request_summary
* response_summary
* structured_fields_jsonb
* status
* occurred_at

`runtime.signal_counters`

* signal_key
* tenant_id
* user_id
* memory_type
* canonical_object_key
* decayed_weight
* unique_sessions_30d
* unique_days_30d
* source_diversity_30d
* same_session_burst_ratio
* last_seen_at

`runtime.entities`

* entity_id
* tenant_id
* entity_type
* canonical_key
* attributes_jsonb
* created_at
* updated_at

`runtime.entity_aliases`

* id
* entity_id
* alias
* alias_type
* confidence
* created_at

`runtime.memories`

* memory_id
* tenant_id
* user_id
* memory_type
* subject_entity_id
* object_entity_id nullable
* value_jsonb
* canonical_key
* state
* confidence
* importance
* sensitivity
* embedding vector nullable
* valid_from
* valid_to nullable
* supersedes nullable
* config_snapshot_id
* created_at
* updated_at

`runtime.relations`

* relation_id
* tenant_id
* subject_entity_id
* relation_type
* object_entity_id
* state
* strength
* evidence_count
* config_snapshot_id
* created_at
* updated_at

`runtime.evidence`

* evidence_id
* linked_record_type
* linked_record_id
* source_event_id
* api_name
* source_trust
* extraction_method
* config_snapshot_id
* observed_at

### 14.4 Ops Schema Tables

`ops.jobs`

* job_id
* job_type
* payload_jsonb
* status
* attempts
* next_run_at
* created_at

`ops.metrics_rollups`

* metric_name
* bucket_start
* bucket_end
* labels_jsonb
* value

---

## 15. Backend Specification (Python + FastAPI)

### 15.1 Services

There shall be two Python services sharing the same codebase:

* **API service**
* **Worker service**

### 15.2 API Service Responsibilities

* admin APIs for control plane
* event ingestion API
* retrieval API
* memory browser API
* simulation API
* publish/rollback API

### 15.3 Worker Responsibilities

* asynchronous event processing
* embedding generation
* conflict resolution jobs
* replay jobs
* cleanup/TTL jobs

### 15.4 Core Endpoint Groups

Admin:

* `GET /v1/control/api-ontology`
* `POST /v1/control/api-ontology`
* `GET /v1/control/memory-ontology`
* `POST /v1/control/memory-ontology`
* `GET /v1/control/policy-profiles`
* `POST /v1/control/policy-profiles`
* `POST /v1/control/validate`
* `POST /v1/control/simulate`
* `POST /v1/control/publish`
* `POST /v1/control/rollback`

Runtime:

* `POST /v1/events/ingest`
* `POST /v1/memory/query`
* `POST /v1/memory/forget`
* `GET /v1/memory/users/{user_id}`
* `GET /v1/memory/users/{user_id}/timeline`

### 15.5 Roles

At minimum:

* `viewer`
* `editor`
* `approver`
* `operator`
* `admin`

`editor` cannot publish to production without `approver` or `admin`.

---

## 16. Frontend Specification (Next.js + Tailwind CSS)

### 16.1 Purpose

The frontend is an **operator console**, not an end-user app.

### 16.2 Required Pages

* API Ontology list
* API Ontology editor
* Memory Ontology list
* Memory Ontology editor
* Policy Profile editor
* Validation results
* Simulation runner
* Publication history
* Rollback page
* Decision explorer
* User memory browser
* Audit log viewer

### 16.3 Required UX Features

* schema-driven forms
* raw YAML/JSON editor
* diff viewer between revisions
* publish confirmation modal
* rollback confirmation modal
* per-tenant override toggle
* sample-event simulator
* reason-code viewer
* filter by scope, environment, tenant, and status

### 16.4 UI Design Direction

Use Tailwind CSS for a dense admin interface with clear states for:

* draft
* validated
* approved
* published
* archived
* overridden
* blocked
* conflicted

---

## 17. Docker Compose Topology

### 17.1 Required Services

* `postgres`
* `api`
* `worker`
* `web`

### 17.2 Required Volumes

* `postgres_data`
* optional local file volume for logs or exported configs

### 17.3 Required Networks

* one internal application network is enough for v1

### 17.4 Service Responsibilities

* `postgres`: durable state for config and runtime memory
* `api`: FastAPI HTTP service
* `worker`: async background processing
* `web`: Next.js admin console

### 17.5 Startup Rules

* `postgres` must be healthy before `api` and `worker`
* database migrations must run before application traffic is served
* `web` should point to the published API URL
* all services must read environment variables from a shared Compose environment source

### 17.6 One-Shot Operations

The following operational flows must work through one Compose project:

* first boot
* migration
* restart
* publish config
* rollback config
* rebuild API
* rebuild web

---

## 18. Example Configuration Documents

### 18.1 API Ontology: CRM Deal Creation

```yaml
api_name: crm.createDeal
enabled: true
capability_family: RELATION_WRITE
method_semantics: WRITE
domain: crm
description: Creates a business deal with a customer
candidate_memory_types:
  - relationship.customer
default_action: UPSERT
repeat_policy: BYPASS
sensitivity_hint: S2_PERSONAL
source_trust: 90
extractors:
  - customer_parser
relation_templates:
  - USER_WORKS_WITH_CUSTOMER
dedup_strategy_hint: ENTITY_RELATION
conflict_strategy_hint: DEDUP_BY_CANONICAL_OBJECT
tenant_override_allowed: true
notes: Strong write signal.
```

### 18.2 Memory Ontology: Output Language Preference

```yaml
memory_type: preference.output_language
enabled: true
memory_class: preference
subject_type: User
value_type: enum
cardinality: ONE_ACTIVE
identity_strategy: user_id + slot(output_language)
merge_strategy: REPLACE
conflict_strategy: SUPERSEDE_BY_PRECEDENCE
allowed_sensitivity: S1_INTERNAL
embed_mode: SUMMARY
default_ttl_days: null
retrieval_mode: EXACT
importance_default: 0.90
tenant_override_allowed: true
notes: Explicit user preference only.
```

### 18.3 Tenant Override: Disable Search-Derived Interest Memory

```yaml
scope: tenant
tenant_id: tenant_finreg
overrides:
  api_name: search.webSearch
  default_action: OBSERVE
  max_persist_action: OBSERVE
  notes: Regulatory tenant does not allow persistence from search behavior.
```

### 18.4 Tenant Override: Raise Topic Repeat Threshold

```yaml
scope: tenant
tenant_id: tenant_enterprise_a
overrides:
  policy_profile:
    frequency:
      thresholds:
        persist: 0.82
```

---

## 19. Worked End-to-End Examples

### 19.1 Explicit Address Update

Event:

```json
{
  "api_name": "profile.updateAddress",
  "structured_fields": {
    "address": "123 Seongsu-ro, Seongdong-gu, Seoul"
  }
}
```

Flow:

* API ontology maps event to `PROFILE_WRITE`
* candidate memory type is `profile.primary_address`
* repeat gate is bypassed
* sensitivity is `S2_PERSONAL`
* memory ontology says `ONE_ACTIVE`
* existing active address is superseded
* new address becomes active
* embedding stores only a coarse summary

### 19.2 Repeated Topic Interest

Events:

* the user opens four real-estate-tax documents over three weeks across four sessions

Flow:

* API ontology maps reads to `interest.topic`
* topic extractor emits `real_estate_tax`
* repeat score crosses threshold
* sensitivity remains within `S1_INTERNAL`
* Memory Engine upserts `interest.topic`
* score is reinforced on future matching events

### 19.3 Customer Alias Merge

Events:

* `crm.createDeal(customer="ABC Corp", domain="abc.com")`
* `crm.createDeal(customer="ABC Corporation", domain="abc.com")`

Flow:

* both events generate `relationship.customer`
* entity resolver canonicalizes the customer using domain anchor
* relation deduplicates
* evidence count increases
* aliases are attached to one canonical customer entity

### 19.4 Manual Operator Change

Operator action:

* sets `search.webSearch` to `OBSERVE only` for one tenant
* publishes tenant-scoped snapshot

Result:

* no backend redeploy
* future events for that tenant stop creating topic memories from search
* other tenants remain unchanged

### 19.5 Rollback

Operator action:

* bad policy profile causes too many topic memories
* operator rolls back to prior snapshot

Result:

* new events use prior thresholds
* historical data remains auditable
* decision logs show the old and new `config_snapshot_id`

---

## 20. Acceptance Criteria

1. A human operator can create and edit API Ontology, Memory Ontology, and Policy Profile documents from the admin UI.
2. A human operator can import and export those documents as YAML or JSON.
3. Invalid documents cannot be published.
4. Every publication creates an immutable config snapshot.
5. Every memory decision stores the config snapshot used.
6. Publishing a new snapshot changes runtime behavior for new events without backend redeploy.
7. Rolling back to a prior snapshot changes runtime behavior for new events without backend redeploy.
8. Tenant overrides affect only the targeted tenant.
9. Hard safety rules cannot be bypassed by tenant or operator config.
10. `profile.updateAddress` supersedes the prior active address.
11. repeated `docs.openDocument` events can create `interest.topic` only after the configured threshold is met.
12. `search.webSearch` one-off activity does not create long-term memory under default policy.
13. duplicate customer aliases resolve to one canonical relation when anchor confidence is sufficient.
14. all persisted memories are traceable to evidence records.
15. deleted memories no longer appear in retrieval results.

---

## 21. Observability and Audit

The platform must emit:

* decision counts by action
* memory creation counts by memory type
* blocked counts by sensitivity level
* repeat score distributions
* duplicate/merge/supersede/conflict counts
* config validation failures
* publication and rollback events
* retrieval hit rate by memory type
* tenant override usage

Every admin action must be audit logged with:

* actor
* role
* document kind
* document version
* action
* timestamp
* before/after diff reference

---

## 22. Security Rules

* `S4_RESTRICTED` content must never be persisted.
* `S3_CONFIDENTIAL` content is blocked in v1 by default.
* S2+ structured values must be stored in protected encrypted columns, with only coarse metadata and canonical keys retained in cleartext.
* raw sensitive strings must not be embedded.
* embeddings for sensitive memory types must use coarse summaries or be disabled.
* tenant isolation must be enforced throughout config and memory access.
* operator actions must require authenticated and authorized roles.

---

## 23. Final Design Decision

The final v1 design is:

**A human-configurable memory platform where API Ontology, Memory Ontology, and Policy Profiles are versioned data in PostgreSQL; operators manage them through a Next.js control plane; FastAPI executes them at runtime; PostgreSQL stores both structured memory and vector memory; and Docker Compose runs the entire stack as one deployable application.**

---

## Assumptions

* The product needs a real operator control plane, not just internal developer-only configs.
* API events can be normalized into structured fields before policy evaluation.
* Per-tenant behavior differences are important enough to justify override support.
* PostgreSQL is acceptable as the single durable store for config, memory, and vectors.
* Human operators are trusted to tune policy, but not to bypass non-overridable safety rules.

---

## Key Checks

* The design now explicitly treats ontology and policy as **human-authored runtime configuration**.
* The earlier frequency and sensitivity concerns are solved by introducing a **versioned Policy Profile**.
* Deduplication and conflict resolution are explicitly **memory-type-specific**.
* Manual edits do not require backend redeploy because publication creates a new runtime snapshot.
* The stack is aligned with the requested technologies and current official versions. ([PostgreSQL][1])

---

## Risks

* Human-edited ontology can become inconsistent without strong validation and simulation.
* Tenant overrides can create policy sprawl if not governed tightly.
* Alias resolution can still merge unrelated entities if anchors are weak.
* Too many manual knobs can make policy hard to reason about unless defaults remain strong.
* PostgreSQL-only storage is a good v1 simplification, but very large embedding workloads may require later tuning or architecture changes.

---

## Confidence

0.96

---

## Verdict

This is a strong v1 product spec. The key improvement is that memory behavior is now explicitly **operator-controlled, versioned, auditable, and rollback-safe**, instead of being hidden inside code.

[1]: https://www.postgresql.org/ "https://www.postgresql.org/"
[2]: https://github.com/pgvector/pgvector "https://github.com/pgvector/pgvector"
[3]: https://docs.docker.com/compose/ "https://docs.docker.com/compose/"
[4]: https://fastapi.tiangolo.com/advanced/generate-clients/ "https://fastapi.tiangolo.com/advanced/generate-clients/"
