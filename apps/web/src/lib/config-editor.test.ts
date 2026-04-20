import test from "node:test";
import assert from "node:assert/strict";
import type { APIOntologyPackage, ConfigDocument } from "./api/types";
import {
  hasConfigDraftChanges,
  hasPackageDraftChanges,
  parseApiOntologyPackage,
  serializeApiOntologyPackage,
  serializeDocumentSource,
  sourceLineCount,
} from "./config-editor.ts";

const document: ConfigDocument = {
  id: "cfgdoc_test",
  kind: "api-ontology",
  name: "Core API Ontology",
  version: 3,
  status: "draft",
  tenant: "all",
  scope: "global",
  environment: "dev",
  updatedAt: "2026-04-16T00:00:00.000Z",
  summary: "Summary",
  yaml: "document_name: Core API Ontology\nentries: []\n",
  definitionJson: {
    document_name: "Core API Ontology",
    modules: [],
    workflows: [],
  },
};

const packageDraft: APIOntologyPackage = {
  document_name: "Core API Ontology",
  modules: [
    {
      module_key: "orders.lifecycle",
      title: "Orders Lifecycle",
      description: "Checkout lifecycle APIs",
      entries: [
        {
          entry_id: "order.register",
          module_key: "orders.lifecycle",
          api_name: "order.register",
          enabled: true,
          capability_family: "ENTITY_UPSERT",
          method_semantics: "WRITE",
          domain: "orders",
          description: "Register an order",
          candidate_memory_types: ["interest.topic"],
          default_action: "UPSERT",
          repeat_policy: "BYPASS",
          sensitivity_hint: "S1_INTERNAL",
          source_trust: 80,
          source_precedence_key: "structured_business_write",
          extractors: ["topic_extractor"],
          relation_templates: [],
          dedup_strategy_hint: "TOPIC_SCORE",
          conflict_strategy_hint: "NO_DIRECT_CONFLICT",
          tenant_override_allowed: true,
          event_match: {
            source_system: "order_service",
            http_method: "POST",
            route_template: "/v1/orders",
          },
          request_field_selectors: ["$.topic"],
          response_field_selectors: [],
          normalization_rules: { primary_fact_source: "request_only" },
          evidence_capture_policy: { request: "summary_only", response: "summary_only" },
          llm_usage_mode: "DISABLED",
          prompt_template_key: null,
          llm_allowed_field_paths: [],
          llm_blocked_field_paths: [],
          notes: "",
        },
      ],
    },
  ],
  workflows: [
    {
      workflow_key: "order_checkout",
      title: "Order checkout",
      description: "Links order and payment APIs into one workflow.",
      participant_entry_ids: ["order.register"],
      relationship_edges: [],
      intent_memory_type: "intent.user_goal",
      default_intent_summary: "User is trying to place an order and complete payment.",
      intent_rules: [
        {
          observed_entry_ids: ["order.register"],
          summary: "User is trying to place an order and complete payment.",
        },
      ],
    },
  ],
};

test("serializeDocumentSource returns YAML for yaml mode", () => {
  assert.equal(serializeDocumentSource(document, "yaml"), document.yaml);
});

test("serializeDocumentSource pretty prints JSON for json mode", () => {
  assert.equal(
    serializeDocumentSource(document, "json"),
    JSON.stringify(document.definitionJson ?? {}, null, 2),
  );
});

test("hasConfigDraftChanges stays false for identical editor metadata and source", () => {
  assert.equal(
    hasConfigDraftChanges({
      active: document,
      editor: { ...document },
      sourceText: document.yaml,
      sourceFormat: "yaml",
    }),
    false,
  );
});

test("hasConfigDraftChanges detects metadata edits", () => {
  assert.equal(
    hasConfigDraftChanges({
      active: document,
      editor: { ...document, name: "Changed name" },
      sourceText: document.yaml,
      sourceFormat: "yaml",
    }),
    true,
  );
});

test("hasConfigDraftChanges detects source edits in the active format", () => {
  assert.equal(
    hasConfigDraftChanges({
      active: document,
      editor: { ...document },
      sourceText: `${document.yaml}notes: changed\n`,
      sourceFormat: "yaml",
    }),
    true,
  );
});

test("sourceLineCount counts logical lines", () => {
  assert.equal(sourceLineCount("alpha\nbeta\ngamma"), 3);
  assert.equal(sourceLineCount(""), 0);
});

test("parseApiOntologyPackage lifts legacy entries into a package module", () => {
  const parsed = parseApiOntologyPackage({
    document_name: "Legacy API Ontology",
    entries: [
      {
        api_name: "order.register",
        enabled: true,
        capability_family: "ENTITY_UPSERT",
        method_semantics: "WRITE",
        domain: "orders",
        description: "Register an order",
        candidate_memory_types: ["interest.topic"],
        default_action: "UPSERT",
        repeat_policy: "BYPASS",
        sensitivity_hint: "S1_INTERNAL",
        source_trust: 80,
        source_precedence_key: "structured_business_write",
        extractors: ["topic_extractor"],
        relation_templates: [],
        dedup_strategy_hint: "TOPIC_SCORE",
        conflict_strategy_hint: "NO_DIRECT_CONFLICT",
        tenant_override_allowed: true,
        event_match: {
          source_system: "order_service",
          http_method: "POST",
          route_template: "/v1/orders",
        },
        request_field_selectors: ["$.topic"],
        response_field_selectors: [],
        normalization_rules: { primary_fact_source: "request_only" },
        evidence_capture_policy: { request: "summary_only", response: "summary_only" },
        llm_usage_mode: "DISABLED",
        llm_allowed_field_paths: [],
        llm_blocked_field_paths: [],
      },
    ],
  });
  assert.equal(parsed?.modules[0]?.module_key, "legacy.default");
  assert.equal(parsed?.modules[0]?.entries[0]?.entry_id, "order.register");
});

test("serializeApiOntologyPackage pretty prints package JSON", () => {
  assert.equal(serializeApiOntologyPackage(packageDraft), JSON.stringify(packageDraft, null, 2));
});

test("hasPackageDraftChanges detects workflow edits", () => {
  assert.equal(
    hasPackageDraftChanges({
      active: packageDraft,
      editor: {
        ...packageDraft,
        workflows: packageDraft.workflows.map((workflow) =>
          workflow.workflow_key === "order_checkout"
            ? { ...workflow, default_intent_summary: "Changed summary" }
            : workflow,
        ),
      },
    }),
    true,
  );
});
