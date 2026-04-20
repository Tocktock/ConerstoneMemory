import type {
  AuditRecord,
  ConfigDocument,
  ConfigKind,
  DecisionRecord,
  MemoryRecord,
  PublicationSnapshot,
  Session,
  SimulationRun,
  ValidationRun,
} from "@/lib/api/types";
import { parseApiOntologyPackage } from "@/lib/config-editor";

type RequestOptions = RequestInit & {
  skipAuth?: boolean;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_MEMORYENGINE_API_BASE_URL?.replace(/\/$/, "");
const SESSION_STORAGE_KEY = "memoryengine-session-v1";

type BackendConfig = {
  id: string;
  kind: string;
  name: string;
  version: number;
  status: string;
  scope: string;
  tenant_id?: string | null;
  environment?: string | null;
  base_version?: number | null;
  created_at?: string | null;
  approved_at?: string | null;
  published_at?: string | null;
  checksum: string;
  definition_json: Record<string, unknown>;
  definition_yaml: string;
  summary?: string | null;
  release_notes?: string | null;
  snapshot_id?: string | null;
  snapshot_hash?: string | null;
  source_precedence_key?: string | null;
  source_precedence_score?: number | null;
  created_by: string;
  updated_at: string;
  approved_by?: string | null;
  published_by?: string | null;
};

type BackendValidationIssue = {
  id: string;
  severity: string;
  path: string;
  code: string;
  message: string;
  document_id?: string | null;
};

type BackendValidationResponse = {
  status: "pass" | "warn" | "fail";
  validated_document_ids: string[];
  issues: BackendValidationIssue[];
};

type BackendSimulationResponse = {
  active_snapshot_id?: string | null;
  candidate_snapshot_id?: string | null;
  old_decision?: Record<string, unknown> | null;
  new_decision: Record<string, unknown>;
  changed_reason_codes: string[];
  changed_memory_candidates: string[];
  expected_write_delta: number;
  expected_block_delta: number;
};

type BackendPublication = {
  id: string;
  environment: string;
  scope: string;
  tenant_id?: string | null;
  snapshot_hash: string;
  is_active: boolean;
  published_by: string;
  published_at: string;
  rollback_of?: string | null;
  release_notes?: string | null;
  api_ontology_document_id: string;
  api_ontology_document_name?: string | null;
  api_ontology_document_version?: number | null;
  memory_ontology_document_id: string;
  memory_ontology_document_name?: string | null;
  memory_ontology_document_version?: number | null;
  policy_profile_document_id: string;
  policy_profile_document_name?: string | null;
  policy_profile_document_version?: number | null;
};

type BackendDecision = {
  id: string;
  title: string;
  action: string;
  status: string;
  kind?: string;
  scope: string;
  tenant: string;
  environment: string;
  reason_code: string;
  reason_codes?: string[];
  config_snapshot_id: string;
  evidence: string;
  evidence_count?: number;
  document_version?: string;
  document_kind?: string;
  source_system?: string;
  http_method?: string;
  route_template?: string;
  inference_invoked?: boolean;
  inference_provider?: string | null;
  model_name?: string | null;
  prompt_template_key?: string | null;
  prompt_version?: string | null;
  model_recommendation?: string | null;
  model_confidence?: number | null;
  reasoning_summary?: string | null;
  observed_entry_id?: string | null;
  module_key?: string | null;
  workflow_key?: string | null;
  related_api_ids?: string[];
  intent_summary?: string | null;
  timestamp: string;
};

type BackendMemory = {
  record_type: string;
  record_id: string;
  memory_type: string;
  title: string;
  state: string;
  confidence: number;
  importance: number;
  sensitivity: string;
  config_snapshot_id: string;
  evidence_count: number;
  source_precedence_key?: string;
  source_precedence_score?: number;
  canonical_key?: string;
  reason_codes?: string[];
  environment?: string;
  scope?: string;
  tenant_id?: string;
  payload: Record<string, unknown>;
  protected_value_encrypted?: string | null;
};

type BackendAudit = {
  id: string;
  actor: string;
  role: string;
  action: string;
  document_kind: string;
  document_version: string;
  document_name?: string;
  scope?: string;
  tenant?: string;
  tenant_id?: string;
  environment?: string;
  snapshot_id?: string;
  before_checksum?: string;
  after_checksum?: string;
  release_notes?: string;
  approved_at?: string | null;
  published_at?: string | null;
  timestamp: string;
  diff_ref: unknown;
};

type ConfigListFilters = {
  scope?: string;
  environment?: string;
  tenant?: string;
  status?: string;
};

type PublicationFilters = ConfigListFilters & {
  kind?: string;
};

type DecisionFilters = {
  scope?: string;
  environment?: string;
  tenant?: string;
  status?: string;
  kind?: string;
  query?: string;
};

type MemoryFilters = {
  scope?: string;
  environment?: string;
  tenant?: string;
  user?: string;
  status?: string;
  type?: string;
  query?: string;
};

type AuditFilters = {
  scope?: string;
  environment?: string;
  tenant?: string;
  status?: string;
  kind?: string;
  action?: string;
  query?: string;
};

type PublishRequest = {
  api_ontology_document_id: string;
  memory_ontology_document_id: string;
  policy_profile_document_id: string;
  environment: string;
  scope: string;
  tenant_id?: string | null;
  release_notes: string;
};

type RollbackRequest = {
  snapshot_id: string;
};

type ValidateRequest = {
  config_id?: string;
  api_ontology_document_id?: string;
  memory_ontology_document_id?: string;
  policy_profile_document_id?: string;
  environment?: string;
  tenant_id?: string | null;
};

type ImportPayload = {
  kind: string;
  format: "yaml" | "json";
  yaml?: string;
  json?: Record<string, unknown>;
  definition_yaml?: string;
  definition_json?: Record<string, unknown>;
};

function toBackendKind(kind: ConfigKind): string {
  return kind.replace(/-/g, "_");
}

function toFrontendKind(kind: string): ConfigKind {
  return kind.replace(/_/g, "-") as ConfigKind;
}

function deriveSummary(name: string, yaml: string): string {
  const lines = yaml
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !line.startsWith("document_name:") && !line.startsWith("profile_name:"));
  return lines[0] ?? `${name} configuration document`;
}

function safeJsonParse(value: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(value);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    // Keep the raw JSON string if parsing fails.
  }
  return null;
}

function buildSearchParams(filters: Record<string, string | number | boolean | null | undefined>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  return search;
}

function toSession(data: any): Session {
  return {
    token: data.token ?? "",
    user: {
      email: data.user.email,
      displayName: data.user.display_name ?? data.user.displayName ?? data.user.email,
      role: data.user.role,
    },
  };
}

class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

class BackendUnavailableError extends ApiError {
  constructor(message: string) {
    super(message, 503);
    this.name = "BackendUnavailableError";
  }
}

class UnauthorizedError extends ApiError {
  constructor(message = "Unauthorized") {
    super(message, 401);
    this.name = "UnauthorizedError";
  }
}

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readStoredSession(): Session | null {
  if (!canUseStorage()) {
    return null;
  }
  const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as Session;
  } catch {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
    return null;
  }
}

function writeStoredSession(session: Session | null) {
  if (!canUseStorage()) {
    return;
  }
  if (session) {
    window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
    return;
  }
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
}

function buildHeaders(options: RequestOptions): Headers {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData) && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  if (!options.skipAuth) {
    const token = readStoredSession()?.token;
    if (token && !headers.has("authorization")) {
      headers.set("authorization", `Bearer ${token}`);
    }
  }
  return headers;
}

async function buildApiError(response: Response): Promise<ApiError> {
  const body = (await response.text()).trim();
  const message = body || `Request failed: ${response.status}`;
  if (response.status === 401) {
    return new UnauthorizedError(message);
  }
  return new ApiError(message, response.status);
}

function toConfigDocument(data: BackendConfig, previousYaml?: string): ConfigDocument {
  return {
    id: data.id,
    kind: toFrontendKind(data.kind),
    name: data.name,
    version: data.version,
    status: data.status as ConfigDocument["status"],
    tenant: data.tenant_id ?? "all",
    scope: data.scope,
    environment: data.environment ?? "dev",
    baseVersion: data.base_version ?? null,
    createdAt: data.created_at ?? data.updated_at,
    approvedAt: data.approved_at ?? null,
    publishedAt: data.published_at ?? null,
    updatedAt: data.updated_at,
    lastPublishedAt: data.published_at ?? undefined,
    summary: data.summary ?? deriveSummary(data.name, data.definition_yaml),
    yaml: data.definition_yaml,
    definitionJson: data.definition_json,
    apiOntologyPackage: data.kind === "api_ontology" ? parseApiOntologyPackage(data.definition_json) : null,
    releaseNotes: data.release_notes ?? undefined,
    snapshotId: data.snapshot_id ?? null,
    snapshotHash: data.snapshot_hash ?? null,
    sourcePrecedenceKey: data.source_precedence_key ?? null,
    sourcePrecedenceScore: data.source_precedence_score ?? null,
    previousYaml,
  };
}

function toConfigDocuments(records: BackendConfig[]): ConfigDocument[] {
  const mapped = records.map((record) => toConfigDocument(record));
  const grouped = new Map<string, ConfigDocument[]>();

  for (const document of mapped) {
    const key = [document.kind, document.scope, document.tenant].join("::");
    const current = grouped.get(key) ?? [];
    current.push(document);
    grouped.set(key, current);
  }

  for (const documents of grouped.values()) {
    documents.sort((left, right) => left.version - right.version);
    for (let index = 0; index < documents.length; index += 1) {
      documents[index].previousYaml = index > 0 ? documents[index - 1].yaml : undefined;
    }
  }

  return mapped.sort((left, right) => {
    if (left.kind !== right.kind) return left.kind.localeCompare(right.kind);
    if (left.scope !== right.scope) return left.scope.localeCompare(right.scope);
    if (left.tenant !== right.tenant) return left.tenant.localeCompare(right.tenant);
    return right.version - left.version;
  });
}

function validationChecksFromIssues(issues: BackendValidationIssue[]) {
  if (issues.every((issue) => issue.severity === "info")) {
    return [{ name: "validation", status: "pass" as const, detail: "No validation issues detected." }];
  }
  if (!issues.length) {
    return [{ name: "validation", status: "pass" as const, detail: "No validation issues detected." }];
  }
  return issues.map((issue) => ({
    name: issue.code === "validation.pass" ? "validation" : `${issue.code} @ ${issue.path}`,
    status:
      issue.severity === "error"
        ? ("fail" as const)
        : issue.severity === "info"
          ? ("pass" as const)
          : ("warn" as const),
    detail: issue.message,
  }));
}

function toValidationRun(result: BackendValidationResponse, configId: string): ValidationRun {
  const issues = result.issues.filter((issue) => !issue.document_id || issue.document_id === configId);
  const actionableIssues = issues.filter((issue) => issue.severity !== "info");
  return {
    id: `validation-${configId}`,
    documentId: configId,
    documentName: configId,
    status: result.status,
    timestamp: new Date().toISOString(),
    summary: actionableIssues.length ? `${actionableIssues.length} validation issue(s) reported.` : "No validation issues detected.",
    checks: validationChecksFromIssues(issues),
    issues: actionableIssues.map((issue) => issue.message),
  };
}

function groupValidationRuns(issues: BackendValidationIssue[]): ValidationRun[] {
  const grouped = new Map<string, BackendValidationIssue[]>();
  for (const issue of issues) {
    const documentId = issue.document_id ?? "unknown";
    const current = grouped.get(documentId) ?? [];
    current.push(issue);
    grouped.set(documentId, current);
  }
  return Array.from(grouped.entries()).map(([documentId, documentIssues]) => ({
    id: `validation-${documentId}`,
    documentId,
    documentName: documentId,
    status: documentIssues.some((issue) => issue.severity === "error")
      ? "fail"
      : documentIssues.some((issue) => issue.severity === "warn")
        ? "warn"
        : "pass",
    timestamp: new Date().toISOString(),
    summary: documentIssues.some((issue) => issue.severity !== "info")
      ? `${documentIssues.filter((issue) => issue.severity !== "info").length} validation issue(s) recorded.`
      : "No validation issues detected.",
    checks: validationChecksFromIssues(documentIssues),
    issues: documentIssues.filter((issue) => issue.severity !== "info").map((issue) => issue.message),
  }));
}

function parseSampleEvent(sampleEvent: string) {
  const event = Object.fromEntries(
    sampleEvent
      .split("\n")
      .map((line) => line.split(":").map((part) => part.trim()))
      .filter((parts) => parts.length >= 2)
      .map(([key, ...rest]) => [key, rest.join(": ")])
  );
  const action = String(event.action ?? "docs.openDocument");
  const user = String(event.user ?? "user_ui");
  const base = {
    tenant_id: "tenant_ui",
    user_id: user,
    session_id: "session_ui",
    source_channel: "ui_simulator",
    redaction_policy_version: "v1",
  };
  if (action === "profile.updateAddress") {
    return {
      ...base,
      source_system: "profile_service",
      api_name: action,
      http_method: "POST",
      route_template: "/v1/profile/address",
      request: {
        summary: "User submitted a new primary address",
        selected_fields: { address: "123 Seongsu-ro, Seongdong-gu, Seoul" },
        artifact_ref: null,
      },
      response: {
        status_code: 200,
        summary: "Profile service accepted normalized primary address",
        selected_fields: { normalized_address: "123 Seongsu-ro, Seongdong-gu, Seoul" },
        artifact_ref: null,
      },
    };
  }
  if (action === "search.webSearch") {
    return {
      ...base,
      source_system: "search_service",
      api_name: action,
      http_method: "GET",
      route_template: "/v1/search",
      request: {
        summary: "User searched the web",
        selected_fields: { query: "one off search" },
        artifact_ref: null,
      },
      response: {
        status_code: 200,
        summary: "Search service returned results",
        selected_fields: {},
        artifact_ref: null,
      },
    };
  }
  return {
    ...base,
    source_system: "docs_service",
    api_name: action,
    http_method: "GET",
    route_template: "/v1/docs/{documentId}",
    request: {
      summary: "User opened a document",
      selected_fields: { document_title: "Real Estate Tax Guide" },
      artifact_ref: null,
    },
    response: {
      status_code: 200,
      summary: "Document service returned the content",
      selected_fields: {},
      artifact_ref: null,
    },
  };
}

function toSimulationRun(result: BackendSimulationResponse, configId: string, sampleEvent: string): SimulationRun {
  const llmAssist = (result.new_decision?.llm_assist as Record<string, unknown> | undefined) ?? {};
  const modelRecommendation = typeof llmAssist.recommendation === "string" ? llmAssist.recommendation : null;
  const afterDecision = String(result.new_decision?.action ?? "n/a");
  return {
    id: `simulation-${configId}`,
    documentId: configId,
    sampleEvent,
    timestamp: new Date().toISOString(),
    beforeDecision: String(result.old_decision?.action ?? "n/a"),
    afterDecision,
    inferenceInvoked: Boolean(llmAssist.invoked),
    modelRecommendation,
    modelConfidence: typeof llmAssist.confidence === "number" ? llmAssist.confidence : null,
    policyOverride: modelRecommendation && modelRecommendation !== afterDecision ? afterDecision : null,
    activeSnapshotId: result.active_snapshot_id ?? null,
    candidateSnapshotId: result.candidate_snapshot_id ?? null,
    reasonCodes:
      result.changed_reason_codes.length > 0
        ? result.changed_reason_codes
        : ((result.new_decision?.reason_codes as string[] | undefined) ?? []),
    changedMemoryCandidates: result.changed_memory_candidates,
    expectedWriteDelta: result.expected_write_delta,
    expectedBlockDelta: result.expected_block_delta,
    diff: JSON.stringify(
      {
        before: result.old_decision,
        after: result.new_decision,
        changedMemoryCandidates: result.changed_memory_candidates,
        expectedWriteDelta: result.expected_write_delta,
        expectedBlockDelta: result.expected_block_delta,
      },
      null,
      2,
    ),
  };
}

function normalizeArrayResponse<T>(value: unknown): T[] {
  if (Array.isArray(value)) {
    return value as T[];
  }
  if (value && typeof value === "object") {
    const maybeItems = (value as { items?: unknown }).items;
    if (Array.isArray(maybeItems)) {
      return maybeItems as T[];
    }
  }
  return [];
}

function toPublicationSnapshot(data: BackendPublication): PublicationSnapshot {
  return {
    id: data.id,
    configSnapshotId: data.id,
    snapshotHash: data.snapshot_hash,
    scope: data.scope,
    tenant: data.tenant_id ?? null,
    environment: data.environment,
    status: data.rollback_of ? "rolled-back" : data.is_active ? "active" : "archived",
    publishedAt: data.published_at,
    publishedBy: data.published_by,
    rollbackOf: data.rollback_of ?? null,
    releaseNotes: data.release_notes ?? "",
    apiOntology: {
      id: data.api_ontology_document_id,
      name: data.api_ontology_document_name ?? "API Ontology",
      version: data.api_ontology_document_version ?? 0,
      kind: "api-ontology",
      status: data.is_active ? "published" : "archived",
    },
    memoryOntology: {
      id: data.memory_ontology_document_id,
      name: data.memory_ontology_document_name ?? "Memory Ontology",
      version: data.memory_ontology_document_version ?? 0,
      kind: "memory-ontology",
      status: data.is_active ? "published" : "archived",
    },
    policyProfile: {
      id: data.policy_profile_document_id,
      name: data.policy_profile_document_name ?? "Policy Profile",
      version: data.policy_profile_document_version ?? 0,
      kind: "policy-profile",
      status: data.is_active ? "published" : "archived",
    },
  };
}

function toDecisionRecord(data: BackendDecision): DecisionRecord {
  return {
    id: data.id,
    title: data.title,
    action: data.action,
    status: data.status as DecisionRecord["status"],
    kind: data.kind,
    scope: data.scope,
    tenant: data.tenant,
    environment: data.environment,
    reasonCode: data.reason_code,
    reasonCodes: data.reason_codes,
    configSnapshotId: data.config_snapshot_id,
    evidence: data.evidence,
    evidenceCount: data.evidence_count,
    documentVersion: data.document_version,
    documentKind: data.document_kind,
    sourceSystem: data.source_system,
    httpMethod: data.http_method,
    routeTemplate: data.route_template,
    inferenceInvoked: data.inference_invoked,
    inferenceProvider: data.inference_provider ?? null,
    modelName: data.model_name ?? null,
    promptTemplateKey: data.prompt_template_key ?? null,
    promptVersion: data.prompt_version ?? null,
    modelRecommendation: data.model_recommendation ?? null,
    modelConfidence: data.model_confidence ?? null,
    reasoningSummary: data.reasoning_summary ?? null,
    observedEntryId: data.observed_entry_id ?? null,
    moduleKey: data.module_key ?? null,
    workflowKey: data.workflow_key ?? null,
    relatedApiIds: data.related_api_ids ?? [],
    intentSummary: data.intent_summary ?? null,
    timestamp: data.timestamp,
  };
}

function toMemoryRecord(data: BackendMemory): MemoryRecord {
  const workflowKey =
    typeof data.payload.workflow_key === "string" ? data.payload.workflow_key : null;
  const relatedApiIds = Array.isArray(data.payload.related_api_ids)
    ? data.payload.related_api_ids.filter((item): item is string => typeof item === "string")
    : [];
  const evidenceEventIds = Array.isArray(data.payload.evidence_event_ids)
    ? data.payload.evidence_event_ids.filter((item): item is string => typeof item === "string")
    : [];
  const observedApiName =
    typeof data.payload.observed_api_name === "string" ? data.payload.observed_api_name : null;
  return {
    id: data.record_id,
    title: data.title,
    type: data.memory_type,
    confidence: data.confidence,
    summary:
      (typeof data.payload.summary === "string" && data.payload.summary) ||
      (typeof data.payload.topic === "string" && data.payload.topic) ||
      JSON.stringify(data.payload),
    scope: data.scope ?? "runtime",
    tenant: data.tenant_id ?? "runtime",
    environment: data.environment ?? undefined,
    status:
      data.state === "active" ? "active" : data.state === "deleted" ? "deleted" : ("blocked" as MemoryRecord["status"]),
    evidence: `${data.evidence_count} evidence record(s)`,
    evidenceCount: data.evidence_count,
    configSnapshotId: data.config_snapshot_id,
    sourcePrecedenceKey: data.source_precedence_key,
    sourcePrecedenceScore: data.source_precedence_score,
    canonicalKey: data.canonical_key,
    reasonCodes: data.reason_codes,
    payload: data.payload,
    workflowKey,
    relatedApiIds,
    observedApiName,
    evidenceEventIds,
    timestamp: new Date().toISOString(),
  };
}

function toAuditRecord(data: BackendAudit): AuditRecord {
  const normalizedAction = data.action.startsWith("config.") ? data.action.slice("config.".length) : data.action;
  return {
    id: data.id,
    actor: data.actor,
    role: data.role,
    documentKind: data.document_kind,
    documentVersion: data.document_version,
    documentName: data.document_name,
    action: normalizedAction,
    scope: data.scope,
    tenant: data.tenant ?? data.tenant_id,
    environment: data.environment,
    snapshotId: data.snapshot_id,
    beforeChecksum: data.before_checksum,
    afterChecksum: data.after_checksum,
    releaseNotes: data.release_notes ?? undefined,
    approvedAt: data.approved_at ?? null,
    publishedAt: data.published_at ?? null,
    timestamp: data.timestamp,
    diffRef: JSON.stringify(data.diff_ref),
  };
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (!API_BASE_URL) {
    throw new BackendUnavailableError(`Backend unavailable: NEXT_PUBLIC_MEMORYENGINE_API_BASE_URL is not configured for ${path}.`);
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: buildHeaders(options),
      ...options,
    });

    if (!response.ok) {
      const error = await buildApiError(response);
      if (error instanceof UnauthorizedError) {
        writeStoredSession(null);
      }
      throw error;
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const text = await response.text();
    if (!text) {
      return undefined as T;
    }
    return JSON.parse(text) as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new BackendUnavailableError(
      `Backend unavailable at ${API_BASE_URL}: ${error instanceof Error ? error.message : "request failed"}`,
    );
  }
}

async function requestText(path: string, options: RequestOptions = {}): Promise<string> {
  if (!API_BASE_URL) {
    throw new BackendUnavailableError(`Backend unavailable: NEXT_PUBLIC_MEMORYENGINE_API_BASE_URL is not configured for ${path}.`);
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: buildHeaders(options),
      ...options,
    });
    if (!response.ok) {
      const error = await buildApiError(response);
      if (error instanceof UnauthorizedError) {
        writeStoredSession(null);
      }
      throw error;
    }
    return await response.text();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new BackendUnavailableError(
      `Backend unavailable at ${API_BASE_URL}: ${error instanceof Error ? error.message : "request failed"}`,
    );
  }
}

export const client = {
  auth: {
    async login(email: string, password: string) {
      const response = await request<any>("/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
        skipAuth: true,
      });
      const session = toSession(response);
      writeStoredSession(session);
      return session;
    },
    async me() {
      const currentSession = readStoredSession();
      try {
        const response = await request<any>("/v1/auth/me", {
          method: "GET",
        });
        if (!response) {
          writeStoredSession(null);
          return null;
        }
        const session = toSession({ ...response, token: currentSession?.token ?? response.token });
        writeStoredSession(session);
        return session;
      } catch (error) {
        if (error instanceof UnauthorizedError) {
          writeStoredSession(null);
          return null;
        }
        throw error;
      }
    },
    async logout() {
      try {
        await request<void>("/v1/auth/logout", {
          method: "POST",
        });
      } finally {
        writeStoredSession(null);
      }
    },
  },
  configs: {
    async list(filters: ConfigListFilters & { kind?: ConfigKind } = {}) {
      const search = buildSearchParams({
        kind: filters.kind ? toBackendKind(filters.kind) : undefined,
        scope: filters.scope,
        environment: filters.environment,
        tenant: filters.tenant,
        status: filters.status,
      });
      const response = await request<unknown>(`/v1/control/configs${search.toString() ? `?${search.toString()}` : ""}`, {
        method: "GET",
      });
      return toConfigDocuments(normalizeArrayResponse<BackendConfig>(response));
    },
    async save(config: ConfigDocument) {
      const body: Record<string, unknown> = {
        name: config.name,
        scope: config.scope,
        tenant_id: config.tenant === "all" ? null : config.tenant,
        version: config.version,
        base_version: config.baseVersion ?? null,
      };
      if (typeof config.yaml === "string" && config.definitionJson === undefined) {
        body.definition_yaml = config.yaml;
      }
      if (config.definitionJson !== undefined) {
        body.definition_json = config.definitionJson;
      }
      if (config.id) {
        const response = await request<BackendConfig>(`/v1/control/configs/${config.id}`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
        return toConfigDocument(response, config.previousYaml);
      }
      const response = await request<BackendConfig>("/v1/control/configs", {
        method: "POST",
        body: JSON.stringify({
          kind: toBackendKind(config.kind),
          ...body,
        }),
      });
      return toConfigDocument(response);
    },
    async approve(configId: string) {
      const response = await request<{ id: string; status: string; approved_by?: string; approved_at?: string }>(
        `/v1/control/configs/${configId}/approve`,
        {
          method: "POST",
        },
      );
      return response;
    },
    async archive(configId: string) {
      const response = await request<BackendConfig>(`/v1/control/configs/${configId}/archive`, {
        method: "POST",
      });
      return toConfigDocument(response);
    },
    async validate(configId: string) {
      const response = await request<BackendValidationResponse>("/v1/control/validate", {
        method: "POST",
        body: JSON.stringify({ config_id: configId }),
      });
      return toValidationRun(response, configId);
    },
    async validateBundle(requestPayload: ValidateRequest, focusDocumentId: string) {
      const response = await request<BackendValidationResponse>("/v1/control/validate", {
        method: "POST",
        body: JSON.stringify(requestPayload),
      });
      return toValidationRun(response, focusDocumentId);
    },
    async simulate(configId: string, sampleEvent: string) {
      const response = await request<BackendSimulationResponse>("/v1/control/simulate", {
        method: "POST",
        body: JSON.stringify({ config_id: configId, sample_event: parseSampleEvent(sampleEvent) }),
      });
      return toSimulationRun(response, configId, sampleEvent);
    },
    async publish(requestPayload: PublishRequest) {
      const response = await request<BackendPublication>("/v1/control/publish", {
        method: "POST",
        body: JSON.stringify(requestPayload),
      });
      return toPublicationSnapshot(response);
    },
    async rollback(snapshotId: string) {
      const response = await request<BackendPublication>("/v1/control/rollback", {
        method: "POST",
        body: JSON.stringify({ snapshot_id: snapshotId } satisfies RollbackRequest),
      });
      return toPublicationSnapshot(response);
    },
    async importDocument(kind: ConfigKind, source: string, format: "yaml" | "json") {
      const payload: ImportPayload =
        format === "json"
          ? {
              kind: toBackendKind(kind),
              format,
              yaml: source,
              json: safeJsonParse(source) ?? undefined,
              definition_yaml: source,
              definition_json: safeJsonParse(source) ?? undefined,
            }
          : {
              kind: toBackendKind(kind),
              format,
              yaml: source,
              definition_yaml: source,
              definition_json: safeJsonParse(source) ?? undefined,
            };
      const response = await request<BackendConfig>("/v1/control/import", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      return toConfigDocument(response);
    },
    exportDocument(configId: string, format: "yaml" | "json" = "yaml") {
      return requestText(`/v1/control/configs/${configId}/export?${buildSearchParams({ format }).toString()}`, {
        method: "GET",
      });
    },
  },
  validations: {
    async list() {
      const response = await request<unknown>("/v1/control/validation", {
        method: "GET",
      });
      return groupValidationRuns(normalizeArrayResponse<BackendValidationIssue>(response));
    },
  },
  simulations: {
    async list() {
      const response = await request<unknown>("/v1/control/simulation", {
        method: "GET",
      });
      return normalizeArrayResponse<BackendSimulationResponse>(response).map((item, index) =>
        toSimulationRun(item, `config-${index}`, "action: docs.openDocument"),
      );
    },
  },
  publications: {
    async list(filters: PublicationFilters = {}) {
      const search = buildSearchParams({
        scope: filters.scope,
        environment: filters.environment,
        tenant: filters.tenant,
        status: filters.status,
        kind: filters.kind,
      });
      const response = await request<unknown>(`/v1/control/publications${search.toString() ? `?${search.toString()}` : ""}`, {
        method: "GET",
      });
      return normalizeArrayResponse<BackendPublication>(response).map((item) => toPublicationSnapshot(item));
    },
  },
  decisions: {
    async list(filters: DecisionFilters = {}) {
      const search = buildSearchParams({
        scope: filters.scope,
        tenant: filters.tenant,
        environment: filters.environment,
        status: filters.status,
        kind: filters.kind,
        query: filters.query,
      });
      const response = await request<unknown>(`/v1/memory/decisions${search.toString() ? `?${search.toString()}` : ""}`, {
        method: "GET",
      });
      const records = normalizeArrayResponse<BackendDecision>(response).map(toDecisionRecord);
      return records.filter((record) => {
        if (filters.status && record.status !== filters.status) return false;
        if (filters.scope && record.scope !== filters.scope) return false;
        if (filters.environment && record.environment !== filters.environment) return false;
        if (filters.tenant && record.tenant !== filters.tenant) return false;
        if (filters.kind && record.kind !== filters.kind) return false;
        if (filters.query) {
          const haystack = [
            record.title,
            record.reasonCode,
            ...(record.reasonCodes ?? []),
            record.sourceSystem ?? "",
            record.routeTemplate ?? "",
            record.moduleKey ?? "",
            record.workflowKey ?? "",
            record.intentSummary ?? "",
            ...(record.relatedApiIds ?? []),
            record.observedEntryId ?? "",
          ]
            .join(" ")
            .toLowerCase();
          if (!haystack.includes(filters.query.toLowerCase())) return false;
        }
        return true;
      });
    },
  },
  memories: {
    async list(filters: MemoryFilters = {}) {
      const currentSession = readStoredSession();
      const response = await request<unknown>("/v1/memory/query", {
        method: "POST",
        body: JSON.stringify({
          tenant_id: filters.tenant ?? "",
          user_id: filters.user ?? currentSession?.user.email ?? "",
          memory_type: filters.type,
          query_text: filters.query,
          scope: filters.scope,
          environment: filters.environment,
          status: filters.status,
        }),
      });
      const records = normalizeArrayResponse<BackendMemory>(response).map(toMemoryRecord);
      return records.filter((record) => {
        if (filters.type && record.type !== filters.type) return false;
        if (filters.status && record.status !== filters.status) return false;
        if (filters.scope && record.scope !== filters.scope) return false;
        if (filters.environment && record.environment && record.environment !== filters.environment) return false;
        if (filters.tenant && record.tenant !== filters.tenant) return false;
        if (filters.query) {
          const haystack = [
            record.title,
            record.summary,
            record.evidence,
            record.configSnapshotId,
            record.workflowKey ?? "",
            record.observedApiName ?? "",
            ...(record.relatedApiIds ?? []),
            ...(record.evidenceEventIds ?? []),
          ]
            .join(" ")
            .toLowerCase();
          if (!haystack.includes(filters.query.toLowerCase())) return false;
        }
        return true;
      });
    },
  },
  audit: {
    async list(filters: AuditFilters = {}) {
      const search = buildSearchParams({
        scope: filters.scope,
        tenant_id: filters.tenant,
        target_kind: filters.kind,
        action: filters.action ? `config.${filters.action}` : undefined,
      });
      const response = await request<unknown>(`/v1/control/audit-log${search.toString() ? `?${search.toString()}` : ""}`, {
        method: "GET",
      });
      return normalizeArrayResponse<BackendAudit>(response)
        .map(toAuditRecord)
        .filter((record) => {
          if (filters.environment && record.environment !== filters.environment) return false;
          if (filters.query) {
            const haystack = [
              record.actor,
              record.role,
              record.action,
              record.documentKind,
              record.documentName,
              record.snapshotId,
              record.diffRef,
            ]
              .filter(Boolean)
              .join(" ")
              .toLowerCase();
            if (!haystack.includes(filters.query.toLowerCase())) return false;
          }
          return true;
        });
    },
  },
};
