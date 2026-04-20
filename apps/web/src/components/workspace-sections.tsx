"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useConsoleSession } from "@/components/console-shell";
import { client } from "@/lib/api/client";
import type {
  APIOntologyEntry,
  APIOntologyModule,
  APIOntologyPackage,
  APIOntologyWorkflowDefinition,
  ConfigDocument,
  ConfigKind,
  DecisionRecord,
  MemoryRecord,
  PublicationSnapshot,
  SimulationRun,
  ValidationRun,
} from "@/lib/api/types";
import {
  type EditorFormat,
  hasConfigDraftChanges,
  hasPackageDraftChanges,
  parseApiOntologyPackage,
  serializeApiOntologyPackage,
  serializeDocumentSource,
  sourceLineCount,
} from "@/lib/config-editor";
import { Badge, Button, Card, CodeBlock, ConsolePageHeader, EmptyState, Input, Label, Metric, Select, Section, Textarea, cx } from "@/components/ui";

function canEditConfig(role?: string) {
  return role === "editor" || role === "approver" || role === "operator" || role === "admin";
}

function canApprove(role?: string) {
  return role === "approver" || role === "admin";
}

function canRollback(role?: string) {
  return role === "operator" || role === "admin";
}

function canArchive(role?: string) {
  return role === "operator" || role === "admin";
}

function canPublish(role?: string) {
  return role === "approver" || role === "admin";
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : "Request failed";
}

function kindLabel(kind: ConfigKind) {
  return kindMeta[kind].title;
}

function joinItems(values: Array<string | null | undefined>) {
  return values.filter(Boolean).join(" · ");
}

function safeParseJson(value: string) {
  try {
    return JSON.parse(value) as Record<string, unknown>;
  } catch {
    return null;
  }
}

const kindMeta: Record<ConfigKind, { title: string; eyebrow: string; description: string }> = {
  "api-ontology": {
    title: "API Ontology",
    eyebrow: "Document routing and semantic action mapping",
    description: "Author the normalized action vocabulary that runtime evaluation consumes.",
  },
  "memory-ontology": {
    title: "Memory Ontology",
    eyebrow: "Memory types, supersession, and retrieval shape",
    description: "Define the memory types that can persist and how they replace each other.",
  },
  "policy-profile": {
    title: "Policy Profile",
    eyebrow: "Safety ceilings, thresholds, and overrides",
    description: "Tune hard safety rules and repeat thresholds without changing code.",
  },
};

const starterDefinitions: Record<ConfigKind, Record<string, unknown>> = {
  "api-ontology": {
    document_name: "Core API Ontology",
    modules: [
      {
        module_key: "orders.lifecycle",
        title: "Orders Lifecycle",
        description: "Core order lifecycle APIs that establish checkout intent.",
        entries: [
          {
            entry_id: "order.register",
            module_key: "orders.lifecycle",
            api_name: "order.register",
            enabled: true,
            capability_family: "ENTITY_UPSERT",
            method_semantics: "WRITE",
            domain: "orders",
            description: "Register a new order for checkout.",
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
          {
            entry_id: "order.get",
            module_key: "orders.lifecycle",
            api_name: "order.get",
            enabled: true,
            capability_family: "CONTENT_READ",
            method_semantics: "READ",
            domain: "orders",
            description: "Read an existing order after registration.",
            candidate_memory_types: ["interest.topic"],
            default_action: "OBSERVE",
            repeat_policy: "REQUIRED",
            sensitivity_hint: "S1_INTERNAL",
            source_trust: 30,
            source_precedence_key: "repeated_behavioral_signal",
            extractors: ["topic_extractor"],
            relation_templates: [],
            dedup_strategy_hint: "TOPIC_SCORE",
            conflict_strategy_hint: "NO_DIRECT_CONFLICT",
            tenant_override_allowed: true,
            event_match: {
              source_system: "order_service",
              http_method: "GET",
              route_template: "/v1/orders/{orderId}",
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
      {
        module_key: "orders.payment",
        title: "Orders Payment",
        description: "Payment APIs related to the checkout workflow.",
        entries: [
          {
            entry_id: "payment.charge",
            module_key: "orders.payment",
            api_name: "payment.charge",
            enabled: true,
            capability_family: "ENTITY_UPSERT",
            method_semantics: "WRITE",
            domain: "payments",
            description: "Capture payment for a registered order.",
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
              source_system: "payment_service",
              http_method: "POST",
              route_template: "/v1/payments/charge",
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
        description: "Connect order registration, follow-up read, and payment into one intent.",
        participant_entry_ids: ["order.register", "order.get", "payment.charge"],
        relationship_edges: [
          { from_entry_id: "order.register", to_entry_id: "order.get", edge_type: "READS_AFTER_WRITE" },
          { from_entry_id: "order.register", to_entry_id: "payment.charge", edge_type: "ENABLES" },
        ],
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
  },
  "memory-ontology": {
    document_name: "Core Memory Ontology",
    entries: [
      {
        memory_type: "profile.primary_address",
        enabled: true,
        memory_class: "fact",
        subject_type: "User",
        object_type: "Address",
        cardinality: "ONE_ACTIVE",
        identity_strategy: "user_id + slot(primary)",
        merge_strategy: "MERGE_ATTRIBUTES_WHEN_EQUAL",
        conflict_strategy: "SUPERSEDE_BY_PRECEDENCE",
        allowed_sensitivity: "S2_PERSONAL",
        embed_mode: "COARSE_SUMMARY_ONLY",
        default_ttl_days: null,
        retrieval_mode: "EXACT_THEN_VECTOR",
        importance_default: 0.95,
        tenant_override_allowed: true,
        notes: "",
      },
      {
        memory_type: "interest.topic",
        enabled: true,
        memory_class: "interest",
        subject_type: "User",
        object_type: "Topic",
        cardinality: "MANY_SCORED",
        identity_strategy: "user_id + canonical_topic_id",
        merge_strategy: "REINFORCE_SCORE",
        conflict_strategy: "NO_DIRECT_CONFLICT",
        allowed_sensitivity: "S1_INTERNAL",
        embed_mode: "SUMMARY",
        default_ttl_days: 180,
        retrieval_mode: "VECTOR_PLUS_FILTER",
        importance_default: 0.6,
        tenant_override_allowed: true,
        notes: "",
      },
      {
        memory_type: "relationship.customer",
        enabled: true,
        memory_class: "relation",
        subject_type: "User",
        object_type: "Customer",
        cardinality: "MANY_UNIQUE_BY_OBJECT",
        identity_strategy: "user_id + canonical_customer_id",
        merge_strategy: "EVIDENCE_MERGE",
        conflict_strategy: "DEDUP_BY_CANONICAL_OBJECT",
        allowed_sensitivity: "S2_PERSONAL",
        embed_mode: "DISABLED",
        default_ttl_days: null,
        retrieval_mode: "RELATION_THEN_VECTOR",
        importance_default: 0.7,
        tenant_override_allowed: true,
        notes: "",
      },
      {
        memory_type: "intent.user_goal",
        enabled: true,
        memory_class: "fact",
        subject_type: "User",
        value_type: "IntentSummary",
        cardinality: "ONE_ACTIVE",
        identity_strategy: "user_id + workflow_key",
        merge_strategy: "MERGE_ATTRIBUTES_WHEN_EQUAL",
        conflict_strategy: "SUPERSEDE_BY_PRECEDENCE",
        allowed_sensitivity: "S1_INTERNAL",
        embed_mode: "SUMMARY",
        default_ttl_days: null,
        retrieval_mode: "EXACT_THEN_VECTOR",
        importance_default: 0.85,
        tenant_override_allowed: true,
        notes: "",
      },
    ],
  },
  "policy-profile": {
    profile_name: "default-v1",
    frequency: {
      half_life_days: 14,
      weights: {
        decayed_weight: 0.45,
        unique_sessions_30d: 0.25,
        unique_days_30d: 0.2,
        source_diversity_30d: 0.1,
      },
      thresholds: { persist: 0.7, observe: 0.4 },
      burst_penalty: {
        enabled: true,
        penalty_value: 0.25,
        same_session_ratio_threshold: 0.8,
      },
    },
    sensitivity: {
      hard_block_levels: ["S4_RESTRICTED", "S3_CONFIDENTIAL"],
      memory_type_allow_ceiling: {
        "interest.topic": "S1_INTERNAL",
        "profile.primary_address": "S2_PERSONAL",
        "relationship.customer": "S2_PERSONAL",
        "intent.user_goal": "S1_INTERNAL",
      },
    },
    source_precedence: {
      explicit_user_write: 100,
      structured_business_write: 80,
      repeated_behavioral_signal: 50,
    },
    conflict_windows: { typo_correction_minutes: 5 },
    embedding_rules: { raw_sensitive_embedding_allowed: false, redact_address_detail: true },
    forget_rules: { tombstone_on_delete: true, remove_from_retrieval: true },
    model_inference: {
      enabled: true,
      explicit_write_bypass: true,
      hard_rule_bypass: true,
      require_policy_validation: true,
      low_confidence_threshold: 0.6,
      allow_low_confidence_persist: true,
      log_reasoning_summary: true,
      provider_gate: {
        default_provider: "ollama",
        rules: [
          {
            capability_families: ["SEARCH_READ", "CONTENT_READ"],
            llm_usage_modes: ["ASSIST", "REQUIRE"],
            memory_types: [],
            max_sensitivity: "S1_INTERNAL",
            provider_order: ["ollama", "openai"],
          },
        ],
      },
    },
  },
};

function starterName(kind: ConfigKind) {
  const definition = starterDefinitions[kind];
  return String(definition.document_name ?? definition.profile_name ?? kindLabel(kind));
}

function cloneStarterDefinition(kind: ConfigKind) {
  return JSON.parse(JSON.stringify(starterDefinitions[kind])) as Record<string, unknown>;
}

function cloneApiPackage(pkg: APIOntologyPackage) {
  return JSON.parse(JSON.stringify(pkg)) as APIOntologyPackage;
}

function parseCommaSeparated(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseLineSeparated(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinCommaSeparated(values: string[]) {
  return values.join(", ");
}

function joinLineSeparated(values: string[]) {
  return values.join("\n");
}

function defaultApiEntry(moduleKey: string, index: number): APIOntologyEntry {
  return {
    entry_id: `${moduleKey}.entry_${index + 1}`,
    module_key: moduleKey,
    api_name: "",
    enabled: true,
    capability_family: "ENTITY_UPSERT",
    method_semantics: "WRITE",
    domain: moduleKey.split(".")[0] ?? "domain",
    description: "",
    candidate_memory_types: [],
    default_action: "UPSERT",
    repeat_policy: "BYPASS",
    sensitivity_hint: "S1_INTERNAL",
    source_trust: 80,
    source_precedence_key: "structured_business_write",
    extractors: [],
    relation_templates: [],
    dedup_strategy_hint: "",
    conflict_strategy_hint: "",
    tenant_override_allowed: true,
    event_match: {
      source_system: "",
      http_method: "POST",
      route_template: "",
    },
    request_field_selectors: [],
    response_field_selectors: [],
    normalization_rules: {
      primary_fact_source: "request_only",
    },
    evidence_capture_policy: {
      request: "summary_only",
      response: "summary_only",
    },
    llm_usage_mode: "DISABLED",
    prompt_template_key: null,
    llm_allowed_field_paths: [],
    llm_blocked_field_paths: [],
    notes: "",
  };
}

function defaultApiModule(index: number): APIOntologyModule {
  const moduleKey = `module_${index + 1}`;
  return {
    module_key: moduleKey,
    title: `Module ${index + 1}`,
    description: "",
    entries: [defaultApiEntry(moduleKey, 0)],
  };
}

function defaultWorkflow(index: number, modules: APIOntologyModule[]): APIOntologyWorkflowDefinition {
  const firstEntryId = modules[0]?.entries[0]?.entry_id ?? "";
  return {
    workflow_key: `workflow_${index + 1}`,
    title: `Workflow ${index + 1}`,
    description: "",
    participant_entry_ids: firstEntryId ? [firstEntryId] : [],
    relationship_edges: [],
    intent_memory_type: "intent.user_goal",
    default_intent_summary: "",
    intent_rules: [],
  };
}

function resolveApiPackage(document: ConfigDocument | null) {
  return document?.apiOntologyPackage ?? parseApiOntologyPackage(document?.definitionJson ?? null);
}

function ApiOntologyPackageEditor({
  activePackage,
  packageDraft,
  onChangePackage,
}: {
  activePackage: APIOntologyPackage | null;
  packageDraft: APIOntologyPackage | null;
  onChangePackage: (nextPackage: APIOntologyPackage) => void;
}) {
  const [selectedModuleKey, setSelectedModuleKey] = useState("");
  const [selectedEntryId, setSelectedEntryId] = useState("");
  const [selectedWorkflowKey, setSelectedWorkflowKey] = useState("");

  const modules = packageDraft?.modules ?? [];
  const workflows = packageDraft?.workflows ?? [];
  const allEntries = useMemo(() => modules.flatMap((module) => module.entries), [modules]);
  const currentModule = modules.find((module) => module.module_key === selectedModuleKey) ?? modules[0] ?? null;
  const currentEntry = currentModule?.entries.find((entry) => entry.entry_id === selectedEntryId) ?? currentModule?.entries[0] ?? null;
  const currentWorkflow = workflows.find((workflow) => workflow.workflow_key === selectedWorkflowKey) ?? workflows[0] ?? null;
  const packageDirty = hasPackageDraftChanges({ active: activePackage, editor: packageDraft });

  useEffect(() => {
    if (!packageDraft) {
      setSelectedModuleKey("");
      setSelectedEntryId("");
      setSelectedWorkflowKey("");
      return;
    }
    const nextModuleKey = currentModule?.module_key ?? packageDraft.modules[0]?.module_key ?? "";
    if (nextModuleKey !== selectedModuleKey) {
      setSelectedModuleKey(nextModuleKey);
    }
    const nextEntryId = currentEntry?.entry_id ?? packageDraft.modules[0]?.entries[0]?.entry_id ?? "";
    if (nextEntryId !== selectedEntryId) {
      setSelectedEntryId(nextEntryId);
    }
    const nextWorkflowKey = currentWorkflow?.workflow_key ?? packageDraft.workflows[0]?.workflow_key ?? "";
    if (nextWorkflowKey !== selectedWorkflowKey) {
      setSelectedWorkflowKey(nextWorkflowKey);
    }
  }, [
    currentEntry,
    currentModule,
    currentWorkflow,
    packageDraft,
    selectedEntryId,
    selectedModuleKey,
    selectedWorkflowKey,
  ]);

  if (!packageDraft) {
    return (
      <Section eyebrow="Structured authoring" title="API package editor">
        <Card>
          <p className="text-sm text-slate-400">
            Structured authoring is available when the API ontology document contains JSON-backed package data.
          </p>
        </Card>
      </Section>
    );
  }

  const updatePackage = (recipe: (draft: APIOntologyPackage) => void) => {
    const nextPackage = cloneApiPackage(packageDraft);
    recipe(nextPackage);
    onChangePackage(nextPackage);
  };

  const replaceEntryId = (draft: APIOntologyPackage, previousId: string, nextId: string) => {
    for (const workflow of draft.workflows) {
      workflow.participant_entry_ids = workflow.participant_entry_ids.map((entryId) =>
        entryId === previousId ? nextId : entryId,
      );
      workflow.relationship_edges = workflow.relationship_edges.map((edge) => ({
        ...edge,
        from_entry_id: edge.from_entry_id === previousId ? nextId : edge.from_entry_id,
        to_entry_id: edge.to_entry_id === previousId ? nextId : edge.to_entry_id,
      }));
      workflow.intent_rules = workflow.intent_rules.map((rule) => ({
        ...rule,
        observed_entry_ids: rule.observed_entry_ids.map((entryId) => (entryId === previousId ? nextId : entryId)),
      }));
    }
  };

  const removeEntryReferences = (draft: APIOntologyPackage, entryId: string) => {
    for (const workflow of draft.workflows) {
      workflow.participant_entry_ids = workflow.participant_entry_ids.filter((participantId) => participantId !== entryId);
      workflow.relationship_edges = workflow.relationship_edges.filter(
        (edge) => edge.from_entry_id !== entryId && edge.to_entry_id !== entryId,
      );
      workflow.intent_rules = workflow.intent_rules
        .map((rule) => ({
          ...rule,
          observed_entry_ids: rule.observed_entry_ids.filter((observedEntryId) => observedEntryId !== entryId),
        }))
        .filter((rule) => rule.observed_entry_ids.length > 0);
    }
  };

  const addModule = () => {
    updatePackage((draft) => {
      const module = defaultApiModule(draft.modules.length);
      draft.modules.push(module);
      setSelectedModuleKey(module.module_key);
      setSelectedEntryId(module.entries[0]?.entry_id ?? "");
    });
  };

  const removeModule = () => {
    if (!currentModule) {
      return;
    }
    updatePackage((draft) => {
      const removing = draft.modules.find((module) => module.module_key === currentModule.module_key);
      if (!removing) {
        return;
      }
      for (const entry of removing.entries) {
        removeEntryReferences(draft, entry.entry_id);
      }
      draft.modules = draft.modules.filter((module) => module.module_key !== currentModule.module_key);
      const fallbackModule = draft.modules[0];
      setSelectedModuleKey(fallbackModule?.module_key ?? "");
      setSelectedEntryId(fallbackModule?.entries[0]?.entry_id ?? "");
    });
  };

  const addEntry = () => {
    if (!currentModule) {
      return;
    }
    updatePackage((draft) => {
      const module = draft.modules.find((item) => item.module_key === currentModule.module_key);
      if (!module) {
        return;
      }
      const entry = defaultApiEntry(module.module_key, module.entries.length);
      module.entries.push(entry);
      setSelectedModuleKey(module.module_key);
      setSelectedEntryId(entry.entry_id);
    });
  };

  const removeEntry = () => {
    if (!currentModule || !currentEntry) {
      return;
    }
    updatePackage((draft) => {
      const module = draft.modules.find((item) => item.module_key === currentModule.module_key);
      if (!module) {
        return;
      }
      module.entries = module.entries.filter((entry) => entry.entry_id !== currentEntry.entry_id);
      removeEntryReferences(draft, currentEntry.entry_id);
      const fallbackEntry = module.entries[0] ?? draft.modules[0]?.entries[0] ?? null;
      setSelectedEntryId(fallbackEntry?.entry_id ?? "");
      setSelectedModuleKey(fallbackEntry?.module_key ?? draft.modules[0]?.module_key ?? "");
    });
  };

  const addWorkflow = () => {
    updatePackage((draft) => {
      const workflow = defaultWorkflow(draft.workflows.length, draft.modules);
      draft.workflows.push(workflow);
      setSelectedWorkflowKey(workflow.workflow_key);
    });
  };

  const removeWorkflow = () => {
    if (!currentWorkflow) {
      return;
    }
    updatePackage((draft) => {
      draft.workflows = draft.workflows.filter((workflow) => workflow.workflow_key !== currentWorkflow.workflow_key);
      setSelectedWorkflowKey(draft.workflows[0]?.workflow_key ?? "");
    });
  };

  const updateModuleField = (field: keyof APIOntologyModule, value: string) => {
    if (!currentModule) {
      return;
    }
    updatePackage((draft) => {
      const module = draft.modules.find((item) => item.module_key === currentModule.module_key);
      if (!module) {
        return;
      }
      if (field === "module_key") {
        const previousKey = module.module_key;
        module.module_key = value;
        for (const entry of module.entries) {
          entry.module_key = value;
        }
        setSelectedModuleKey(value);
        if (currentEntry?.module_key === previousKey) {
          setSelectedEntryId(currentEntry.entry_id);
        }
      } else if (field === "title") {
        module.title = value;
      } else if (field === "description") {
        module.description = value;
      }
    });
  };

  const updateEntry = (recipe: (entry: APIOntologyEntry, draft: APIOntologyPackage) => void) => {
    if (!currentModule || !currentEntry) {
      return;
    }
    updatePackage((draft) => {
      const module = draft.modules.find((item) => item.module_key === currentModule.module_key);
      const entry = module?.entries.find((item) => item.entry_id === currentEntry.entry_id);
      if (!entry) {
        return;
      }
      recipe(entry, draft);
    });
  };

  const updateWorkflow = (recipe: (workflow: APIOntologyWorkflowDefinition) => void) => {
    if (!currentWorkflow) {
      return;
    }
    updatePackage((draft) => {
      const workflow = draft.workflows.find((item) => item.workflow_key === currentWorkflow.workflow_key);
      if (!workflow) {
        return;
      }
      recipe(workflow);
    });
  };

  const availableEntryIds = allEntries.map((entry) => entry.entry_id);
  const packageEntryCount = allEntries.length;
  const relationshipEdgeCount = workflows.reduce((count, workflow) => count + workflow.relationship_edges.length, 0);
  const activeFocusSummary = currentEntry
    ? joinItems([currentEntry.entry_id, currentEntry.event_match.http_method, currentEntry.event_match.route_template])
    : "Select an API entry to inspect the current editing lane.";

  return (
    <div className="space-y-4">
      <div className="panel space-y-5 p-5 sm:p-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="label">Structured authoring</div>
              <Badge tone={packageDirty ? "warning" : "success"}>
                {packageDirty ? "Structured draft changed" : "Structured draft synced"}
              </Badge>
            </div>
            <div className="space-y-2">
              <h3 className="text-2xl font-semibold tracking-tight text-white">Shape the ontology before you touch raw source.</h3>
              <p className="max-w-3xl text-sm leading-6 text-slate-300">
                Group APIs into stable modules, tune one entry at a time, and wire workflows only after the entry-level routing and memory behavior are clear.
              </p>
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Badge>{modules.length} modules</Badge>
            <Badge>{packageEntryCount} API entries</Badge>
            <Badge>{workflows.length} workflows</Badge>
            <Badge>{relationshipEdgeCount} edges</Badge>
          </div>
        </div>
        <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-[minmax(0,1.45fr)_repeat(3,minmax(0,1fr))]">
          <div className="panel-inset space-y-2 p-4 lg:col-span-2 2xl:col-span-1">
            <div className="label">Active focus</div>
            <div className="text-sm font-semibold text-white">
              {currentModule?.title || currentModule?.module_key || "No module selected"}
            </div>
            <p className="text-xs leading-5 text-slate-400">{activeFocusSummary}</p>
          </div>
          <div className="panel-inset space-y-2 p-4">
            <div className="label">Modules</div>
            <div className="text-2xl font-semibold text-white">{modules.length}</div>
            <p className="text-xs leading-5 text-slate-400">Families that organize the authoring surface.</p>
          </div>
          <div className="panel-inset space-y-2 p-4">
            <div className="label">Workflows</div>
            <div className="text-2xl font-semibold text-white">{workflows.length}</div>
            <p className="text-xs leading-5 text-slate-400">User-task definitions across related APIs.</p>
          </div>
          <div className="panel-inset space-y-2 p-4">
            <div className="label">Current workflow</div>
            <div className="text-sm font-semibold text-white">
              {currentWorkflow?.title || currentWorkflow?.workflow_key || "No workflow selected"}
            </div>
            <p className="text-xs leading-5 text-slate-400">
              {currentWorkflow
                ? `${currentWorkflow.participant_entry_ids.length} participants in focus`
                : "Choose a workflow to inspect intent rules and relationship edges."}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
        <div className="space-y-4">
          <div className="panel-muted space-y-4 p-4 sm:p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="label">Module map</div>
                <div className="mt-2 text-sm font-semibold text-white">Define coherent API families first.</div>
              </div>
              <Button variant="secondary" onClick={addModule}>
                Add module
              </Button>
            </div>
            <p className="text-xs leading-5 text-slate-400">
              Modules should stay stable enough that operators can scan the package map before dropping into entry-level tuning.
            </p>
            <div className="space-y-2">
              {modules.map((module) => (
                <button
                  key={module.module_key}
                  onClick={() => {
                    setSelectedModuleKey(module.module_key);
                    setSelectedEntryId(module.entries[0]?.entry_id ?? "");
                  }}
                  className={cx(
                    "w-full rounded-2xl border px-4 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--color-accent)]/35 active:translate-y-px",
                    currentModule?.module_key === module.module_key
                      ? "border-[color:var(--color-line-strong)] bg-[color:var(--color-card-accent)] shadow-sm"
                      : "border-[color:var(--color-line-subtle)] bg-[color:var(--color-card-inset)] hover:border-[color:var(--color-line)] hover:bg-white/5",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-white">{module.title || module.module_key}</div>
                      <div className="mt-1 break-words text-xs text-slate-400">
                        {joinItems([module.module_key, `${module.entries.length} API entries`])}
                      </div>
                    </div>
                    <Badge tone="accent">{module.entries.length}</Badge>
                  </div>
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={addEntry} disabled={!currentModule}>
                Add entry
              </Button>
              <Button variant="danger" onClick={removeModule} disabled={!currentModule}>
                Remove module
              </Button>
            </div>
            <div className="space-y-2 border-t border-[color:var(--color-line-subtle)] pt-4">
              <div className="label">Entries in selected module</div>
              {currentModule?.entries.map((entry) => (
                <button
                  key={entry.entry_id}
                  onClick={() => setSelectedEntryId(entry.entry_id)}
                  className={cx(
                    "w-full rounded-2xl border px-4 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--color-accent)]/35 active:translate-y-px",
                    currentEntry?.entry_id === entry.entry_id
                      ? "border-[color:var(--color-line-strong)] bg-[color:var(--color-card-accent)] shadow-sm"
                      : "border-[color:var(--color-line-subtle)] bg-[color:var(--color-card-inset)] hover:border-[color:var(--color-line)] hover:bg-white/5",
                  )}
                >
                  <div className="truncate font-medium text-white">{entry.api_name || entry.entry_id}</div>
                  <div className="mt-1 break-words text-xs text-slate-400">
                    {joinItems([entry.entry_id, entry.method_semantics, entry.event_match.http_method, entry.event_match.route_template])}
                  </div>
                </button>
              )) ?? <p className="text-sm text-slate-400">No entries in the selected module yet.</p>}
              <Button variant="danger" onClick={removeEntry} disabled={!currentEntry}>
                Remove entry
              </Button>
            </div>
          </div>

          <div className="panel-muted space-y-4 p-4 sm:p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="label">Workflow map</div>
                <div className="mt-2 text-sm font-semibold text-white">Connect related APIs into one user task.</div>
              </div>
              <Button variant="secondary" onClick={addWorkflow}>
                Add workflow
              </Button>
            </div>
            <p className="text-xs leading-5 text-slate-400">
              Workflows come after entry quality. Keep them as readable operator stories instead of raw graph maintenance.
            </p>
            <div className="space-y-2">
              {workflows.map((workflow) => (
                <button
                  key={workflow.workflow_key}
                  onClick={() => setSelectedWorkflowKey(workflow.workflow_key)}
                  className={cx(
                    "w-full rounded-2xl border px-4 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--color-accent)]/35 active:translate-y-px",
                    currentWorkflow?.workflow_key === workflow.workflow_key
                      ? "border-[color:var(--color-line-strong)] bg-[color:var(--color-card-accent)] shadow-sm"
                      : "border-[color:var(--color-line-subtle)] bg-[color:var(--color-card-inset)] hover:border-[color:var(--color-line)] hover:bg-white/5",
                  )}
                >
                  <div className="truncate font-medium text-white">{workflow.title || workflow.workflow_key}</div>
                  <div className="mt-1 break-words text-xs text-slate-400">
                    {joinItems([workflow.workflow_key, `${workflow.participant_entry_ids.length} participants`, workflow.intent_memory_type])}
                  </div>
                </button>
              ))}
            </div>
            <Button variant="danger" onClick={removeWorkflow} disabled={!currentWorkflow}>
              Remove workflow
            </Button>
          </div>
        </div>

        <div className="min-w-0 space-y-4">
          <div className="panel space-y-4 p-5 sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="label">Module details</div>
                <div className="mt-2 text-sm leading-6 text-slate-300">Group related APIs by family or domain before wiring workflows.</div>
              </div>
              {currentModule ? <Badge>{currentModule.entries.length} entries</Badge> : null}
            </div>
            {currentModule ? (
              <div className="panel-inset grid gap-4 p-4 lg:grid-cols-2">
                <div>
                  <Label>Module key</Label>
                  <Input value={currentModule.module_key} onChange={(event) => updateModuleField("module_key", event.target.value)} />
                </div>
                <div>
                  <Label>Title</Label>
                  <Input value={currentModule.title} onChange={(event) => updateModuleField("title", event.target.value)} />
                </div>
                <div className="lg:col-span-2">
                  <Label>Description</Label>
                  <Textarea
                    className="min-h-28"
                    value={currentModule.description}
                    onChange={(event) => updateModuleField("description", event.target.value)}
                  />
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-400">Add a module to start organizing API families.</p>
            )}
          </div>

          <div className="panel space-y-5 p-5 sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="label">Entry details</div>
                <div className="mt-2 text-sm leading-6 text-slate-300">Describe one concrete API and its persistence behavior.</div>
              </div>
              {currentEntry ? <Badge tone={currentEntry.enabled ? "success" : "danger"}>{currentEntry.enabled ? "enabled" : "disabled"}</Badge> : null}
            </div>
            {currentEntry ? (
              <div className="space-y-4">
                <div className="panel-inset grid gap-4 p-4 lg:grid-cols-2">
                  <div>
                    <Label>Entry id</Label>
                    <Input
                      value={currentEntry.entry_id}
                      onChange={(event) =>
                        updateEntry((entry, draft) => {
                          const nextId = event.target.value;
                          const previousId = entry.entry_id;
                          entry.entry_id = nextId;
                          replaceEntryId(draft, previousId, nextId);
                          setSelectedEntryId(nextId);
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>API name</Label>
                    <Input value={currentEntry.api_name} onChange={(event) => updateEntry((entry) => {
                      entry.api_name = event.target.value;
                    })} />
                  </div>
                  <div>
                    <Label>Domain</Label>
                    <Input value={currentEntry.domain} onChange={(event) => updateEntry((entry) => {
                      entry.domain = event.target.value;
                    })} />
                  </div>
                  <div>
                    <Label>Enabled</Label>
                    <Select value={String(currentEntry.enabled)} onChange={(event) => updateEntry((entry) => {
                      entry.enabled = event.target.value === "true";
                    })}>
                      <option value="true">true</option>
                      <option value="false">false</option>
                    </Select>
                  </div>
                  <div>
                    <Label>Capability family</Label>
                    <Select value={currentEntry.capability_family} onChange={(event) => updateEntry((entry) => {
                      entry.capability_family = event.target.value;
                    })}>
                      {[
                        "PROFILE_WRITE",
                        "PREFERENCE_SET",
                        "RELATION_WRITE",
                        "ENTITY_UPSERT",
                        "CONTENT_READ",
                        "SEARCH_READ",
                        "DELETE_FORGET",
                        "UNKNOWN",
                      ].map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label>Method semantics</Label>
                    <Select value={currentEntry.method_semantics} onChange={(event) => updateEntry((entry) => {
                      entry.method_semantics = event.target.value;
                    })}>
                      {["READ", "WRITE", "DELETE"].map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label>Default action</Label>
                    <Select value={currentEntry.default_action} onChange={(event) => updateEntry((entry) => {
                      entry.default_action = event.target.value;
                    })}>
                      {["BLOCK", "OBSERVE", "SESSION", "UPSERT", "FORGET"].map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label>Repeat policy</Label>
                    <Select value={currentEntry.repeat_policy} onChange={(event) => updateEntry((entry) => {
                      entry.repeat_policy = event.target.value;
                    })}>
                      {["BYPASS", "REQUIRED"].map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label>Sensitivity hint</Label>
                    <Select value={currentEntry.sensitivity_hint} onChange={(event) => updateEntry((entry) => {
                      entry.sensitivity_hint = event.target.value;
                    })}>
                      {["S0_PUBLIC", "S1_INTERNAL", "S2_PERSONAL", "S3_CONFIDENTIAL", "S4_RESTRICTED"].map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label>Source precedence key</Label>
                    <Input value={currentEntry.source_precedence_key} onChange={(event) => updateEntry((entry) => {
                      entry.source_precedence_key = event.target.value;
                    })} />
                  </div>
                  <div>
                    <Label>LLM usage mode</Label>
                    <Select value={currentEntry.llm_usage_mode} onChange={(event) => updateEntry((entry) => {
                      entry.llm_usage_mode = event.target.value;
                    })}>
                      {["DISABLED", "ASSIST", "REQUIRE"].map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label>Prompt template key</Label>
                    <Input
                      value={currentEntry.prompt_template_key ?? ""}
                      onChange={(event) =>
                        updateEntry((entry) => {
                          entry.prompt_template_key = event.target.value || null;
                        })
                      }
                    />
                  </div>
                  <div className="lg:col-span-2">
                    <Label>Description</Label>
                    <Textarea
                      className="min-h-28"
                      value={currentEntry.description}
                      onChange={(event) =>
                        updateEntry((entry) => {
                          entry.description = event.target.value;
                        })
                      }
                    />
                  </div>
                </div>

                <div className="panel-inset grid gap-4 p-4 lg:grid-cols-3">
                  <div>
                    <Label>Source system</Label>
                    <Input value={currentEntry.event_match.source_system} onChange={(event) => updateEntry((entry) => {
                      entry.event_match.source_system = event.target.value;
                    })} />
                  </div>
                  <div>
                    <Label>HTTP method</Label>
                    <Input value={currentEntry.event_match.http_method} onChange={(event) => updateEntry((entry) => {
                      entry.event_match.http_method = event.target.value;
                    })} />
                  </div>
                  <div>
                    <Label>Route template</Label>
                    <Input value={currentEntry.event_match.route_template} onChange={(event) => updateEntry((entry) => {
                      entry.event_match.route_template = event.target.value;
                    })} />
                  </div>
                </div>

                <div className="panel-inset grid gap-4 p-4 lg:grid-cols-2">
                  <div>
                    <Label>Candidate memory types</Label>
                    <Input value={joinCommaSeparated(currentEntry.candidate_memory_types)} onChange={(event) => updateEntry((entry) => {
                      entry.candidate_memory_types = parseCommaSeparated(event.target.value);
                    })} />
                  </div>
                  <div>
                    <Label>Extractors</Label>
                    <Input value={joinCommaSeparated(currentEntry.extractors)} onChange={(event) => updateEntry((entry) => {
                      entry.extractors = parseCommaSeparated(event.target.value);
                    })} />
                  </div>
                  <div>
                    <Label>Relation templates</Label>
                    <Input value={joinCommaSeparated(currentEntry.relation_templates)} onChange={(event) => updateEntry((entry) => {
                      entry.relation_templates = parseCommaSeparated(event.target.value);
                    })} />
                  </div>
                  <div>
                    <Label>Allowed field paths</Label>
                    <Input value={joinCommaSeparated(currentEntry.llm_allowed_field_paths)} onChange={(event) => updateEntry((entry) => {
                      entry.llm_allowed_field_paths = parseCommaSeparated(event.target.value);
                    })} />
                  </div>
                  <div>
                    <Label>Blocked field paths</Label>
                    <Input value={joinCommaSeparated(currentEntry.llm_blocked_field_paths)} onChange={(event) => updateEntry((entry) => {
                      entry.llm_blocked_field_paths = parseCommaSeparated(event.target.value);
                    })} />
                  </div>
                  <div>
                    <Label>Request selectors</Label>
                    <Input value={joinCommaSeparated(currentEntry.request_field_selectors)} onChange={(event) => updateEntry((entry) => {
                      entry.request_field_selectors = parseCommaSeparated(event.target.value);
                    })} />
                  </div>
                  <div>
                    <Label>Response selectors</Label>
                    <Input value={joinCommaSeparated(currentEntry.response_field_selectors)} onChange={(event) => updateEntry((entry) => {
                      entry.response_field_selectors = parseCommaSeparated(event.target.value);
                    })} />
                  </div>
                  <div>
                    <Label>Primary fact source</Label>
                    <Select value={currentEntry.normalization_rules.primary_fact_source} onChange={(event) => updateEntry((entry) => {
                      entry.normalization_rules.primary_fact_source = event.target.value;
                    })}>
                      {["request_only", "response_only", "request_then_response", "response_then_request"].map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <Label>Evidence capture policy</Label>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <Select value={currentEntry.evidence_capture_policy.request} onChange={(event) => updateEntry((entry) => {
                        entry.evidence_capture_policy.request = event.target.value;
                      })}>
                        {["none", "summary_only", "summary_plus_artifact_ref"].map((option) => (
                          <option key={option} value={option}>
                            request: {option}
                          </option>
                        ))}
                      </Select>
                      <Select value={currentEntry.evidence_capture_policy.response} onChange={(event) => updateEntry((entry) => {
                        entry.evidence_capture_policy.response = event.target.value;
                      })}>
                        {["none", "summary_only", "summary_plus_artifact_ref"].map((option) => (
                          <option key={option} value={option}>
                            response: {option}
                          </option>
                        ))}
                      </Select>
                    </div>
                  </div>
                  <div className="lg:col-span-2">
                    <Label>Notes</Label>
                    <Textarea
                      className="min-h-24"
                      value={currentEntry.notes ?? ""}
                      onChange={(event) => updateEntry((entry) => {
                        entry.notes = event.target.value;
                      })}
                    />
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-400">Select an API entry to edit its matching and memory behavior.</p>
            )}
          </div>

          <div className="panel space-y-5 p-5 sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="label">Workflow details</div>
                <div className="mt-2 text-sm leading-6 text-slate-300">Describe cross-API relationships and the user goal they imply.</div>
              </div>
              {currentWorkflow ? <Badge tone="accent">{currentWorkflow.participant_entry_ids.length} participants</Badge> : null}
            </div>
            {currentWorkflow ? (
              <div className="space-y-4">
                <div className="panel-inset grid gap-4 p-4 lg:grid-cols-2">
                  <div>
                    <Label>Workflow key</Label>
                    <Input
                      value={currentWorkflow.workflow_key}
                      onChange={(event) =>
                        updateWorkflow((workflow) => {
                          workflow.workflow_key = event.target.value;
                          setSelectedWorkflowKey(event.target.value);
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>Title</Label>
                    <Input value={currentWorkflow.title} onChange={(event) => updateWorkflow((workflow) => {
                      workflow.title = event.target.value;
                    })} />
                  </div>
                  <div className="lg:col-span-2">
                    <Label>Description</Label>
                    <Textarea
                      className="min-h-24"
                      value={currentWorkflow.description}
                      onChange={(event) =>
                        updateWorkflow((workflow) => {
                          workflow.description = event.target.value;
                        })
                      }
                    />
                  </div>
                  <div>
                    <Label>Intent memory type</Label>
                    <Input value={currentWorkflow.intent_memory_type} onChange={(event) => updateWorkflow((workflow) => {
                      workflow.intent_memory_type = event.target.value;
                    })} />
                  </div>
                  <div>
                    <Label>Default intent summary</Label>
                    <Input value={currentWorkflow.default_intent_summary} onChange={(event) => updateWorkflow((workflow) => {
                      workflow.default_intent_summary = event.target.value;
                    })} />
                  </div>
                  <div className="lg:col-span-2">
                    <Label>Participant entry ids</Label>
                    <Textarea
                      className="min-h-28"
                      value={joinLineSeparated(currentWorkflow.participant_entry_ids)}
                      onChange={(event) =>
                        updateWorkflow((workflow) => {
                          workflow.participant_entry_ids = parseLineSeparated(event.target.value);
                        })
                      }
                    />
                    <p className="mt-2 text-xs text-slate-400">
                      Available entry ids: {availableEntryIds.length ? availableEntryIds.join(", ") : "none"}
                    </p>
                  </div>
                </div>

                <div className="panel-inset space-y-3 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="label">Relationship edges</div>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        updateWorkflow((workflow) => {
                          workflow.relationship_edges.push({
                            from_entry_id: workflow.participant_entry_ids[0] ?? "",
                            to_entry_id: workflow.participant_entry_ids[1] ?? workflow.participant_entry_ids[0] ?? "",
                            edge_type: "ENABLES",
                          });
                        })
                      }
                    >
                      Add edge
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {currentWorkflow.relationship_edges.map((edge, edgeIndex) => (
                      <div key={`${edge.from_entry_id}-${edge.to_entry_id}-${edge.edge_type}-${edgeIndex}`} className="grid gap-3 rounded-2xl border border-white/10 bg-slate-950/40 p-3 lg:grid-cols-[1fr_1fr_180px_auto]">
                        <Select value={edge.from_entry_id} onChange={(event) => updateWorkflow((workflow) => {
                          workflow.relationship_edges[edgeIndex].from_entry_id = event.target.value;
                        })}>
                          <option value="">Select source entry</option>
                          {availableEntryIds.map((entryId) => (
                            <option key={entryId} value={entryId}>
                              {entryId}
                            </option>
                          ))}
                        </Select>
                        <Select value={edge.to_entry_id} onChange={(event) => updateWorkflow((workflow) => {
                          workflow.relationship_edges[edgeIndex].to_entry_id = event.target.value;
                        })}>
                          <option value="">Select related entry</option>
                          {availableEntryIds.map((entryId) => (
                            <option key={entryId} value={entryId}>
                              {entryId}
                            </option>
                          ))}
                        </Select>
                        <Select value={edge.edge_type} onChange={(event) => updateWorkflow((workflow) => {
                          workflow.relationship_edges[edgeIndex].edge_type = event.target.value;
                        })}>
                          {["PRECEDES", "READS_AFTER_WRITE", "ENABLES", "COMPENSATES", "ALTERNATIVE_TO"].map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </Select>
                        <Button
                          variant="danger"
                          onClick={() =>
                            updateWorkflow((workflow) => {
                              workflow.relationship_edges = workflow.relationship_edges.filter((_, index) => index !== edgeIndex);
                            })
                          }
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                    {!currentWorkflow.relationship_edges.length ? (
                      <p className="text-sm text-slate-400">Add edges to explain how one API leads to another.</p>
                    ) : null}
                  </div>
                </div>

                <div className="panel-inset space-y-3 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="label">Intent rules</div>
                    <Button
                      variant="secondary"
                      onClick={() =>
                        updateWorkflow((workflow) => {
                          workflow.intent_rules.push({
                            observed_entry_ids: workflow.participant_entry_ids.length ? [workflow.participant_entry_ids[0]] : [],
                            summary: workflow.default_intent_summary,
                          });
                        })
                      }
                    >
                      Add rule
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {currentWorkflow.intent_rules.map((rule, ruleIndex) => (
                      <div key={`${currentWorkflow.workflow_key}-rule-${ruleIndex}`} className="space-y-3 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
                        <div>
                          <Label>Observed entry ids</Label>
                          <Input value={joinCommaSeparated(rule.observed_entry_ids)} onChange={(event) => updateWorkflow((workflow) => {
                            workflow.intent_rules[ruleIndex].observed_entry_ids = parseCommaSeparated(event.target.value);
                          })} />
                        </div>
                        <div>
                          <Label>Summary</Label>
                          <Textarea
                            className="min-h-24"
                            value={rule.summary}
                            onChange={(event) =>
                              updateWorkflow((workflow) => {
                                workflow.intent_rules[ruleIndex].summary = event.target.value;
                              })
                            }
                          />
                        </div>
                        <Button
                          variant="danger"
                          onClick={() =>
                            updateWorkflow((workflow) => {
                              workflow.intent_rules = workflow.intent_rules.filter((_, index) => index !== ruleIndex);
                            })
                          }
                        >
                          Remove rule
                        </Button>
                      </div>
                    ))}
                    {!currentWorkflow.intent_rules.length ? (
                      <p className="text-sm text-slate-400">Add rule-specific summaries when one observed API should update the intent text differently.</p>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-400">Add a workflow to link APIs into a broader user goal.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function timestamp(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusTone(status: string): "neutral" | "success" | "warning" | "danger" | "accent" {
  if (status === "pass" || status === "active" || status === "accepted") return "success";
  if (status === "warn" || status === "validated" || status === "approved") return "warning";
  if (status === "fail" || status === "blocked") return "danger";
  if (status === "overridden" || status === "conflicted") return "accent";
  return "neutral";
}

function shortId(value: string) {
  return value.length > 12 ? `${value.slice(0, 12)}…` : value;
}

function ConfirmGate({
  title,
  body,
  open,
  confirmLabel,
  danger,
  onCancel,
  onConfirm,
}: {
  title: string;
  body: string;
  open: boolean;
  confirmLabel: string;
  danger?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/70 px-4">
      <div className="panel-strong w-full max-w-lg space-y-4 p-6">
        <div className="label">Confirmation required</div>
        <div className="text-xl font-semibold text-white">{title}</div>
        <p className="text-sm text-slate-300">{body}</p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant={danger ? "danger" : "primary"} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

function StateCard({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <Card className="space-y-3">
      <div className="label">Backend state</div>
      <div className="text-lg font-semibold text-white">{title}</div>
      <p className="text-sm text-slate-300">{body}</p>
      {action ? <div>{action}</div> : null}
    </Card>
  );
}

export function ConfigWorkspace({ kind }: { kind: ConfigKind }) {
  const meta = kindMeta[kind];
  const session = useConsoleSession();
  const [allDocs, setAllDocs] = useState<ConfigDocument[]>([]);
  const [docs, setDocs] = useState<ConfigDocument[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [active, setActive] = useState<ConfigDocument | null>(null);
  const [editor, setEditor] = useState<ConfigDocument | null>(null);
  const [sourceFormat, setSourceFormat] = useState<EditorFormat>("yaml");
  const [sourceText, setSourceText] = useState("");
  const [validations, setValidations] = useState<ValidationRun[]>([]);
  const [publications, setPublications] = useState<PublicationSnapshot[]>([]);
  const [importSource, setImportSource] = useState("");
  const [importFormat, setImportFormat] = useState<EditorFormat>("yaml");
  const [publishNotes, setPublishNotes] = useState("");
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [confirmPublish, setConfirmPublish] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [pendingDocumentId, setPendingDocumentId] = useState<string | null>(null);
  const [confirmDiscardChanges, setConfirmDiscardChanges] = useState(false);
  const [confirmResetSource, setConfirmResetSource] = useState(false);
  const [loading, setLoading] = useState(true);
  const activeApiPackage = useMemo(
    () => (kind === "api-ontology" ? resolveApiPackage(active) : null),
    [active, kind],
  );
  const apiPackageDraft = useMemo(() => {
    if (kind !== "api-ontology") {
      return null;
    }
    const parsedFromSource = sourceFormat === "json" ? parseApiOntologyPackage(safeParseJson(sourceText)) : null;
    return parsedFromSource ?? resolveApiPackage(editor);
  }, [editor, kind, sourceFormat, sourceText]);

  const refresh = async (options?: { preferredActiveId?: string; preferredFormat?: EditorFormat }) => {
    setLoading(true);
    setError("");
    try {
      const [nextAllDocs, nextValidations, nextPublications] = await Promise.all([
        client.configs.list(),
        client.validations.list(),
        client.publications.list({ kind: kind === "api-ontology" ? "api_ontology" : kind === "memory-ontology" ? "memory_ontology" : "policy_profile" }),
      ]);
      const nextDocs = nextAllDocs.filter((doc) => doc.kind === kind);
      const preferredFormat = options?.preferredFormat ?? sourceFormat;
      const preferredId = options?.preferredActiveId ?? activeId ?? nextDocs[0]?.id;
      const selected = nextDocs.find((doc) => doc.id === preferredId) ?? nextDocs[0] ?? null;
      setAllDocs(nextAllDocs);
      setDocs(nextDocs);
      setValidations(nextValidations);
      setPublications(nextPublications);
      setSourceFormat(preferredFormat);
      setActive(selected);
      setEditor(selected ? { ...selected } : null);
      setSourceText(selected ? serializeDocumentSource(selected, preferredFormat) : "");
      setActiveId(selected?.id ?? "");
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  useEffect(() => {
    if (!docs.length) {
      setActive(null);
      setEditor(null);
      setSourceText("");
      setActiveId("");
      return;
    }
    if (!activeId) {
      const first = docs[0] ?? null;
      setActive(first);
      setEditor(first ? { ...first } : null);
      setSourceText(first ? serializeDocumentSource(first, sourceFormat) : "");
      setActiveId(first?.id ?? "");
      return;
    }
    const next = docs.find((doc) => doc.id === activeId) ?? null;
    setActive(next);
    setEditor(next ? { ...next } : null);
    setSourceText(next ? serializeDocumentSource(next, sourceFormat) : "");
  }, [activeId, docs]);

  const activeFamilyDocs = useMemo(() => {
    if (!active) {
      return [];
    }
    return allDocs.filter(
      (doc) => doc.scope === active.scope && doc.tenant === active.tenant,
    );
  }, [active, allDocs]);

  const currentBundle = useMemo(() => {
    const latestByKind = new Map<ConfigKind, ConfigDocument>();
    for (const doc of activeFamilyDocs) {
      const current = latestByKind.get(doc.kind);
      if (!current || doc.version > current.version) {
        latestByKind.set(doc.kind, doc);
      }
    }
    const apiOntology = latestByKind.get("api-ontology");
    const memoryOntology = latestByKind.get("memory-ontology");
    const policyProfile = latestByKind.get("policy-profile");
    if (!apiOntology || !memoryOntology || !policyProfile) {
      return null;
    }
    return { apiOntology, memoryOntology, policyProfile };
  }, [activeFamilyDocs]);

  const bundleReadyToPublish = useMemo(() => {
    if (!currentBundle) {
      return false;
    }
    return [currentBundle.apiOntology, currentBundle.memoryOntology, currentBundle.policyProfile].every((document) =>
      ["approved", "published"].includes(document.status),
    );
  }, [currentBundle]);

  const latestValidation = useMemo(
    () => (active ? validations.filter((item) => item.documentId === active.id)[0] ?? null : null),
    [active, validations],
  );

  const publishHistory = useMemo(
    () =>
      publications.filter(
        (item) =>
          active &&
          [item.apiOntology.id, item.memoryOntology.id, item.policyProfile.id].includes(active.id),
      ),
    [active, publications],
  );

  const selectedRole = session?.user.role;
  const canEdit = canEditConfig(selectedRole);
  const canApproveSelected = canApprove(selectedRole);
  const canArchiveSelected = canArchive(selectedRole);
  const canPublishSelected = canPublish(selectedRole);

  const hasUnsavedMetadataChanges = useMemo(() => {
    if (!active || !editor) {
      return false;
    }
    return active.name !== editor.name || active.scope !== editor.scope || active.tenant !== editor.tenant;
  }, [active, editor]);

  const hasUnsavedSourceChanges = useMemo(() => {
    if (!active) {
      return false;
    }
    return serializeDocumentSource(active, sourceFormat) !== sourceText;
  }, [active, sourceFormat, sourceText]);

  const hasUnsavedPackageChanges = useMemo(
    () =>
      kind === "api-ontology"
        ? hasPackageDraftChanges({
            active: activeApiPackage,
            editor: apiPackageDraft,
          })
        : false,
    [activeApiPackage, apiPackageDraft, kind],
  );

  const hasUnsavedChanges = useMemo(
    () =>
      hasConfigDraftChanges({
        active,
        editor,
        sourceText,
        sourceFormat,
      }) || hasUnsavedPackageChanges,
    [active, editor, hasUnsavedPackageChanges, sourceText, sourceFormat],
  );

  const currentSourceLines = useMemo(() => sourceLineCount(sourceText), [sourceText]);
  const apiPackageModuleCount = apiPackageDraft?.modules.length ?? 0;
  const apiPackageEntryCount = apiPackageDraft?.modules.reduce((count, module) => count + module.entries.length, 0) ?? 0;
  const apiPackageWorkflowCount = apiPackageDraft?.workflows.length ?? 0;

  const applyApiPackageDraft = (nextPackage: APIOntologyPackage) => {
    if (!editor) {
      return;
    }
    setEditor({
      ...editor,
      definitionJson: nextPackage as unknown as Record<string, unknown>,
      apiOntologyPackage: nextPackage,
    });
    setSourceFormat("json");
    setSourceText(serializeApiOntologyPackage(nextPackage));
  };

  const persistDraft = async (options?: { preferredFormat?: EditorFormat; statusMessage?: string | null }) => {
    if (!editor) {
      return null;
    }
    setError("");
    const name = editor.name.trim();
    const scope = editor.scope.trim() || "global";
    const tenant = editor.tenant.trim() || "all";
    if (!name) {
      setError("Name is required before saving.");
      return null;
    }

    const baseConfig = {
      ...editor,
      name,
      scope,
      tenant,
    };

    try {
      let saved: ConfigDocument;
      if (sourceFormat === "json") {
        const parsedJson = safeParseJson(sourceText);
        if (!parsedJson) {
          setError("Source must be valid JSON before saving.");
          return null;
        }
        saved = await client.configs.save({
          ...baseConfig,
          yaml: editor.yaml,
          definitionJson: parsedJson,
        });
      } else {
        saved = await client.configs.save({
          ...baseConfig,
          yaml: sourceText,
          definitionJson: undefined,
        });
      }
      if (options?.statusMessage !== null) {
        setStatusMessage(options?.statusMessage ?? `Saved ${saved.name} as v${saved.version}.`);
      }
      await refresh({ preferredActiveId: saved.id, preferredFormat: options?.preferredFormat ?? sourceFormat });
      return saved;
    } catch (requestError) {
      setError(formatError(requestError));
      return null;
    }
  };

  const save = async () => {
    await persistDraft();
  };

  const validate = async () => {
    if (!editor) return;
    setError("");
    try {
      const focusDocument = hasUnsavedChanges
        ? await persistDraft({
            statusMessage: null,
          })
        : editor;
      if (!focusDocument) {
        return;
      }
      const result = currentBundle
        ? await client.configs.validateBundle(
            {
              api_ontology_document_id: kind === "api-ontology" ? focusDocument.id : currentBundle.apiOntology.id,
              memory_ontology_document_id: kind === "memory-ontology" ? focusDocument.id : currentBundle.memoryOntology.id,
              policy_profile_document_id: kind === "policy-profile" ? focusDocument.id : currentBundle.policyProfile.id,
              environment: active?.environment ?? "dev",
              tenant_id: active?.tenant === "all" ? null : active?.tenant,
            },
            focusDocument.id,
          )
        : await client.configs.validate(focusDocument.id);
      setStatusMessage(
        hasUnsavedChanges
          ? `Saved the current draft and validated ${focusDocument.name} with ${result.status.toUpperCase()}.`
          : `Validation ${result.status.toUpperCase()} for ${result.documentId}.`,
      );
      await refresh({ preferredActiveId: focusDocument.id });
    } catch (requestError) {
      setError(formatError(requestError));
    }
  };

  const approve = async () => {
    if (!editor) return;
    setError("");
    const result = await client.configs.approve(editor.id);
    setStatusMessage(`Approved ${result.id} with status ${result.status}.`);
    await refresh();
  };

  const archive = async () => {
    if (!editor) return;
    setError("");
    const archived = await client.configs.archive(editor.id);
    setStatusMessage(`Archived ${archived.name} v${archived.version}.`);
    setConfirmArchive(false);
    await refresh();
  };

  const publish = async () => {
    if (!currentBundle || !active) return;
    setError("");
    const snapshot = await client.configs.publish({
      api_ontology_document_id: currentBundle.apiOntology.id,
      memory_ontology_document_id: currentBundle.memoryOntology.id,
      policy_profile_document_id: currentBundle.policyProfile.id,
      scope: active.scope,
      tenant_id: active.tenant === "all" ? null : active.tenant,
      environment: active.environment,
      release_notes: publishNotes,
    });
    setStatusMessage(`Published snapshot ${shortId(snapshot.configSnapshotId)}.`);
    setConfirmPublish(false);
    setPublishNotes("");
    await refresh();
  };

  const importDocument = async () => {
    if (!importSource.trim()) return;
    setError("");
    await client.configs.importDocument(kind, importSource, importFormat);
    setStatusMessage(`${importFormat.toUpperCase()} imported into the active document set.`);
    setImportSource("");
    await refresh();
  };

  const exportDocument = async () => {
    if (!editor) return;
    const exported = await client.configs.exportDocument(editor.id, sourceFormat);
    await navigator.clipboard.writeText(exported);
    setStatusMessage(`${sourceFormat.toUpperCase()} copied to clipboard.`);
  };

  const createStarterDraft = async () => {
    const created = await client.configs.save({
      id: "",
      kind,
      name: starterName(kind),
      version: 1,
      status: "draft",
      tenant: "all",
      scope: "global",
      environment: "dev",
      updatedAt: new Date().toISOString(),
      summary: `Starter ${meta.title} draft`,
      yaml: "",
      definitionJson: cloneStarterDefinition(kind),
    });
    setStatusMessage(`Created ${created.name} v${created.version}.`);
    await refresh({ preferredActiveId: created.id });
  };

  const switchDocument = (documentId: string) => {
    if (documentId === activeId) {
      return;
    }
    if (hasUnsavedChanges) {
      setPendingDocumentId(documentId);
      setConfirmDiscardChanges(true);
      return;
    }
    setActiveId(documentId);
  };

  const resetSourceFromBackend = () => {
    if (!editor) {
      return;
    }
    if (hasUnsavedSourceChanges) {
      setConfirmResetSource(true);
      return;
    }
    setSourceText(serializeDocumentSource(editor, sourceFormat));
    setStatusMessage(`Reset ${sourceFormat.toUpperCase()} source from the saved document.`);
  };

  const changeSourceFormat = async (nextFormat: EditorFormat) => {
    if (!editor || nextFormat === sourceFormat) {
      return;
    }
    setError("");
    if (hasUnsavedChanges) {
      const saved = await persistDraft({
        preferredFormat: nextFormat,
        statusMessage: null,
      });
      if (!saved) {
        return;
      }
      setStatusMessage(`Saved ${saved.name} and switched to ${nextFormat.toUpperCase()} view.`);
      return;
    }
    setSourceFormat(nextFormat);
    setSourceText(serializeDocumentSource(editor, nextFormat));
    setStatusMessage(`Switched to ${nextFormat.toUpperCase()} view.`);
  };

  return (
    <div className="space-y-4">
      <Section
        eyebrow={meta.eyebrow}
        title={meta.title}
        action={<Badge tone={statusTone(active?.status ?? "draft")}>{active?.status ?? "draft"}</Badge>}
      >
        {error ? (
          <StateCard
            title="Unable to load config documents"
            body={error}
            action={<Button onClick={() => void refresh()}>Retry</Button>}
          />
        ) : loading ? (
          <StateCard title="Loading config documents" body="Fetching live documents, validations, and publications from the backend." />
        ) : (
          <Card className="space-y-4">
            <p className="max-w-3xl text-sm text-slate-300">{meta.description}</p>
            <div className="grid gap-4 2xl:grid-cols-[280px_minmax(0,1fr)]">
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="label">Documents</div>
                  {!docs.length ? (
                    <Button onClick={() => void createStarterDraft()} disabled={!canEdit}>Create starter draft</Button>
                  ) : null}
                </div>
                <div className="space-y-2">
                  {docs.map((doc) => (
                    <button
                      key={doc.id}
                      onClick={() => switchDocument(doc.id)}
                      className={cx(
                        "w-full rounded-2xl border px-4 py-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--color-accent)]/35 active:translate-y-px",
                        doc.id === activeId
                          ? "border-[color:var(--color-line-strong)] bg-[color:var(--color-card-accent)] shadow-sm"
                          : "border-[color:var(--color-line-subtle)] bg-[color:var(--color-card-inset)] hover:border-[color:var(--color-line)] hover:bg-white/5",
                      )}
                    >
                      <div className="flex min-w-0 items-start justify-between gap-3">
                        <div className="min-w-0 font-medium text-white truncate">{doc.name}</div>
                        <Badge tone={statusTone(doc.status)} className="shrink-0">{doc.status}</Badge>
                      </div>
                      <div className="mt-2 break-words text-xs text-slate-400">
                        {joinItems([`v${doc.version}`, doc.scope, doc.tenant, doc.environment])}
                      </div>
                    </button>
                  ))}
                  {!docs.length ? (
                    <p className="rounded-2xl border border-dashed border-white/10 bg-white/5 px-4 py-6 text-sm text-slate-400">
                      No {meta.title} documents exist yet. Create a starter draft to open the editor.
                    </p>
                  ) : null}
                </div>
              </div>

              <div className="space-y-4">
                {editor ? (
                  <>
                    {kind === "api-ontology" ? (
                      <ConsolePageHeader
                        eyebrow={meta.eyebrow}
                        title={editor.name}
                        description="Use the structured package editor as the primary path. Keep lifecycle actions near the header, tune modules and entries in the main lane, and drop into raw source only when you need expert control."
                        status={<Badge tone={statusTone(editor.status)}>{editor.status}</Badge>}
                        actions={
                          <>
                            <Button onClick={save} disabled={!canEdit}>
                              Save draft
                            </Button>
                            <Button variant="secondary" onClick={validate} disabled={!canEdit}>
                              Validate
                            </Button>
                            <Button variant="secondary" onClick={approve} disabled={!canApproveSelected || editor.status !== "validated"}>
                              Approve
                            </Button>
                            <Button variant="secondary" onClick={exportDocument}>
                              Export {sourceFormat.toUpperCase()}
                            </Button>
                            <Button onClick={() => setConfirmPublish(true)} disabled={!currentBundle || !canPublishSelected || !bundleReadyToPublish}>
                              Publish bundle
                            </Button>
                          </>
                        }
                        meta={
                          <>
                            <Badge>{joinItems([`v${editor.version}`, editor.scope, editor.tenant, editor.environment])}</Badge>
                            <Badge>{apiPackageModuleCount} modules</Badge>
                            <Badge>{apiPackageEntryCount} APIs</Badge>
                            <Badge>{apiPackageWorkflowCount} workflows</Badge>
                            <Badge tone={hasUnsavedChanges ? "warning" : "success"}>
                              {hasUnsavedChanges ? "Unsaved draft changes" : "Draft synced to backend"}
                            </Badge>
                          </>
                        }
                      />
                    ) : null}

                    <div className={cx("grid gap-3", kind === "api-ontology" ? "sm:grid-cols-2 2xl:grid-cols-4" : "sm:grid-cols-2 lg:grid-cols-3")}>
                      {kind === "api-ontology" ? (
                        <>
                          <Metric label="Version" value={`v${editor.version}`} hint="Active ontology revision" />
                          <Metric label="Modules" value={String(apiPackageModuleCount)} hint="Grouped API families in the current draft" />
                          <Metric label="API entries" value={String(apiPackageEntryCount)} hint="Concrete APIs modeled in structured authoring" />
                          <Metric label="Workflows" value={String(apiPackageWorkflowCount)} hint="Cross-API user-task definitions" />
                        </>
                      ) : (
                        <>
                          <Metric label="Version" value={`v${editor.version}`} hint="Document revision" />
                          <Metric label="Scope" value={editor.scope} hint="Applies to runtime" />
                          <Metric label="Environment" value={editor.environment} hint="Operator environment" />
                        </>
                      )}
                    </div>

                    <div className="grid gap-4 min-[110rem]:grid-cols-[minmax(0,1fr)_360px]">
                      <div className="min-w-0 space-y-4">
                        <Card className="space-y-4">
                          <div className="grid gap-4 lg:grid-cols-2">
                            <div>
                              <Label>Name</Label>
                              <Input value={editor.name} onChange={(event) => setEditor({ ...editor, name: event.target.value })} />
                            </div>
                            <div>
                              <Label>Status</Label>
                              <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white">
                                {editor.status}
                              </div>
                            </div>
                            <div>
                              <Label>Tenant</Label>
                              <Input value={editor.tenant} onChange={(event) => setEditor({ ...editor, tenant: event.target.value })} />
                            </div>
                            <div>
                              <Label>Scope</Label>
                              <Input value={editor.scope} onChange={(event) => setEditor({ ...editor, scope: event.target.value })} />
                            </div>
                          </div>

                          {kind === "api-ontology" ? (
                            <div className="panel-inset space-y-2 p-4">
                              <div className="label">Summary snapshot</div>
                              <p className="text-sm leading-6 text-slate-300">
                                {editor.summary || "No derived summary is available for the current saved definition yet."}
                              </p>
                              <p className="text-xs text-slate-400">This summary is derived from the saved document definition, not from unsaved local edits.</p>
                            </div>
                          ) : (
                            <div>
                              <Label>Summary preview</Label>
                              <Textarea className="min-h-24" value={editor.summary} readOnly />
                              <p className="mt-2 text-xs text-slate-400">Summary is derived from the saved document definition.</p>
                            </div>
                          )}

                          {kind !== "api-ontology" ? (
                            <div className="grid gap-2 sm:grid-cols-2 2xl:grid-cols-3">
                              <Button onClick={save} disabled={!canEdit} className="w-full">Save draft</Button>
                              <Button variant="secondary" onClick={validate} disabled={!canEdit} className="w-full">
                                Validate
                              </Button>
                              <Button variant="secondary" onClick={approve} disabled={!canApproveSelected || editor.status !== "validated"} className="w-full">
                                Approve
                              </Button>
                              <Button variant="secondary" onClick={() => setConfirmArchive(true)} disabled={!canArchiveSelected} className="w-full">
                                Archive
                              </Button>
                              <Button variant="secondary" onClick={exportDocument} className="w-full">
                                Export {sourceFormat.toUpperCase()}
                              </Button>
                              <Button onClick={() => setConfirmPublish(true)} disabled={!currentBundle || !canPublishSelected || !bundleReadyToPublish} className="w-full">
                                Publish bundle
                              </Button>
                            </div>
                          ) : (
                            <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[color:var(--color-line-subtle)] bg-[color:var(--color-card-inset)] px-4 py-3 text-sm text-slate-300">
                              <span>Primary actions are pinned above so operators can stay in the structured editor.</span>
                              <Button variant="secondary" onClick={() => setConfirmArchive(true)} disabled={!canArchiveSelected}>
                                Archive
                              </Button>
                            </div>
                          )}
                          {!canEdit ? <p className="text-xs text-slate-400">Your current role is read-only for config editing.</p> : null}
                          {currentBundle && !bundleReadyToPublish ? <p className="text-xs text-slate-400">Approve each document in the bundle before publishing the snapshot.</p> : null}
                          {canEdit ? (
                            <p className="text-xs text-slate-400">
                              Validation automatically saves the current draft first when the source or metadata changed.
                            </p>
                          ) : null}
                        </Card>

                        {kind === "api-ontology" ? (
                          <ApiOntologyPackageEditor
                            activePackage={activeApiPackage}
                            packageDraft={apiPackageDraft}
                            onChangePackage={applyApiPackageDraft}
                          />
                        ) : null}

                        <Section
                          eyebrow={kind === "api-ontology" ? "Expert raw mode" : "Raw source"}
                          title={kind === "api-ontology" ? "Expert source editor" : "Document source"}
                          action={
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge tone={hasUnsavedChanges ? "warning" : "success"}>
                                {hasUnsavedChanges ? "Unsaved changes" : "Synced to backend"}
                              </Badge>
                              <Badge>{sourceFormat.toUpperCase()}</Badge>
                              <Badge>{currentSourceLines} lines</Badge>
                            </div>
                          }
                        >
                          <div className="grid gap-3 lg:grid-cols-[180px_minmax(0,1fr)]">
                            <Select value={sourceFormat} onChange={(event) => void changeSourceFormat(event.target.value as EditorFormat)}>
                              <option value="yaml">YAML</option>
                              <option value="json">JSON</option>
                            </Select>
                            <Button variant="secondary" onClick={resetSourceFromBackend} className="w-full">
                              Reset from backend
                            </Button>
                          </div>
                          <Textarea
                            value={sourceText}
                            onChange={(event) => setSourceText(event.target.value)}
                            className="min-h-[24rem] resize-y sm:min-h-[28rem] 2xl:min-h-[36rem]"
                          />
                          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
                            <span>
                              {kind === "api-ontology"
                                ? "Structured edits keep the draft in JSON until you save. Switch to YAML after saving if you need the backend-rendered export."
                                : "Edit the current document source directly. Format changes save the current draft first so the YAML and JSON views stay in sync."}
                            </span>
                            {hasUnsavedMetadataChanges ? <span>Metadata changes are still pending save.</span> : null}
                          </div>
                        </Section>

                        <Section eyebrow="Revision diff" title="Revision diff">
                          <div className="grid gap-4 lg:grid-cols-2">
                            <Card className="min-w-0">
                              <div className="label">Previous</div>
                              <CodeBlock>{editor.previousYaml ?? "No previous revision yet."}</CodeBlock>
                            </Card>
                            <Card className="min-w-0">
                              <div className="label">Current</div>
                              <CodeBlock>{sourceText || editor.yaml}</CodeBlock>
                            </Card>
                          </div>
                        </Section>
                      </div>

                      <div className="min-w-0 space-y-4">
                        <Card className="space-y-3">
                          <div className="label">Import source</div>
                          <Select value={importFormat} onChange={(event) => setImportFormat(event.target.value as EditorFormat)}>
                            <option value="yaml">YAML</option>
                            <option value="json">JSON</option>
                          </Select>
                          <Textarea
                            className="min-h-48 resize-y sm:min-h-56"
                            placeholder={`Paste ${importFormat.toUpperCase()} here`}
                            value={importSource}
                            onChange={(event) => setImportSource(event.target.value)}
                          />
                          <Button variant="secondary" onClick={importDocument} disabled={!canEdit}>
                            Import {importFormat.toUpperCase()}
                          </Button>
                        </Card>

                        <Card className="space-y-3">
                          <div className="label">Publish notes</div>
                          <Textarea
                            className="min-h-24 resize-y sm:min-h-28"
                            placeholder="Release notes for the next snapshot"
                            value={publishNotes}
                            onChange={(event) => setPublishNotes(event.target.value)}
                          />
                        </Card>

                        <Card className="space-y-3">
                          <div className="label">Bundle preview</div>
                          {currentBundle ? (
                            <div className="space-y-2 text-sm text-slate-300">
                              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                                <div className="truncate font-medium text-white">{currentBundle.apiOntology.name}</div>
                                <div className="mt-1 text-xs text-slate-400">{joinItems([currentBundle.apiOntology.kind, `v${currentBundle.apiOntology.version}`, currentBundle.apiOntology.status])}</div>
                              </div>
                              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                                <div className="truncate font-medium text-white">{currentBundle.memoryOntology.name}</div>
                                <div className="mt-1 text-xs text-slate-400">{joinItems([currentBundle.memoryOntology.kind, `v${currentBundle.memoryOntology.version}`, currentBundle.memoryOntology.status])}</div>
                              </div>
                              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                                <div className="truncate font-medium text-white">{currentBundle.policyProfile.name}</div>
                                <div className="mt-1 text-xs text-slate-400">{joinItems([currentBundle.policyProfile.kind, `v${currentBundle.policyProfile.version}`, currentBundle.policyProfile.status])}</div>
                              </div>
                            </div>
                          ) : (
                            <p className="text-sm text-slate-400">The selected document family does not yet have a complete three-document bundle.</p>
                          )}
                        </Card>

                        <Card className="space-y-3">
                          <div className="label">Validation</div>
                          {latestValidation ? (
                            <div className="space-y-3">
                              <div className="flex items-center justify-between gap-3">
                                <Badge tone={statusTone(latestValidation.status)}>{latestValidation.status}</Badge>
                                <span className="text-xs text-slate-400">{timestamp(latestValidation.timestamp)}</span>
                              </div>
                              <p className="text-sm text-slate-300">{latestValidation.summary}</p>
                              <div className="space-y-2">
                                {latestValidation.checks.map((check) => (
                                  <div key={check.name} className="rounded-xl border border-white/10 bg-white/5 p-3">
                                    <div className="flex items-center justify-between">
                                      <span className="font-medium text-white">{check.name}</span>
                                      <Badge tone={statusTone(check.status)}>{check.status}</Badge>
                                    </div>
                                    <div className="mt-2 text-xs text-slate-400">{check.detail}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <p className="text-sm text-slate-400">Run validation to see schema, lifecycle, and safety checks.</p>
                          )}
                        </Card>

                        <Card className="space-y-3">
                          <div className="label">Publication history</div>
                          <div className="space-y-2">
                            {publishHistory.map((snapshot) => (
                              <div key={snapshot.id} className="rounded-xl border border-white/10 bg-white/5 p-3">
                                <div className="flex min-w-0 items-center justify-between gap-3">
                                  <div className="min-w-0 truncate font-medium text-white">{shortId(snapshot.configSnapshotId)}</div>
                                  <Badge tone={statusTone(snapshot.status)} className="shrink-0">{snapshot.status}</Badge>
                                </div>
                                <div className="mt-1 break-words text-xs text-slate-400">{timestamp(snapshot.publishedAt)} · {snapshot.releaseNotes || "No release notes"}</div>
                              </div>
                            ))}
                            {!publishHistory.length ? <p className="text-sm text-slate-400">No snapshots for this document family yet.</p> : null}
                          </div>
                        </Card>
                      </div>
                    </div>
                  </>
                ) : (
                  <StateCard
                    title={`No ${meta.title} document yet`}
                    body="This page is empty because there is no saved document for this kind. Create a starter draft to open the editor, then customize it in the UI."
                    action={<Button onClick={() => void createStarterDraft()} disabled={!canEdit}>Create starter draft</Button>}
                  />
                )}
              </div>
            </div>
            {statusMessage ? <p className="text-sm text-cyan-200">{statusMessage}</p> : null}
          </Card>
        )}
      </Section>

      <ConfirmGate
        title={`Publish ${editor?.name ?? "document family"}?`}
        body="This will create an immutable three-document snapshot and mark the selected runtime bundle as active."
        open={confirmPublish}
        confirmLabel="Publish snapshot"
        onCancel={() => setConfirmPublish(false)}
        onConfirm={() => {
          void publish();
        }}
      />

      <ConfirmGate
        title={`Archive ${editor?.name ?? "document"}?`}
        body="Archiving closes the current revision and removes it from future lifecycle edits."
        open={confirmArchive}
        confirmLabel="Archive document"
        danger
        onCancel={() => setConfirmArchive(false)}
        onConfirm={() => {
          void archive();
        }}
      />

      <ConfirmGate
        title="Discard unsaved changes?"
        body="You have unsaved draft edits. Discard them before opening a different document."
        open={confirmDiscardChanges}
        confirmLabel="Discard changes"
        danger
        onCancel={() => {
          setPendingDocumentId(null);
          setConfirmDiscardChanges(false);
        }}
        onConfirm={() => {
          if (pendingDocumentId) {
            setActiveId(pendingDocumentId);
          }
          setPendingDocumentId(null);
          setConfirmDiscardChanges(false);
        }}
      />

      <ConfirmGate
        title="Reset source from backend?"
        body="This will discard the current unsaved source edits and reload the last saved document body."
        open={confirmResetSource}
        confirmLabel="Reset source"
        danger
        onCancel={() => setConfirmResetSource(false)}
        onConfirm={() => {
          if (editor) {
            setSourceText(serializeDocumentSource(editor, sourceFormat));
            setStatusMessage(`Reset ${sourceFormat.toUpperCase()} source from the saved document.`);
          }
          setConfirmResetSource(false);
        }}
      />
    </div>
  );
}

export function ValidationWorkspace() {
  const [validations, setValidations] = useState<ValidationRun[]>([]);
  const [configs, setConfigs] = useState<ConfigDocument[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [current, setCurrent] = useState<ValidationRun | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const [nextValidations, nextConfigs] = await Promise.all([client.validations.list(), client.configs.list()]);
      setValidations(nextValidations);
      setConfigs(nextConfigs);
      const first = nextConfigs[0];
      if (!selectedId && first) {
        setSelectedId(first.id);
        const run = nextValidations.find((item) => item.documentId === first.id) ?? null;
        setCurrent(run);
      } else if (selectedId) {
        setCurrent(nextValidations.find((item) => item.documentId === selectedId) ?? null);
      }
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedId) {
      return;
    }
    setCurrent(validations.find((item) => item.documentId === selectedId) ?? null);
  }, [selectedId, validations]);

  const selectedConfig = useMemo(
    () => configs.find((doc) => doc.id === selectedId) ?? null,
    [configs, selectedId],
  );
  const validationByDocumentId = useMemo(
    () => new Map(validations.map((run) => [run.documentId, run])),
    [validations],
  );
  const documentHealth = useMemo(
    () =>
      configs.map((doc) => ({
        doc,
        run: validationByDocumentId.get(doc.id) ?? null,
      })),
    [configs, validationByDocumentId],
  );
  const selectedStatusTone = current ? statusTone(current.status) : "neutral";
  const selectedStatusLabel = current ? current.status : "not run";
  const selectedMeta = selectedConfig
    ? joinItems([
        selectedConfig.kind,
        selectedConfig.scope,
        selectedConfig.tenant,
        selectedConfig.environment,
      ])
    : null;

  const runValidation = async () => {
    if (!selectedId) return;
    setRunning(true);
    setError("");
    try {
      const result = await client.configs.validate(selectedId);
      setValidations((previous) => [result, ...previous.filter((item) => item.documentId !== selectedId)]);
      setCurrent(result);
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-4">
      <ConsolePageHeader
        eyebrow="Validation"
        title={selectedConfig?.name ?? "Validation review"}
        description={
          selectedConfig
            ? "Review whether the selected document is ready for approval or publication. Keep one target in focus, then interpret its checks and blocking issues."
            : "Select a config document first. Validation is the operator review surface for schema, lifecycle, and safety checks before publish-time actions."
        }
        status={<Badge tone={selectedStatusTone}>{selectedStatusLabel}</Badge>}
        actions={
          <Button onClick={runValidation} disabled={!selectedId || running}>
            {running ? "Running validation..." : "Run validation"}
          </Button>
        }
        meta={
          <>
            <Badge>{selectedMeta ?? "No document selected"}</Badge>
            <Badge>{current ? `Last run ${timestamp(current.timestamp)}` : "No recorded validation run"}</Badge>
            {current?.issues.length ? (
              <Badge tone="danger">{current.issues.length} issue(s) require attention</Badge>
            ) : selectedConfig && current ? (
              <Badge tone="success">No blocking issues detected</Badge>
            ) : null}
          </>
        }
      />

      {error ? (
        <StateCard title="Validation data unavailable" body={error} action={<Button onClick={() => void refresh()}>Retry</Button>} />
      ) : loading ? (
        <StateCard title="Loading validations" body="Fetching config documents and validation runs from the backend." />
      ) : (
        <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)] 2xl:grid-cols-[360px_minmax(0,1fr)]">
          <Card className="space-y-4">
            <div className="space-y-2">
              <div className="label">Validation target</div>
              <p className="text-sm leading-6 text-slate-300">
                Choose one config document from the health list, then inspect its current readiness before approval or publication.
              </p>
              <p className="text-xs leading-5 text-slate-500">
                The selected document controls both the current summary and the next validation run.
              </p>
            </div>

            {selectedConfig ? (
              <div className="panel-inset space-y-2 p-4 text-sm text-slate-300">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-white">{selectedConfig.name}</div>
                  <Badge tone={selectedStatusTone}>{selectedStatusLabel}</Badge>
                </div>
                <div className="text-xs leading-5 text-slate-400">{selectedMeta}</div>
                <div className="text-xs leading-5 text-slate-400">
                  {current ? current.summary : "No recorded validation run for the selected document yet."}
                </div>
              </div>
            ) : (
              <EmptyState
                eyebrow="No target"
                title="Select a config document"
                body="Validation needs one document in focus. Pick API Ontology, Memory Ontology, or Policy Profile content before running checks."
              />
            )}

            <div className="space-y-3">
              <div className="label">Document health</div>
              <div className="space-y-2">
                {documentHealth.map(({ doc, run }) => {
                  const active = doc.id === selectedId;
                  return (
                    <button
                      key={doc.id}
                      onClick={() => {
                        setSelectedId(doc.id);
                        setCurrent(run);
                      }}
                      className={cx(
                        "w-full rounded-2xl border px-4 py-3 text-left transition",
                        active
                          ? "border-[color:var(--color-line-strong)] bg-[color:var(--color-card-accent)]"
                          : "border-[color:var(--color-line-subtle)] bg-[color:var(--color-card-inset)] hover:border-[color:var(--color-line)] hover:bg-white/5",
                      )}
                    >
                      <div className="flex min-w-0 items-start gap-3 overflow-hidden">
                        <div className="min-w-0 flex-1">
                          <div className="truncate font-medium text-white" title={doc.name}>
                            {doc.name}
                          </div>
                          <div className="mt-1 truncate text-xs text-slate-400" title={joinItems([doc.kind, doc.scope, doc.tenant])}>
                            {joinItems([doc.kind, doc.scope, doc.tenant])}
                          </div>
                        </div>
                        <Badge className="shrink-0" tone={run ? statusTone(run.status) : "neutral"}>
                          {run ? run.status : "not run"}
                        </Badge>
                      </div>
                      <div className="mt-2 text-xs leading-5 text-slate-400">
                        {run ? `${timestamp(run.timestamp)} · ${run.summary}` : "No validation recorded yet."}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </Card>

          <div className="space-y-4">
            {selectedConfig ? (
              <>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <Metric
                    label="Result"
                    value={current ? current.status.toUpperCase() : "NOT RUN"}
                    hint={current?.summary ?? "Run validation to inspect the selected document."}
                  />
                  <Metric
                    label="Checks"
                    value={String(current?.checks.length ?? 0)}
                    hint="Schema, lifecycle, and safety checks returned for this document."
                  />
                  <Metric
                    label="Issues"
                    value={String(current?.issues.length ?? 0)}
                    hint="Blocking or actionable concerns that need operator review."
                  />
                  <Metric
                    label="Last Run"
                    value={current ? timestamp(current.timestamp) : "Not run"}
                    hint="Most recent validation result for the selected document."
                  />
                </div>

                {current ? (
                  <>
                    <Card className="space-y-4">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="label">Result summary</div>
                          <div className="mt-2 text-lg font-semibold text-white">{current.summary}</div>
                        </div>
                        <Badge tone={selectedStatusTone}>{selectedStatusLabel}</Badge>
                      </div>
                      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_320px]">
                        <div className="space-y-3">
                          <div className="label">Checks</div>
                          <div className="space-y-2">
                            {current.checks.map((check) => (
                              <div key={check.name} className="panel-inset space-y-3 p-4">
                                <div className="flex items-center justify-between gap-3">
                                  <div className="font-medium text-white">{check.name}</div>
                                  <Badge tone={statusTone(check.status)}>{check.status}</Badge>
                                </div>
                                <div className="text-sm leading-6 text-slate-300">{check.detail}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                        <Card className="space-y-3">
                          <div className="label">Issues</div>
                          {current.issues.length ? (
                            <ul className="space-y-2 text-sm text-rose-100">
                              {current.issues.map((issue) => (
                                <li key={issue} className="rounded-xl border border-rose-300/20 bg-rose-400/10 p-3 leading-6">
                                  {issue}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <EmptyState
                              eyebrow="No blockers"
                              title="No validation issues detected"
                              body="The current validation result did not report any actionable warnings or failures for the selected document."
                            />
                          )}
                        </Card>
                      </div>
                    </Card>
                  </>
                ) : (
                  <EmptyState
                    eyebrow="No result"
                    title="Run validation for this document"
                    body="The selected document is in focus, but there is no recorded validation result yet. Run validation to populate checks, issues, and the current readiness summary."
                    action={
                      <Button onClick={runValidation} disabled={running}>
                        {running ? "Running validation..." : "Run validation"}
                      </Button>
                    }
                  />
                )}
              </>
            ) : (
              <EmptyState
                eyebrow="No selection"
                title="Pick a document to begin"
                body="Validation review is document-specific. Select a config document on the left to see its current readiness, issues, and check details."
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function SimulationWorkspace() {
  const [configs, setConfigs] = useState<ConfigDocument[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [sampleEvent, setSampleEvent] = useState("action: docs.openDocument\nuser: current\ncontext: live");
  const [current, setCurrent] = useState<SimulationRun | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const docs = await client.configs.list();
      setConfigs(docs);
      if (!selectedId && docs[0]) {
        setSelectedId(docs[0].id);
      }
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runSimulation = async () => {
    if (!selectedId) return;
    const result = await client.configs.simulate(selectedId, sampleEvent);
    setCurrent(result);
  };

  return (
    <Section eyebrow="Simulation" title="Simulation runner" action={<Button onClick={runSimulation}>Run simulation</Button>}>
      {error ? (
        <StateCard title="Simulation data unavailable" body={error} action={<Button onClick={() => void refresh()}>Retry</Button>} />
      ) : loading ? (
        <StateCard title="Loading simulations" body="Fetching config documents from the backend." />
      ) : (
        <Card className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)] 2xl:grid-cols-[360px_minmax(0,1fr)]">
            <div className="space-y-3">
              <div>
                <Label>Config document</Label>
                <Select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
                  <option value="">Select a document</option>
                  {configs.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.name} · {doc.scope} · {doc.environment}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label>Sample event</Label>
                <Select value={sampleEvent} onChange={(event) => setSampleEvent(event.target.value)} className="mb-2">
                  <option value="action: docs.openDocument\nuser: current\ncontext: live">docs.openDocument</option>
                  <option value="action: profile.updateAddress\nuser: current\ncontext: live">profile.updateAddress</option>
                  <option value="action: search.webSearch\nuser: current\ncontext: live">search.webSearch</option>
                </Select>
                <Textarea value={sampleEvent} onChange={(event) => setSampleEvent(event.target.value)} className="min-h-56" />
              </div>
            </div>

            <div className="space-y-4">
              {current ? (
                <>
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <Metric label="Before" value={current.beforeDecision} hint="Baseline runtime behavior" />
                    <Metric label="After" value={current.afterDecision} hint="Expected with current config" />
                    <Metric
                      label="Model"
                      value={
                        current.inferenceInvoked
                          ? joinItems([
                              current.modelRecommendation ?? "n/a",
                              current.modelConfidence != null ? current.modelConfidence.toFixed(2) : null,
                            ])
                          : "not invoked"
                      }
                      hint="Recommendation and confidence"
                    />
                  </div>
                  <div className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_360px]">
                    <Card className="space-y-3">
                      <div className="label">Decision diff</div>
                      <CodeBlock>{current.diff}</CodeBlock>
                    </Card>
                    <Card className="space-y-3">
                      <div className="label">Reason-code viewer</div>
                      <div className="space-y-2">
                        {current.reasonCodes.map((reason) => (
                          <div key={reason} className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-slate-200">
                            {reason}
                          </div>
                        ))}
                      </div>
                      {current.policyOverride ? (
                        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                          <div className="label">Final policy override</div>
                          <div className="mt-1 text-white">{current.policyOverride}</div>
                        </div>
                      ) : null}
                      {current.changedMemoryCandidates?.length ? (
                        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                          <div className="label">Memory candidates</div>
                          <div className="mt-1 text-white">{current.changedMemoryCandidates.join(" · ")}</div>
                          <div className="mt-2 text-slate-400">
                            write delta {current.expectedWriteDelta ?? 0}, block delta {current.expectedBlockDelta ?? 0}
                          </div>
                        </div>
                      ) : null}
                      <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                        <div className="label">Snapshot context</div>
                        <div className="mt-1 text-white">Active snapshot id: {current.activeSnapshotId ?? "n/a"}</div>
                        <div className="mt-1 text-slate-400">Candidate snapshot id: {current.candidateSnapshotId ?? "n/a"}</div>
                      </div>
                    </Card>
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-400">Run a simulation to compare before and after decisions.</p>
              )}
            </div>
          </div>
        </Card>
      )}
    </Section>
  );
}

export function PublicationWorkspace() {
  const [configs, setConfigs] = useState<ConfigDocument[]>([]);
  const [publications, setPublications] = useState<PublicationSnapshot[]>([]);
  const [filters, setFilters] = useState({ scope: "", tenant: "", environment: "", status: "" });
  const [selectedId, setSelectedId] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const [nextConfigs, nextPublications] = await Promise.all([
        client.configs.list(),
        client.publications.list({
          scope: filters.scope || undefined,
          tenant: filters.tenant || undefined,
          environment: filters.environment || undefined,
          status: filters.status || undefined,
        }),
      ]);
      setConfigs(nextConfigs);
      setPublications(nextPublications);
      if (!selectedId && nextConfigs[0]) {
        setSelectedId(nextConfigs[0].id);
      }
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const currentSnapshots = publications.filter((item) => !selectedId || item.apiOntology.id === selectedId || item.memoryOntology.id === selectedId || item.policyProfile.id === selectedId);

  return (
    <Section eyebrow="Publication" title="Publication history">
      {error ? (
        <StateCard title="Publication history unavailable" body={error} action={<Button onClick={() => void refresh()}>Retry</Button>} />
      ) : loading ? (
        <StateCard title="Loading publication history" body="Fetching live snapshot history from the backend." />
      ) : (
        <Card className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)] 2xl:grid-cols-[320px_minmax(0,1fr)]">
            <div className="space-y-3">
              <div className="grid gap-2">
                <Input placeholder="Scope" value={filters.scope} onChange={(event) => setFilters({ ...filters, scope: event.target.value })} />
                <Input placeholder="Tenant" value={filters.tenant} onChange={(event) => setFilters({ ...filters, tenant: event.target.value })} />
                <Input placeholder="Environment" value={filters.environment} onChange={(event) => setFilters({ ...filters, environment: event.target.value })} />
                <Select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
                  <option value="">All statuses</option>
                  {["active", "rolled-back", "archived"].map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </Select>
              </div>
              <Label>Snapshot bundle</Label>
              <Select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
                <option value="">All bundles</option>
                {configs.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.name} · {doc.scope} · {doc.environment}
                  </option>
                ))}
              </Select>
              <div className="space-y-2">
                {currentSnapshots.map((snapshot) => (
                  <div key={snapshot.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1 break-words font-medium text-white">{snapshot.apiOntology.name}</div>
                      <Badge tone={statusTone(snapshot.status)} className="shrink-0">
                        {snapshot.status}
                      </Badge>
                    </div>
                    <div className="mt-2 break-words text-xs text-slate-400">{joinItems([snapshot.scope, snapshot.tenant ?? "all", snapshot.environment, timestamp(snapshot.publishedAt)])}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                <Metric label="Snapshots" value={String(currentSnapshots.length)} hint="Immutable config snapshots" />
                <Metric label="Active" value={String(currentSnapshots.filter((item) => item.status === "active").length)} hint="Currently active" />
                <Metric label="Rolled back" value={String(currentSnapshots.filter((item) => item.status === "rolled-back").length)} hint="Historical rollback events" />
              </div>

              <Card className="space-y-3">
                <div className="label">Snapshot history</div>
                <div className="space-y-2">
                  {currentSnapshots.map((snapshot) => (
                    <div key={snapshot.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1 space-y-1">
                          <div className="break-words font-medium text-white">{snapshot.releaseNotes || "No release notes"}</div>
                          <div className="break-words text-xs text-slate-400">
                            {snapshot.publishedBy} · {timestamp(snapshot.publishedAt)}
                          </div>
                        </div>
                        <Badge tone={statusTone(snapshot.status)} className="shrink-0">
                          {snapshot.status}
                        </Badge>
                      </div>
                      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                          <div className="label">API Ontology</div>
                          <div className="mt-1 text-sm text-white">{snapshot.apiOntology.name}</div>
                          <div className="mt-1 text-xs text-slate-400">{joinItems([`v${snapshot.apiOntology.version}`, snapshot.apiOntology.status])}</div>
                        </div>
                        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                          <div className="label">Memory Ontology</div>
                          <div className="mt-1 text-sm text-white">{snapshot.memoryOntology.name}</div>
                          <div className="mt-1 text-xs text-slate-400">{joinItems([`v${snapshot.memoryOntology.version}`, snapshot.memoryOntology.status])}</div>
                        </div>
                        <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                          <div className="label">Policy Profile</div>
                          <div className="mt-1 text-sm text-white">{snapshot.policyProfile.name}</div>
                          <div className="mt-1 text-xs text-slate-400">{joinItems([`v${snapshot.policyProfile.version}`, snapshot.policyProfile.status])}</div>
                        </div>
                      </div>
                      <div className="mt-3 text-xs text-slate-400">
                        configSnapshotId: <span className="font-mono text-slate-200">{snapshot.configSnapshotId}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        </Card>
      )}
    </Section>
  );
}

export function RollbackWorkspace() {
  const session = useConsoleSession();
  const [publications, setPublications] = useState<PublicationSnapshot[]>([]);
  const [selectedSnapshot, setSelectedSnapshot] = useState<PublicationSnapshot | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState("");
  const [confirmRollback, setConfirmRollback] = useState(false);

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const nextPublications = await client.publications.list();
      setPublications(nextPublications);
      setSelectedSnapshot((current) => current ?? nextPublications[0] ?? null);
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const rollback = async () => {
    if (!selectedSnapshot) return;
    const result = await client.configs.rollback(selectedSnapshot.configSnapshotId);
    setStatusMessage(`Rolled back to snapshot ${shortId(result.configSnapshotId)}.`);
    setConfirmRollback(false);
    await refresh();
  };

  return (
    <Section eyebrow="Rollback" title="Rollback center">
      {error ? (
        <StateCard title="Rollback history unavailable" body={error} action={<Button onClick={() => void refresh()}>Retry</Button>} />
      ) : loading ? (
        <StateCard title="Loading rollback history" body="Fetching publication snapshots from the backend." />
      ) : (
        <Card className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)] 2xl:grid-cols-[320px_minmax(0,1fr)]">
            <div className="space-y-3">
              <div className="label">Snapshots</div>
              <div className="space-y-2">
                {publications.map((snapshot) => (
                  <button
                    key={snapshot.id}
                    onClick={() => setSelectedSnapshot(snapshot)}
                    className={cx(
                      "w-full rounded-2xl border px-4 py-3 text-left transition",
                      selectedSnapshot?.id === snapshot.id ? "border-cyan-300/30 bg-cyan-400/10" : "border-white/10 bg-white/5 hover:bg-white/8",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1 break-words font-medium text-white">{snapshot.apiOntology.name}</div>
                      <Badge tone={statusTone(snapshot.status)} className="shrink-0">
                        {snapshot.status}
                      </Badge>
                    </div>
                    <div className="mt-1 break-words text-xs text-slate-400">{joinItems([snapshot.scope, snapshot.environment, timestamp(snapshot.publishedAt)])}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              {selectedSnapshot ? (
                <>
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <Metric label="Snapshot" value={shortId(selectedSnapshot.configSnapshotId)} hint="Published bundle id" />
                    <Metric label="Status" value={selectedSnapshot.status.toUpperCase()} hint={selectedSnapshot.releaseNotes || "No release notes"} />
                    <Metric label="Published" value={timestamp(selectedSnapshot.publishedAt)} hint={selectedSnapshot.publishedBy} />
                  </div>
                  <Card className="space-y-3">
                    <div className="label">Snapshot details</div>
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                        <div className="font-medium text-white">{selectedSnapshot.apiOntology.name}</div>
                        <div className="mt-1 text-xs text-slate-400">{joinItems([`v${selectedSnapshot.apiOntology.version}`, selectedSnapshot.apiOntology.status])}</div>
                      </div>
                      <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                        <div className="font-medium text-white">{selectedSnapshot.memoryOntology.name}</div>
                        <div className="mt-1 text-xs text-slate-400">{joinItems([`v${selectedSnapshot.memoryOntology.version}`, selectedSnapshot.memoryOntology.status])}</div>
                      </div>
                      <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                        <div className="font-medium text-white">{selectedSnapshot.policyProfile.name}</div>
                        <div className="mt-1 text-xs text-slate-400">{joinItems([`v${selectedSnapshot.policyProfile.version}`, selectedSnapshot.policyProfile.status])}</div>
                      </div>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-sm text-slate-300">
                      {selectedSnapshot.releaseNotes || "No release notes provided."}
                    </div>
                    <div className="flex items-center gap-3">
                      <Button onClick={() => setConfirmRollback(true)} disabled={!canRollback(session?.user.role)}>
                        Roll back snapshot
                      </Button>
                      <Badge tone="accent">{selectedSnapshot.scope}</Badge>
                    </div>
                  </Card>
                </>
              ) : (
                <p className="text-sm text-slate-400">Select a publication snapshot to roll back to.</p>
              )}
            </div>
          </div>
          {statusMessage ? <p className="text-sm text-cyan-200">{statusMessage}</p> : null}
        </Card>
      )}

      <ConfirmGate
        title="Rollback active runtime snapshot?"
        body="This will reactivate the selected bundle for future events without mutating historical audit data."
        open={confirmRollback}
        confirmLabel="Rollback snapshot"
        danger
        onCancel={() => setConfirmRollback(false)}
        onConfirm={() => {
          void rollback();
        }}
      />
    </Section>
  );
}

export function DecisionExplorerWorkspace() {
  const [filters, setFilters] = useState({ scope: "", tenant: "", environment: "", status: "", kind: "", query: "" });
  const [decisions, setDecisions] = useState<DecisionRecord[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      setDecisions(
        await client.decisions.list({
          scope: filters.scope || undefined,
          tenant: filters.tenant || undefined,
          environment: filters.environment || undefined,
          status: filters.status || undefined,
          kind: filters.kind || undefined,
          query: filters.query || undefined,
        }),
      );
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  return (
    <Section eyebrow="Decision explorer" title="Decision explorer">
      {error ? (
        <StateCard title="Decision data unavailable" body={error} action={<Button onClick={() => void refresh()}>Retry</Button>} />
      ) : loading ? (
        <StateCard title="Loading decisions" body="Fetching live decision rows from the backend." />
      ) : (
        <Card className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            <Input placeholder="Scope" value={filters.scope} onChange={(event) => setFilters({ ...filters, scope: event.target.value })} />
            <Input placeholder="Tenant" value={filters.tenant} onChange={(event) => setFilters({ ...filters, tenant: event.target.value })} />
            <Input placeholder="Environment" value={filters.environment} onChange={(event) => setFilters({ ...filters, environment: event.target.value })} />
            <Select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
              <option value="">All statuses</option>
              {["accepted", "overridden", "blocked", "conflicted"].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
            <Input placeholder="Kind" value={filters.kind} onChange={(event) => setFilters({ ...filters, kind: event.target.value })} />
            <Input placeholder="Search reason codes or workflows" value={filters.query} onChange={(event) => setFilters({ ...filters, query: event.target.value })} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Results" value={String(decisions.length)} hint="Filtered decisions" />
            <Metric label="Blocked" value={String(decisions.filter((item) => item.status === "blocked").length)} hint="Sensitivity or safety blocks" />
            <Metric label="Conflicted" value={String(decisions.filter((item) => item.status === "conflicted").length)} hint="Canonicalization unresolved" />
            <Metric label="Overridden" value={String(decisions.filter((item) => item.status === "overridden").length)} hint="Operator or tenant override" />
          </div>

          <div className="space-y-2">
            {decisions.map((decision) => (
              <div key={decision.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="break-words font-medium text-white">{decision.title}</div>
                    <div className="mt-1 break-words text-xs text-slate-400">
                      {joinItems([
                        decision.action,
                        decision.sourceSystem ?? null,
                        decision.httpMethod ?? null,
                        decision.routeTemplate ?? null,
                        decision.scope,
                        decision.tenant,
                        decision.environment,
                      ])}
                    </div>
                  </div>
                  <Badge tone={statusTone(decision.status)} className="shrink-0">
                    {decision.status}
                  </Badge>
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                    <div className="label">Reason code</div>
                    <div className="mt-1 text-sm text-white">{decision.reasonCode}</div>
                    {decision.reasonCodes?.length ? <div className="mt-2 text-xs text-slate-400">{decision.reasonCodes.join(" · ")}</div> : null}
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                    <div className="label">Config snapshot</div>
                    <div className="mt-1 font-mono text-sm text-white">{shortId(decision.configSnapshotId)}</div>
                    <div className="mt-2 text-xs text-slate-400">{decision.documentVersion ?? "n/a"}</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                    <div className="label">Evidence</div>
                    <div className="mt-1 text-sm text-white">{decision.evidence}</div>
                    {decision.evidenceCount ? <div className="mt-2 text-xs text-slate-400">{decision.evidenceCount} evidence item(s)</div> : null}
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                    <div className="label">Workflow context</div>
                    <div className="mt-1 text-sm text-white">
                      {joinItems([decision.moduleKey ?? null, decision.workflowKey ?? null]) || "No workflow"}
                    </div>
                    <div className="mt-2 text-xs text-slate-400">
                      {joinItems([decision.observedEntryId ?? null, decision.relatedApiIds?.length ? `${decision.relatedApiIds.length} related APIs` : null]) || "Standalone API match"}
                    </div>
                    {decision.relatedApiIds?.length ? (
                      <div className="mt-2 break-words text-xs text-slate-400">{decision.relatedApiIds.join(" · ")}</div>
                    ) : null}
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                    <div className="label">Inference</div>
                    <div className="mt-1 text-sm text-white">
                      {decision.inferenceInvoked
                        ? joinItems([
                            decision.inferenceProvider ?? null,
                            decision.modelName ?? null,
                            decision.modelRecommendation ?? null,
                            decision.modelConfidence != null ? decision.modelConfidence.toFixed(2) : null,
                          ])
                        : "not invoked"}
                    </div>
                    <div className="mt-2 text-xs text-slate-400">
                      {joinItems([decision.promptTemplateKey ?? null, decision.promptVersion ?? null, decision.documentKind ?? "runtime decision"])}
                    </div>
                  </div>
                </div>
                {decision.reasoningSummary ? (
                  <div className="mt-3 rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                    <div className="label">Reasoning summary</div>
                    <div className="mt-1 text-sm text-white">{decision.reasoningSummary}</div>
                  </div>
                ) : null}
                {decision.intentSummary ? (
                  <div className="mt-3 rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                    <div className="label">Intent summary</div>
                    <div className="mt-1 text-sm text-white">{decision.intentSummary}</div>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </Card>
      )}
    </Section>
  );
}

export function MemoryBrowserWorkspace() {
  const session = useConsoleSession();
  const [filters, setFilters] = useState({ tenant: "all", user: session?.user.email ?? "", scope: "", environment: "", type: "", status: "", query: "" });
  const [memories, setMemories] = useState<MemoryRecord[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    if (!filters.tenant || !filters.user) {
      setMemories([]);
      setError("Enter a tenant and user to query live memory records.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setMemories(
        await client.memories.list({
          tenant: filters.tenant || undefined,
          user: filters.user || undefined,
          scope: filters.scope || undefined,
          environment: filters.environment || undefined,
          type: filters.type || undefined,
          status: filters.status || undefined,
          query: filters.query || undefined,
        }),
      );
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  return (
    <Section eyebrow="Memory browser" title="User memory browser">
      {error ? (
        <StateCard title="Memory data unavailable" body={error} action={<Button onClick={() => void refresh()}>Retry</Button>} />
      ) : loading ? (
        <StateCard title="Loading memories" body="Fetching live memory records from the backend." />
      ) : (
        <Card className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Input placeholder="Tenant" value={filters.tenant} onChange={(event) => setFilters({ ...filters, tenant: event.target.value })} />
            <Input placeholder="User" value={filters.user} onChange={(event) => setFilters({ ...filters, user: event.target.value })} />
            <Input placeholder="Scope" value={filters.scope} onChange={(event) => setFilters({ ...filters, scope: event.target.value })} />
            <Input placeholder="Environment" value={filters.environment} onChange={(event) => setFilters({ ...filters, environment: event.target.value })} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <Input placeholder="Memory type" value={filters.type} onChange={(event) => setFilters({ ...filters, type: event.target.value })} />
            <Select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
              <option value="">All statuses</option>
              {["active", "blocked", "deleted"].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
            <Input placeholder="Search title, evidence, or workflow" value={filters.query} onChange={(event) => setFilters({ ...filters, query: event.target.value })} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Visible" value={String(memories.filter((item) => item.status !== "deleted").length)} hint="Retrieval-visible memories" />
            <Metric label="Active" value={String(memories.filter((item) => item.status === "active").length)} hint="Durable memory entries" />
            <Metric label="Blocked" value={String(memories.filter((item) => item.status === "blocked").length)} hint="Safety suppressed" />
            <Metric label="Avg confidence" value={`${Math.round((memories.reduce((sum, item) => sum + item.confidence, 0) / Math.max(memories.length, 1)) * 100)}%`} hint="Live backend confidence" />
          </div>

          <div className="space-y-2">
            {memories.map((memory) => (
              <div key={memory.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="break-words font-medium text-white">{memory.title}</div>
                    <div className="mt-1 break-words text-xs text-slate-400">
                      {joinItems([memory.type, memory.scope, memory.tenant, memory.environment, timestamp(memory.timestamp)])}
                    </div>
                  </div>
                  <Badge tone={statusTone(memory.status)} className="shrink-0">
                    {memory.status}
                  </Badge>
                </div>
                <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                    <div className="label">Summary</div>
                    <div className="mt-1 text-sm text-white">{memory.summary}</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                    <div className="label">Evidence</div>
                    <div className="mt-1 text-sm text-white">{memory.evidence}</div>
                    {memory.evidenceCount ? <div className="mt-2 text-xs text-slate-400">{memory.evidenceCount} evidence item(s)</div> : null}
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                    <div className="label">Config snapshot</div>
                    <div className="mt-1 font-mono text-sm text-white">{shortId(memory.configSnapshotId)}</div>
                    {memory.sourcePrecedenceKey ? <div className="mt-2 text-xs text-slate-400">{memory.sourcePrecedenceKey} · {memory.sourcePrecedenceScore}</div> : null}
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                    <div className="label">Workflow context</div>
                    <div className="mt-1 text-sm text-white">{memory.workflowKey ?? "No workflow"}</div>
                    <div className="mt-2 text-xs text-slate-400">
                      {joinItems([
                        memory.observedApiName ?? null,
                        memory.evidenceEventIds?.length ? `${memory.evidenceEventIds.length} event ids` : null,
                      ]) || "Standalone memory"}
                    </div>
                    {memory.relatedApiIds?.length ? (
                      <div className="mt-2 break-words text-xs text-slate-400">{memory.relatedApiIds.join(" · ")}</div>
                    ) : null}
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                    <div className="label">Canonical key</div>
                    <div className="mt-1 text-sm text-white">{memory.canonicalKey ?? "n/a"}</div>
                    {memory.reasonCodes?.length ? <div className="mt-2 text-xs text-slate-400">{memory.reasonCodes.join(" · ")}</div> : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </Section>
  );
}

export function AuditLogWorkspace() {
  const [records, setRecords] = useState<Awaited<ReturnType<typeof client.audit.list>>>([]);
  const [filters, setFilters] = useState({ scope: "", tenant: "", environment: "", kind: "", action: "", query: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      setRecords(
        await client.audit.list({
          scope: filters.scope || undefined,
          tenant: filters.tenant || undefined,
          environment: filters.environment || undefined,
          kind: filters.kind || undefined,
          action: filters.action || undefined,
          query: filters.query || undefined,
        }),
      );
    } catch (requestError) {
      setError(formatError(requestError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  return (
    <Section eyebrow="Audit log" title="Audit log viewer">
      {error ? (
        <StateCard title="Audit log unavailable" body={error} action={<Button onClick={() => void refresh()}>Retry</Button>} />
      ) : loading ? (
        <StateCard title="Loading audit log" body="Fetching live audit rows from the backend." />
      ) : (
        <Card className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            <Input placeholder="Scope" value={filters.scope} onChange={(event) => setFilters({ ...filters, scope: event.target.value })} />
            <Input placeholder="Tenant" value={filters.tenant} onChange={(event) => setFilters({ ...filters, tenant: event.target.value })} />
            <Input placeholder="Environment" value={filters.environment} onChange={(event) => setFilters({ ...filters, environment: event.target.value })} />
            <Input placeholder="Kind" value={filters.kind} onChange={(event) => setFilters({ ...filters, kind: event.target.value })} />
            <Select value={filters.action} onChange={(event) => setFilters({ ...filters, action: event.target.value })}>
              <option value="">All actions</option>
              {["save", "validate", "approve", "publish", "rollback", "archive"].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
            <Input placeholder="Search" value={filters.query} onChange={(event) => setFilters({ ...filters, query: event.target.value })} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Events" value={String(records.length)} hint="Logged operator actions" />
            <Metric label="Publishes" value={String(records.filter((item) => item.action === "publish").length)} hint="Config publication events" />
            <Metric label="Rollbacks" value={String(records.filter((item) => item.action === "rollback").length)} hint="Snapshot rollbacks" />
            <Metric label="Validations" value={String(records.filter((item) => item.action === "validate").length)} hint="Validation runs" />
          </div>

          <div className="overflow-x-auto rounded-2xl border border-white/10">
            <table className="min-w-[960px] divide-y divide-white/10 text-left text-sm">
              <thead className="bg-white/5 text-xs uppercase tracking-[0.18em] text-slate-400">
                <tr>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Document</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Snapshot</th>
                  <th className="px-4 py-3">Checksums</th>
                  <th className="px-4 py-3">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {records.map((record) => (
                  <tr key={record.id} className="bg-slate-950/20">
                    <td className="px-4 py-3 text-white">{record.actor}</td>
                    <td className="px-4 py-3">
                      <Badge tone="accent">{record.role}</Badge>
                    </td>
                    <td className="px-4 py-3 text-slate-300">
                      <div>{record.documentName ?? record.documentKind}</div>
                      <div className="mt-1 text-xs text-slate-500">{joinItems([record.scope, record.tenant, record.environment])}</div>
                    </td>
                    <td className="px-4 py-3 text-white">{record.action}</td>
                    <td className="px-4 py-3 text-slate-300">
                      <div className="font-mono text-xs text-cyan-100">{record.snapshotId ?? record.documentVersion}</div>
                      <div className="mt-1 text-xs text-slate-500">{record.releaseNotes ?? "n/a"}</div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-cyan-100">
                      {joinItems([record.beforeChecksum, record.afterChecksum]) || record.diffRef}
                    </td>
                    <td className="px-4 py-3 text-slate-400">{timestamp(record.timestamp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </Section>
  );
}
