export type ConfigKind = "api-ontology" | "memory-ontology" | "policy-profile";

export type ConfigStatus = "draft" | "validated" | "approved" | "published" | "archived";

export type DecisionStatus = "accepted" | "overridden" | "blocked" | "conflicted";

export interface APIOntologyEntry {
  entry_id: string;
  module_key?: string;
  api_name: string;
  enabled: boolean;
  capability_family: string;
  method_semantics: string;
  domain: string;
  description: string;
  candidate_memory_types: string[];
  default_action: string;
  repeat_policy: string;
  sensitivity_hint: string;
  source_trust: number;
  source_precedence_key: string;
  extractors: string[];
  relation_templates: string[];
  dedup_strategy_hint: string;
  conflict_strategy_hint: string;
  tenant_override_allowed: boolean;
  event_match: {
    source_system: string;
    http_method: string;
    route_template: string;
  };
  request_field_selectors: string[];
  response_field_selectors: string[];
  normalization_rules: {
    primary_fact_source: string;
  };
  evidence_capture_policy: {
    request: string;
    response: string;
  };
  llm_usage_mode: string;
  prompt_template_key?: string | null;
  llm_allowed_field_paths: string[];
  llm_blocked_field_paths: string[];
  notes?: string | null;
}

export interface APIOntologyModule {
  module_key: string;
  title: string;
  description: string;
  entries: APIOntologyEntry[];
}

export interface APIOntologyWorkflowEdge {
  from_entry_id: string;
  to_entry_id: string;
  edge_type: string;
}

export interface APIOntologyIntentRule {
  observed_entry_ids: string[];
  summary: string;
}

export interface APIOntologyWorkflowDefinition {
  workflow_key: string;
  title: string;
  description: string;
  participant_entry_ids: string[];
  relationship_edges: APIOntologyWorkflowEdge[];
  intent_memory_type: string;
  default_intent_summary: string;
  intent_rules: APIOntologyIntentRule[];
}

export interface APIOntologyPackage {
  document_name: string;
  modules: APIOntologyModule[];
  workflows: APIOntologyWorkflowDefinition[];
}

export interface Session {
  token: string;
  user: {
    email: string;
    displayName: string;
    role: "viewer" | "editor" | "approver" | "operator" | "admin";
  };
}

export interface ConfigDocument {
  id: string;
  kind: ConfigKind;
  name: string;
  version: number;
  status: ConfigStatus;
  tenant: string;
  scope: string;
  environment: string;
  baseVersion?: number | null;
  createdAt?: string;
  approvedAt?: string | null;
  publishedAt?: string | null;
  updatedAt: string;
  lastPublishedAt?: string;
  summary: string;
  yaml: string;
  definitionJson?: Record<string, unknown>;
  apiOntologyPackage?: APIOntologyPackage | null;
  releaseNotes?: string;
  snapshotId?: string | null;
  snapshotHash?: string | null;
  sourcePrecedenceKey?: string | null;
  sourcePrecedenceScore?: number | null;
  previousYaml?: string;
}

export interface ValidationCheck {
  name: string;
  status: "pass" | "warn" | "fail";
  detail: string;
}

export interface ValidationRun {
  id: string;
  documentId: string;
  documentName: string;
  status: "pass" | "warn" | "fail";
  timestamp: string;
  summary: string;
  checks: ValidationCheck[];
  issues: string[];
}

export interface SimulationRun {
  id: string;
  documentId: string;
  sampleEvent: string;
  timestamp: string;
  beforeDecision: string;
  afterDecision: string;
  reasonCodes: string[];
  inferenceInvoked?: boolean;
  modelRecommendation?: string | null;
  modelConfidence?: number | null;
  policyOverride?: string | null;
  activeSnapshotId?: string | null;
  candidateSnapshotId?: string | null;
  changedMemoryCandidates?: string[];
  expectedWriteDelta?: number;
  expectedBlockDelta?: number;
  diff: string;
}

export interface PublicationSnapshot {
  id: string;
  documentId?: string;
  documentName?: string;
  version?: number;
  createdAt?: string;
  createdBy?: string;
  note?: string;
  configSnapshotId: string;
  snapshotHash: string;
  scope: string;
  tenant: string | null;
  environment: string;
  status: "active" | "rolled-back" | "archived";
  publishedAt: string;
  publishedBy: string;
  rollbackOf?: string | null;
  releaseNotes: string;
  apiOntology: PublicationBundleDocument;
  memoryOntology: PublicationBundleDocument;
  policyProfile: PublicationBundleDocument;
}

export interface PublicationBundleDocument {
  id: string;
  name: string;
  version: number;
  kind: ConfigKind;
  status: ConfigStatus;
}

export interface DecisionRecord {
  id: string;
  title: string;
  action: string;
  status: DecisionStatus;
  kind?: string;
  scope: string;
  tenant: string;
  environment: string;
  reasonCode: string;
  reasonCodes?: string[];
  configSnapshotId: string;
  evidence: string;
  evidenceCount?: number;
  documentVersion?: string;
  documentKind?: string;
  sourceSystem?: string;
  httpMethod?: string;
  routeTemplate?: string;
  inferenceInvoked?: boolean;
  inferenceProvider?: string | null;
  modelName?: string | null;
  promptTemplateKey?: string | null;
  promptVersion?: string | null;
  modelRecommendation?: string | null;
  modelConfidence?: number | null;
  reasoningSummary?: string | null;
  observedEntryId?: string | null;
  moduleKey?: string | null;
  workflowKey?: string | null;
  relatedApiIds?: string[];
  intentSummary?: string | null;
  timestamp: string;
}

export interface MemoryRecord {
  id: string;
  title: string;
  type: string;
  confidence: number;
  summary: string;
  scope: string;
  tenant: string;
  environment?: string;
  status: "active" | "blocked" | "deleted";
  evidence: string;
  evidenceCount?: number;
  configSnapshotId: string;
  sourcePrecedenceKey?: string;
  sourcePrecedenceScore?: number;
  canonicalKey?: string;
  reasonCodes?: string[];
  payload?: Record<string, unknown>;
  workflowKey?: string | null;
  relatedApiIds?: string[];
  observedApiName?: string | null;
  evidenceEventIds?: string[];
  timestamp: string;
}

export interface AuditRecord {
  id: string;
  actor: string;
  role: string;
  scope?: string;
  tenant?: string;
  environment?: string;
  documentKind: string;
  documentVersion: string;
  documentName?: string;
  action: string;
  snapshotId?: string;
  beforeChecksum?: string;
  afterChecksum?: string;
  releaseNotes?: string;
  approvedAt?: string | null;
  publishedAt?: string | null;
  timestamp: string;
  diffRef: string;
}

export interface DemoState {
  session: Session | null;
  configs: ConfigDocument[];
  validations: ValidationRun[];
  simulations: SimulationRun[];
  publications: PublicationSnapshot[];
  decisions: DecisionRecord[];
  memories: MemoryRecord[];
  audits: AuditRecord[];
}
