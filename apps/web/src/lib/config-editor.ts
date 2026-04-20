import type {
  APIOntologyEntry,
  APIOntologyIntentRule,
  APIOntologyModule,
  APIOntologyPackage,
  APIOntologyWorkflowDefinition,
  APIOntologyWorkflowEdge,
  ConfigDocument,
} from "./api/types";

export type EditorFormat = "yaml" | "json";

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" ? value : fallback;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function parseApiEntry(value: unknown, moduleKey?: string): APIOntologyEntry | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }
  const apiName = asString(record.api_name);
  if (!apiName) {
    return null;
  }
  const eventMatch = asRecord(record.event_match);
  const normalizationRules = asRecord(record.normalization_rules);
  const evidenceCapturePolicy = asRecord(record.evidence_capture_policy);
  return {
    entry_id: asString(record.entry_id, apiName),
    module_key: asString(record.module_key, moduleKey ?? ""),
    api_name: apiName,
    enabled: asBoolean(record.enabled, true),
    capability_family: asString(record.capability_family),
    method_semantics: asString(record.method_semantics),
    domain: asString(record.domain),
    description: asString(record.description),
    candidate_memory_types: asStringArray(record.candidate_memory_types),
    default_action: asString(record.default_action),
    repeat_policy: asString(record.repeat_policy),
    sensitivity_hint: asString(record.sensitivity_hint),
    source_trust: asNumber(record.source_trust),
    source_precedence_key: asString(record.source_precedence_key),
    extractors: asStringArray(record.extractors),
    relation_templates: asStringArray(record.relation_templates),
    dedup_strategy_hint: asString(record.dedup_strategy_hint),
    conflict_strategy_hint: asString(record.conflict_strategy_hint),
    tenant_override_allowed: asBoolean(record.tenant_override_allowed, true),
    event_match: {
      source_system: asString(eventMatch?.source_system),
      http_method: asString(eventMatch?.http_method),
      route_template: asString(eventMatch?.route_template),
    },
    request_field_selectors: asStringArray(record.request_field_selectors),
    response_field_selectors: asStringArray(record.response_field_selectors),
    normalization_rules: {
      primary_fact_source: asString(normalizationRules?.primary_fact_source, "request_then_response"),
    },
    evidence_capture_policy: {
      request: asString(evidenceCapturePolicy?.request, "summary_only"),
      response: asString(evidenceCapturePolicy?.response, "summary_only"),
    },
    llm_usage_mode: asString(record.llm_usage_mode, "DISABLED"),
    prompt_template_key:
      typeof record.prompt_template_key === "string" || record.prompt_template_key === null
        ? (record.prompt_template_key as string | null)
        : null,
    llm_allowed_field_paths: asStringArray(record.llm_allowed_field_paths),
    llm_blocked_field_paths: asStringArray(record.llm_blocked_field_paths),
    notes:
      typeof record.notes === "string" || record.notes === null
        ? (record.notes as string | null)
        : null,
  };
}

function parseApiModule(value: unknown): APIOntologyModule | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }
  const moduleKey = asString(record.module_key);
  if (!moduleKey) {
    return null;
  }
  return {
    module_key: moduleKey,
    title: asString(record.title, moduleKey),
    description: asString(record.description),
    entries: Array.isArray(record.entries)
      ? record.entries
          .map((entry) => parseApiEntry(entry, moduleKey))
          .filter((entry): entry is APIOntologyEntry => Boolean(entry))
      : [],
  };
}

function parseWorkflowEdge(value: unknown): APIOntologyWorkflowEdge | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }
  const fromEntryId = asString(record.from_entry_id);
  const toEntryId = asString(record.to_entry_id);
  const edgeType = asString(record.edge_type);
  if (!fromEntryId || !toEntryId || !edgeType) {
    return null;
  }
  return {
    from_entry_id: fromEntryId,
    to_entry_id: toEntryId,
    edge_type: edgeType,
  };
}

function parseIntentRule(value: unknown): APIOntologyIntentRule | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }
  const observedEntryIds = asStringArray(record.observed_entry_ids);
  const summary = asString(record.summary);
  if (!observedEntryIds.length || !summary) {
    return null;
  }
  return {
    observed_entry_ids: observedEntryIds,
    summary,
  };
}

function parseWorkflow(value: unknown): APIOntologyWorkflowDefinition | null {
  const record = asRecord(value);
  if (!record) {
    return null;
  }
  const workflowKey = asString(record.workflow_key);
  if (!workflowKey) {
    return null;
  }
  return {
    workflow_key: workflowKey,
    title: asString(record.title, workflowKey),
    description: asString(record.description),
    participant_entry_ids: asStringArray(record.participant_entry_ids),
    relationship_edges: Array.isArray(record.relationship_edges)
      ? record.relationship_edges
          .map(parseWorkflowEdge)
          .filter((edge): edge is APIOntologyWorkflowEdge => Boolean(edge))
      : [],
    intent_memory_type: asString(record.intent_memory_type),
    default_intent_summary: asString(record.default_intent_summary),
    intent_rules: Array.isArray(record.intent_rules)
      ? record.intent_rules
          .map(parseIntentRule)
          .filter((rule): rule is APIOntologyIntentRule => Boolean(rule))
      : [],
  };
}

export function parseApiOntologyPackage(
  definitionJson?: Record<string, unknown> | null,
): APIOntologyPackage | null {
  const record = definitionJson ?? null;
  if (!record) {
    return null;
  }
  const documentName = asString(record.document_name, "API Ontology");
  const modules = Array.isArray(record.modules)
    ? record.modules
        .map(parseApiModule)
        .filter((module): module is APIOntologyModule => Boolean(module))
    : [];
  if (modules.length > 0) {
    return {
      document_name: documentName,
      modules,
      workflows: Array.isArray(record.workflows)
        ? record.workflows
            .map(parseWorkflow)
            .filter((workflow): workflow is APIOntologyWorkflowDefinition => Boolean(workflow))
        : [],
    };
  }
  const legacyEntries = Array.isArray(record.entries)
    ? record.entries
        .map((entry) => parseApiEntry(entry, "legacy.default"))
        .filter((entry): entry is APIOntologyEntry => Boolean(entry))
    : [];
  return {
    document_name: documentName,
    modules:
      legacyEntries.length > 0
        ? [
            {
              module_key: "legacy.default",
              title: "Legacy API Ontology",
              description: "Implicit module created from legacy entries[] authoring.",
              entries: legacyEntries,
            },
          ]
        : [],
    workflows: Array.isArray(record.workflows)
      ? record.workflows
          .map(parseWorkflow)
          .filter((workflow): workflow is APIOntologyWorkflowDefinition => Boolean(workflow))
      : [],
  };
}

export function serializeApiOntologyPackage(pkg: APIOntologyPackage) {
  return JSON.stringify(pkg, null, 2);
}

export function hasPackageDraftChanges({
  active,
  editor,
}: {
  active: APIOntologyPackage | null;
  editor: APIOntologyPackage | null;
}) {
  if (!active || !editor) {
    return false;
  }
  return serializeApiOntologyPackage(active) !== serializeApiOntologyPackage(editor);
}

export function serializeDocumentSource(
  document: Pick<ConfigDocument, "yaml" | "definitionJson">,
  format: EditorFormat,
) {
  if (format === "json") {
    return JSON.stringify(document.definitionJson ?? {}, null, 2);
  }
  return document.yaml;
}

export function hasConfigDraftChanges({
  active,
  editor,
  sourceText,
  sourceFormat,
}: {
  active: ConfigDocument | null;
  editor: ConfigDocument | null;
  sourceText: string;
  sourceFormat: EditorFormat;
}) {
  if (!active || !editor) {
    return false;
  }

  if (
    active.name !== editor.name ||
    active.scope !== editor.scope ||
    active.tenant !== editor.tenant
  ) {
    return true;
  }

  return serializeDocumentSource(active, sourceFormat) !== sourceText;
}

export function sourceLineCount(value: string) {
  if (!value) {
    return 0;
  }
  return value.split(/\r?\n/).length;
}
