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
import {
  mockExportConfig,
  mockImportConfig,
  mockListAuditLogs,
  mockListConfigs,
  mockListDecisions,
  mockListMemories,
  mockListPublications,
  mockListSimulations,
  mockListValidations,
  mockLogin,
  mockLogout,
  mockMe,
  mockPublishConfig,
  mockRollbackPublication,
  mockSaveConfig,
  mockSimulateConfig,
  mockValidateConfig,
} from "@/lib/api/mock";

type RequestOptions = RequestInit & {
  mockFallback?: () => Promise<unknown>;
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
  checksum: string;
  definition_json: Record<string, unknown>;
  definition_yaml: string;
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
  api_ontology_document_id: string;
  memory_ontology_document_id: string;
  policy_profile_document_id: string;
};

type BackendDecision = {
  id: string;
  title: string;
  action: string;
  status: string;
  scope: string;
  tenant: string;
  environment: string;
  reason_code: string;
  config_snapshot_id: string;
  evidence: string;
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
  payload: Record<string, unknown>;
};

type BackendAudit = {
  id: string;
  actor: string;
  role: string;
  action: string;
  document_kind: string;
  document_version: string;
  timestamp: string;
  diff_ref: unknown;
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

function shouldUseMockFallback(error: unknown) {
  return error instanceof TypeError;
}

function toConfigDocument(data: BackendConfig): ConfigDocument {
  return {
    id: data.id,
    kind: toFrontendKind(data.kind),
    name: data.name,
    version: data.version,
    status: data.status as ConfigDocument["status"],
    tenant: data.tenant_id ?? "all",
    scope: data.scope,
    environment: "dev",
    updatedAt: data.updated_at,
    lastPublishedAt: data.published_by ? data.updated_at : undefined,
    summary: deriveSummary(data.name, data.definition_yaml),
    yaml: data.definition_yaml,
    previousYaml: undefined,
  };
}

function validationChecksFromIssues(issues: BackendValidationIssue[]) {
  if (!issues.length) {
    return [{ name: "validation", status: "pass" as const, detail: "No validation issues detected." }];
  }
  return issues.map((issue) => ({
    name: `${issue.code} @ ${issue.path}`,
    status: issue.severity === "error" ? ("fail" as const) : ("warn" as const),
    detail: issue.message,
  }));
}

function toValidationRun(result: BackendValidationResponse, configId: string): ValidationRun {
  const issues = result.issues.filter((issue) => !issue.document_id || issue.document_id === configId);
  return {
    id: `validation-${configId}`,
    documentId: configId,
    documentName: configId,
    status: result.status,
    timestamp: new Date().toISOString(),
    summary: issues.length ? `${issues.length} validation issue(s) reported.` : "No validation issues detected.",
    checks: validationChecksFromIssues(issues),
    issues: issues.map((issue) => issue.message),
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
    status: documentIssues.some((issue) => issue.severity === "error") ? "fail" : "warn",
    timestamp: new Date().toISOString(),
    summary: `${documentIssues.length} validation issue(s) recorded.`,
    checks: validationChecksFromIssues(documentIssues),
    issues: documentIssues.map((issue) => issue.message),
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
  return {
    tenant_id: "tenant_ui",
    user_id: String(event.user ?? "user_ui"),
    api_name: action,
    structured_fields:
      action === "profile.updateAddress"
        ? { address: "123 Seongsu-ro, Seongdong-gu, Seoul" }
        : action === "search.webSearch"
          ? { query: "one off search" }
          : { document_title: "Real Estate Tax Guide" },
  };
}

function toSimulationRun(result: BackendSimulationResponse, configId: string, sampleEvent: string): SimulationRun {
  return {
    id: `simulation-${configId}`,
    documentId: configId,
    sampleEvent,
    timestamp: new Date().toISOString(),
    beforeDecision: String(result.old_decision?.action ?? "n/a"),
    afterDecision: String(result.new_decision?.action ?? "n/a"),
    reasonCodes:
      result.changed_reason_codes.length > 0
        ? result.changed_reason_codes
        : ((result.new_decision?.reason_codes as string[] | undefined) ?? []),
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

function toPublicationSnapshot(data: BackendPublication, documentId: string, documentName: string): PublicationSnapshot {
  return {
    id: data.id,
    documentId,
    documentName,
    version: 0,
    status: data.rollback_of ? "rolled-back" : data.is_active ? "active" : "archived",
    createdAt: data.published_at,
    createdBy: data.published_by,
    configSnapshotId: data.id,
    note: data.snapshot_hash,
  };
}

function toDecisionRecord(data: BackendDecision): DecisionRecord {
  return {
    id: data.id,
    title: data.title,
    action: data.action,
    status: data.status as DecisionRecord["status"],
    scope: data.scope,
    tenant: data.tenant,
    environment: data.environment,
    reasonCode: data.reason_code,
    configSnapshotId: data.config_snapshot_id,
    evidence: data.evidence,
    timestamp: data.timestamp,
  };
}

function toMemoryRecord(data: BackendMemory): MemoryRecord {
  return {
    id: data.record_id,
    title: data.title,
    type: data.memory_type,
    confidence: data.confidence,
    summary:
      (typeof data.payload.summary === "string" && data.payload.summary) ||
      (typeof data.payload.topic === "string" && data.payload.topic) ||
      JSON.stringify(data.payload),
    scope: "runtime",
    tenant: "runtime",
    status:
      data.state === "active" ? "active" : data.state === "deleted" ? "deleted" : ("blocked" as MemoryRecord["status"]),
    evidence: `${data.evidence_count} evidence record(s)`,
    configSnapshotId: data.config_snapshot_id,
    timestamp: new Date().toISOString(),
  };
}

function toAuditRecord(data: BackendAudit): AuditRecord {
  return {
    id: data.id,
    actor: data.actor,
    role: data.role,
    documentKind: data.document_kind,
    documentVersion: data.document_version,
    action: data.action,
    timestamp: data.timestamp,
    diffRef: JSON.stringify(data.diff_ref),
  };
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (API_BASE_URL) {
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

      return (await response.json()) as T;
    } catch (error) {
      if (options.mockFallback && shouldUseMockFallback(error)) {
        return (await options.mockFallback()) as T;
      }
      throw error;
    }
  }

  if (!options.mockFallback) {
    throw new Error(`No backend available for ${path}`);
  }

  return (await options.mockFallback()) as T;
}

async function requestText(path: string, options: RequestOptions = {}): Promise<string> {
  if (API_BASE_URL) {
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
      if (options.mockFallback && shouldUseMockFallback(error)) {
        return (await options.mockFallback()) as string;
      }
      throw error;
    }
  }

  if (!options.mockFallback) {
    throw new Error(`No backend available for ${path}`);
  }
  return (await options.mockFallback()) as string;
}

export const client = {
  auth: {
    async login(email: string, password: string) {
      const response = await request<any>("/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
        skipAuth: true,
        mockFallback: () => mockLogin(email, password),
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
          mockFallback: () => mockMe(),
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
          mockFallback: () => mockLogout(),
        });
      } finally {
        writeStoredSession(null);
      }
    },
  },
  configs: {
    async list(kind?: ConfigKind) {
      const suffix = kind ? `?kind=${toBackendKind(kind)}` : "";
      const response = await request<BackendConfig[]>(`/v1/control/configs${suffix}`, {
        method: "GET",
        mockFallback: () => mockListConfigs(kind),
      });
      return response.map(toConfigDocument);
    },
    async save(config: ConfigDocument) {
      if (config.id) {
        const response = await request<BackendConfig>(`/v1/control/configs/${config.id}`, {
          method: "PUT",
          body: JSON.stringify({
            scope: config.scope,
            tenant_id: config.tenant === "all" ? null : config.tenant,
            definition_yaml: config.yaml,
          }),
          mockFallback: () => mockSaveConfig(config),
        });
        return toConfigDocument(response);
      }
      const response = await request<BackendConfig>("/v1/control/configs", {
        method: "POST",
        body: JSON.stringify({
          kind: toBackendKind(config.kind),
          name: config.name,
          scope: config.scope,
          tenant_id: config.tenant === "all" ? null : config.tenant,
          yaml: config.yaml,
        }),
        mockFallback: () => mockSaveConfig(config),
      });
      return toConfigDocument(response);
    },
    async validate(configId: string) {
      const response = await request<BackendValidationResponse>("/v1/control/validate", {
        method: "POST",
        body: JSON.stringify({ config_id: configId }),
        mockFallback: () => mockValidateConfig(configId),
      });
      return toValidationRun(response, configId);
    },
    async simulate(configId: string, sampleEvent: string) {
      const response = await request<BackendSimulationResponse>("/v1/control/simulate", {
        method: "POST",
        body: JSON.stringify({ config_id: configId, sample_event: parseSampleEvent(sampleEvent) }),
        mockFallback: () => mockSimulateConfig(configId, sampleEvent),
      });
      return toSimulationRun(response, configId, sampleEvent);
    },
    async publish(configId: string) {
      const response = await request<BackendPublication>("/v1/control/publish", {
        method: "POST",
        body: JSON.stringify({ config_id: configId }),
        mockFallback: () => mockPublishConfig(configId),
      });
      return toPublicationSnapshot(response, configId, configId);
    },
    async rollback(snapshotId: string) {
      const response = await request<BackendPublication>("/v1/control/rollback", {
        method: "POST",
        body: JSON.stringify({ snapshot_id: snapshotId }),
        mockFallback: () => mockRollbackPublication(snapshotId),
      });
      return toPublicationSnapshot(response, response.api_ontology_document_id, "Rolled back snapshot");
    },
    async importYaml(kind: ConfigKind, yaml: string) {
      const response = await request<BackendConfig>("/v1/control/import", {
        method: "POST",
        body: JSON.stringify({ kind: toBackendKind(kind), yaml }),
        mockFallback: () => mockImportConfig(kind, yaml),
      });
      return toConfigDocument(response);
    },
    exportYaml(configId: string) {
      return requestText(`/v1/control/configs/${configId}/export`, {
        method: "GET",
        mockFallback: () => mockExportConfig(configId),
      });
    },
  },
  validations: {
    async list() {
      const response = await request<BackendValidationIssue[]>("/v1/control/validation", {
        method: "GET",
        mockFallback: () => mockListValidations(),
      });
      return groupValidationRuns(response);
    },
  },
  simulations: {
    async list() {
      const response = await request<BackendSimulationResponse[]>("/v1/control/simulation", {
        method: "GET",
        mockFallback: () => mockListSimulations(),
      });
      return response.map((item, index) => toSimulationRun(item, `config-${index}`, "action: docs.openDocument"));
    },
  },
  publications: {
    async list() {
      const response = await request<BackendPublication[]>("/v1/control/publications", {
        method: "GET",
        mockFallback: () => mockListPublications(),
      });
      return response.map((item) => toPublicationSnapshot(item, item.api_ontology_document_id, "Config snapshot"));
    },
  },
  decisions: {
    async list(filters?: {
      scope?: string;
      tenant?: string;
      environment?: string;
      status?: string;
      query?: string;
    }) {
      const search = new URLSearchParams();
      if (filters?.tenant) search.set("tenant", filters.tenant);
      const response = await request<BackendDecision[]>(`/v1/memory/decisions?${search.toString()}`, {
        method: "GET",
        mockFallback: () => mockListDecisions(filters),
      });
      return response.map(toDecisionRecord);
    },
  },
  memories: {
    async list(filters?: { type?: string; status?: string; query?: string }) {
      const response = await request<BackendMemory[]>("/v1/memory/query", {
        method: "POST",
        body: JSON.stringify({
          tenant_id: "tenant_ui",
          user_id: "user_ui",
          memory_type: filters?.type,
          query_text: filters?.query,
        }),
        mockFallback: () => mockListMemories(filters),
      });
      return response.map(toMemoryRecord);
    },
  },
  audit: {
    async list() {
      const response = await request<BackendAudit[]>("/v1/audit/logs", {
        method: "GET",
        mockFallback: () => mockListAuditLogs(),
      });
      return response.map(toAuditRecord);
    },
  },
};
