import type {
  AuditRecord,
  ConfigDocument,
  ConfigKind,
  DemoState,
  DecisionRecord,
  MemoryRecord,
  PublicationSnapshot,
  Session,
  SimulationRun,
  ValidationRun,
} from "@/lib/api/types";

const STORAGE_KEY = "memoryengine-demo-state-v1";

const now = () => new Date().toISOString();

const id = (prefix: string) => `${prefix}_${Math.random().toString(36).slice(2, 10)}`;

const configSeed = (): ConfigDocument[] => [
  {
    id: "cfg_api_1",
    kind: "api-ontology",
    name: "Core API Ontology",
    version: 3,
    status: "published",
    tenant: "all",
    scope: "global",
    environment: "staging-local",
    updatedAt: now(),
    lastPublishedAt: now(),
    summary: "Normalizes profile and document activity into stable semantic actions.",
    yaml: `kind: api-ontology
name: Core API Ontology
version: 3
status: published
actions:
  - profile.updateAddress
  - docs.openDocument
  - search.webSearch`,
    previousYaml: `kind: api-ontology
name: Core API Ontology
version: 2
status: validated`,
  },
  {
    id: "cfg_memory_1",
    kind: "memory-ontology",
    name: "Memory Ontology",
    version: 5,
    status: "validated",
    tenant: "all",
    scope: "global",
    environment: "staging-local",
    updatedAt: now(),
    summary: "Defines which observations can become durable memory and how they supersede each other.",
    yaml: `kind: memory-ontology
name: Memory Ontology
version: 5
status: validated
memories:
  - interest.topic
  - profile.address
  - relation.customerAlias`,
    previousYaml: `kind: memory-ontology
name: Memory Ontology
version: 4
status: draft`,
  },
  {
    id: "cfg_policy_1",
    kind: "policy-profile",
    name: "Default Policy Profile",
    version: 7,
    status: "approved",
    tenant: "all",
    scope: "global",
    environment: "staging-local",
    updatedAt: now(),
    lastPublishedAt: now(),
    summary: "Applies sensitivity ceilings, repeat thresholds, and hard safety blocks.",
    yaml: `kind: policy-profile
name: Default Policy Profile
version: 7
status: approved
repeatThresholds:
  docs.openDocument: 3
hardSafety:
  blockSensitiveLevels:
    - S3_CONFIDENTIAL
    - S4_RESTRICTED`,
    previousYaml: `kind: policy-profile
name: Default Policy Profile
version: 6
status: validated`,
  },
];

const validationSeed = (): ValidationRun[] => [
  {
    id: "val_1",
    documentId: "cfg_api_1",
    documentName: "Core API Ontology",
    status: "pass",
    timestamp: now(),
    summary: "All document schemas resolved and policy links are stable.",
    checks: [
      { name: "schema", status: "pass", detail: "All required fields present." },
      { name: "versioning", status: "pass", detail: "Version increases monotonically." },
      { name: "policy-link", status: "pass", detail: "Policy references resolved." },
    ],
    issues: [],
  },
  {
    id: "val_2",
    documentId: "cfg_memory_1",
    documentName: "Memory Ontology",
    status: "warn",
    timestamp: now(),
    summary: "One memory type needs stricter sensitivity guidance.",
    checks: [
      { name: "schema", status: "pass", detail: "All required fields present." },
      { name: "sensitivity", status: "warn", detail: "relation.customerAlias should retain evidence anchors." },
      { name: "supersession", status: "pass", detail: "Supersession rules are defined." },
    ],
    issues: ["relation.customerAlias requires anchor-confidence review before publish."],
  },
];

const publicationSeed = (): PublicationSnapshot[] => [
  {
    id: "snap_101",
    documentId: "cfg_api_1",
    documentName: "Core API Ontology",
    version: 3,
    status: "active",
    createdAt: now(),
    createdBy: "operator@memoryengine.local",
    configSnapshotId: "cfgsnap_001",
    note: "Initial active snapshot for the operator console.",
  },
  {
    id: "snap_102",
    documentId: "cfg_policy_1",
    documentName: "Default Policy Profile",
    version: 7,
    status: "active",
    createdAt: now(),
    createdBy: "approver@memoryengine.local",
    configSnapshotId: "cfgsnap_002",
    note: "Current policy profile used for local evaluation.",
  },
];

const decisionsSeed = (): DecisionRecord[] => [
  {
    id: "dec_1",
    title: "Address change accepted",
    action: "profile.updateAddress",
    status: "accepted",
    scope: "tenant:acme",
    tenant: "acme",
    environment: "staging-local",
    reasonCode: "supersedes_prior_value",
    configSnapshotId: "cfgsnap_001",
    evidence: "user profile payload and current address slot",
    timestamp: now(),
  },
  {
    id: "dec_2",
    title: "Repeated reading promoted to topic memory",
    action: "docs.openDocument",
    status: "overridden",
    scope: "tenant:acme",
    tenant: "acme",
    environment: "staging-local",
    reasonCode: "repeat_threshold_met",
    configSnapshotId: "cfgsnap_001",
    evidence: "three document-open events over five days",
    timestamp: now(),
  },
  {
    id: "dec_3",
    title: "Search activity blocked from long-term memory",
    action: "search.webSearch",
    status: "blocked",
    scope: "global",
    tenant: "acme",
    environment: "staging-local",
    reasonCode: "single_event_insufficient",
    configSnapshotId: "cfgsnap_002",
    evidence: "one-off search session with no repeat signal",
    timestamp: now(),
  },
  {
    id: "dec_4",
    title: "Duplicate customer aliases merged",
    action: "relation.customerAlias",
    status: "conflicted",
    scope: "tenant:acme",
    tenant: "acme",
    environment: "staging-local",
    reasonCode: "anchor_confidence_borderline",
    configSnapshotId: "cfgsnap_002",
    evidence: "two aliases mapped to one canonical customer entity",
    timestamp: now(),
  },
];

const memoriesSeed = (): MemoryRecord[] => [
  {
    id: "mem_1",
    title: "Update address memory",
    type: "profile.address",
    confidence: 0.96,
    summary: "User moved to a new primary mailing address.",
    scope: "tenant:acme",
    tenant: "acme",
    status: "active",
    evidence: "profile.updateAddress event",
    configSnapshotId: "cfgsnap_001",
    timestamp: now(),
  },
  {
    id: "mem_2",
    title: "Reading interest topic",
    type: "interest.topic",
    confidence: 0.88,
    summary: "Document reading pattern indicates active interest in policy tooling.",
    scope: "tenant:acme",
    tenant: "acme",
    status: "active",
    evidence: "docs.openDocument repeated three times",
    configSnapshotId: "cfgsnap_001",
    timestamp: now(),
  },
  {
    id: "mem_3",
    title: "Search event suppressed",
    type: "search.webSearch",
    confidence: 0.22,
    summary: "One-off web search suppressed from durable memory.",
    scope: "global",
    tenant: "acme",
    status: "blocked",
    evidence: "single query, default policy",
    configSnapshotId: "cfgsnap_002",
    timestamp: now(),
  },
];

const auditsSeed = (): AuditRecord[] => [
  {
    id: "aud_1",
    actor: "operator@memoryengine.local",
    role: "operator",
    documentKind: "api-ontology",
    documentVersion: "3",
    action: "publish",
    timestamp: now(),
    diffRef: "snap_101 -> cfgsnap_001",
  },
  {
    id: "aud_2",
    actor: "approver@memoryengine.local",
    role: "approver",
    documentKind: "policy-profile",
    documentVersion: "7",
    action: "rollback",
    timestamp: now(),
    diffRef: "cfgsnap_002 -> cfgsnap_001",
  },
];

export function createInitialState(): DemoState {
  return {
    session: null,
    configs: configSeed(),
    validations: validationSeed(),
    simulations: [],
    publications: publicationSeed(),
    decisions: decisionsSeed(),
    memories: memoriesSeed(),
    audits: auditsSeed(),
  };
}

export function readState(): DemoState {
  if (typeof window === "undefined") {
    return createInitialState();
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    const initial = createInitialState();
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(initial));
    return initial;
  }

  try {
    return JSON.parse(raw) as DemoState;
  } catch {
    const initial = createInitialState();
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(initial));
    return initial;
  }
}

export function writeState(next: DemoState): DemoState {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  return next;
}

export function clearState(): DemoState {
  const initial = createInitialState();
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(initial));
  }
  return initial;
}

function cloneState(state: DemoState): DemoState {
  return JSON.parse(JSON.stringify(state)) as DemoState;
}

function nextSession(email: string): Session {
  const role: Session["user"]["role"] = email.includes("admin")
    ? "admin"
    : email.includes("approver")
      ? "approver"
      : email.includes("editor")
        ? "editor"
        : email.includes("viewer")
          ? "viewer"
          : "operator";

  return {
    token: `demo.${email.replace(/[^a-z0-9]/gi, "").toLowerCase()}`,
    user: {
      email,
      displayName: email.split("@")[0].replaceAll(".", " "),
      role,
    },
  };
}

export async function mockLogin(email: string, password: string): Promise<Session> {
  void password;
  const session = nextSession(email);
  const state = cloneState(readState());
  state.session = session;
  state.audits.unshift({
    id: id("aud"),
    actor: email,
    role: session.user.role,
    documentKind: "auth",
    documentVersion: "1",
    action: "login",
    timestamp: now(),
    diffRef: "session-created",
  });
  writeState(state);
  return session;
}

export async function mockMe(): Promise<Session | null> {
  return readState().session;
}

export async function mockLogout(): Promise<void> {
  const state = cloneState(readState());
  state.session = null;
  writeState(state);
}

export async function mockListConfigs(kind?: ConfigKind) {
  const state = readState();
  return kind ? state.configs.filter((config) => config.kind === kind) : state.configs;
}

export async function mockSaveConfig(next: ConfigDocument) {
  const state = cloneState(readState());
  const index = state.configs.findIndex((config) => config.id === next.id);
  const previous = state.configs[index];
  const updated = {
    ...next,
    updatedAt: now(),
    previousYaml: previous?.yaml,
    version: previous ? previous.version + (previous.yaml !== next.yaml ? 1 : 0) : next.version,
  };

  if (index >= 0) {
    state.configs[index] = updated;
  } else {
    state.configs.unshift(updated);
  }

  state.audits.unshift({
    id: id("aud"),
    actor: state.session?.user.email ?? "operator@memoryengine.local",
    role: state.session?.user.role ?? "operator",
    documentKind: updated.kind,
    documentVersion: String(updated.version),
    action: "save",
    timestamp: now(),
    diffRef: `${updated.id}:yaml`,
  });

  writeState(state);
  return updated;
}

export async function mockValidateConfig(configId: string): Promise<ValidationRun> {
  const state = cloneState(readState());
  const config = state.configs.find((item) => item.id === configId);
  if (!config) {
    throw new Error("Config document not found");
  }

  const isInvalid = /invalid|broken|error/i.test(config.yaml);
  const run: ValidationRun = {
    id: id("val"),
    documentId: config.id,
    documentName: config.name,
    status: isInvalid ? "fail" : config.kind === "memory-ontology" ? "warn" : "pass",
    timestamp: now(),
    summary: isInvalid
      ? "Validation failed because the document contains an invalid marker."
      : config.kind === "memory-ontology"
        ? "Validation passed with one sensitivity warning."
        : "Validation passed."
      ,
    checks: [
      {
        name: "schema",
        status: isInvalid ? "fail" : "pass",
        detail: isInvalid ? "Detected invalid marker in YAML." : "All required keys present.",
      },
      {
        name: "lifecycle",
        status: config.status === "published" ? "pass" : "warn",
        detail: config.status === "published" ? "Published snapshot is immutable." : "Document is still editable.",
      },
      {
        name: "safety",
        status: config.kind === "policy-profile" ? "pass" : "warn",
        detail: config.kind === "policy-profile" ? "Hard safety rules remain intact." : "Sensitivity review recommended.",
      },
    ],
    issues: isInvalid ? ["Document is not publishable until invalid markers are removed."] : [],
  };

  state.validations.unshift(run);
  state.audits.unshift({
    id: id("aud"),
    actor: state.session?.user.email ?? "operator@memoryengine.local",
    role: state.session?.user.role ?? "operator",
    documentKind: config.kind,
    documentVersion: String(config.version),
    action: "validate",
    timestamp: now(),
    diffRef: run.id,
  });
  writeState(state);
  return run;
}

export async function mockSimulateConfig(configId: string, sampleEvent: string): Promise<SimulationRun> {
  const state = cloneState(readState());
  const config = state.configs.find((item) => item.id === configId);
  if (!config) {
    throw new Error("Config document not found");
  }

  const event = sampleEvent.trim();
  const beforeDecision = event.includes("search.webSearch")
    ? "No durable memory"
    : event.includes("docs.openDocument")
      ? "Below repeat threshold"
      : "Pending evaluation";
  const afterDecision = event.includes("profile.updateAddress")
    ? "Create profile.address memory"
    : event.includes("docs.openDocument")
      ? "Promote to interest.topic after repeat threshold"
      : event.includes("search.webSearch")
        ? "Block durable memory; keep audit trace only"
        : "No long-term memory";

  const run: SimulationRun = {
    id: id("sim"),
    documentId: config.id,
    sampleEvent: event,
    timestamp: now(),
    beforeDecision,
    afterDecision,
    reasonCodes: event.includes("profile.updateAddress")
      ? ["supersedes_prior_value"]
      : event.includes("docs.openDocument")
        ? ["repeat_threshold_met", "semantic_signal_key:docs.openDocument"]
        : event.includes("search.webSearch")
          ? ["single_event_insufficient", "s3_blocked"]
          : ["no_matching_rule"],
    diff: [
      `before: ${beforeDecision}`,
      `after: ${afterDecision}`,
      `snapshot: ${config.id}:${config.version}`,
    ].join("\n"),
  };

  state.simulations.unshift(run);
  state.audits.unshift({
    id: id("aud"),
    actor: state.session?.user.email ?? "operator@memoryengine.local",
    role: state.session?.user.role ?? "operator",
    documentKind: config.kind,
    documentVersion: String(config.version),
    action: "simulate",
    timestamp: now(),
    diffRef: run.id,
  });
  writeState(state);
  return run;
}

export async function mockPublishConfig(configId: string): Promise<PublicationSnapshot> {
  const state = cloneState(readState());
  const config = state.configs.find((item) => item.id === configId);
  if (!config) {
    throw new Error("Config document not found");
  }

  const snapshot: PublicationSnapshot = {
    id: id("snap"),
    documentId: config.id,
    documentName: config.name,
    version: config.version,
    status: "active",
    createdAt: now(),
    createdBy: state.session?.user.email ?? "operator@memoryengine.local",
    configSnapshotId: id("cfgsnap"),
    note: "Published from the operator console.",
  };

  state.publications = state.publications.map((item) => ({ ...item, status: item.status === "active" ? "archived" : item.status }));
  state.publications.unshift(snapshot);
  config.status = "published";
  config.lastPublishedAt = now();
  state.audits.unshift({
    id: id("aud"),
    actor: state.session?.user.email ?? "operator@memoryengine.local",
    role: state.session?.user.role ?? "operator",
    documentKind: config.kind,
    documentVersion: String(config.version),
    action: "publish",
    timestamp: now(),
    diffRef: snapshot.configSnapshotId,
  });
  writeState(state);
  return snapshot;
}

export async function mockRollbackPublication(snapshotId: string): Promise<PublicationSnapshot> {
  const state = cloneState(readState());
  const target = state.publications.find((item) => item.id === snapshotId);
  if (!target) {
    throw new Error("Snapshot not found");
  }

  state.publications = state.publications.map((item) => {
    if (item.id === snapshotId) {
      return { ...item, status: "active" };
    }
    if (item.status === "active") {
      return { ...item, status: "rolled-back" };
    }
    return item;
  });

  state.audits.unshift({
    id: id("aud"),
    actor: state.session?.user.email ?? "operator@memoryengine.local",
    role: state.session?.user.role ?? "operator",
    documentKind: "config-snapshot",
    documentVersion: String(target.version),
    action: "rollback",
    timestamp: now(),
    diffRef: `${snapshotId}:rollback`,
  });
  writeState(state);
  return target;
}

export async function mockListValidations() {
  return readState().validations;
}

export async function mockListSimulations() {
  return readState().simulations;
}

export async function mockListPublications() {
  return readState().publications;
}

export async function mockListDecisions(filters?: {
  scope?: string;
  tenant?: string;
  environment?: string;
  status?: string;
  query?: string;
}) {
  const state = readState();
  return state.decisions.filter((decision) => {
    const matchesScope = !filters?.scope || decision.scope.includes(filters.scope);
    const matchesTenant = !filters?.tenant || decision.tenant.includes(filters.tenant);
    const matchesEnvironment = !filters?.environment || decision.environment.includes(filters.environment);
    const matchesStatus = !filters?.status || decision.status === filters.status;
    const haystack = `${decision.title} ${decision.action} ${decision.reasonCode} ${decision.evidence}`.toLowerCase();
    const matchesQuery = !filters?.query || haystack.includes(filters.query.toLowerCase());
    return matchesScope && matchesTenant && matchesEnvironment && matchesStatus && matchesQuery;
  });
}

export async function mockListMemories(filters?: {
  type?: string;
  status?: string;
  query?: string;
}) {
  const state = readState();
  return state.memories.filter((memory) => {
    const matchesType = !filters?.type || memory.type.includes(filters.type);
    const matchesStatus = !filters?.status || memory.status === filters.status;
    const haystack = `${memory.title} ${memory.summary} ${memory.evidence}`.toLowerCase();
    const matchesQuery = !filters?.query || haystack.includes(filters.query.toLowerCase());
    return matchesType && matchesStatus && matchesQuery;
  });
}

export async function mockListAuditLogs() {
  return readState().audits;
}

export async function mockExportConfig(configId: string): Promise<string> {
  const state = readState();
  const config = state.configs.find((item) => item.id === configId);
  if (!config) {
    throw new Error("Config document not found");
  }

  return config.yaml;
}

export async function mockImportConfig(kind: ConfigKind, yaml: string) {
  const state = cloneState(readState());
  const existing = state.configs.find((item) => item.kind === kind && item.status !== "archived");
  const config: ConfigDocument = existing
    ? {
        ...existing,
        name: existing.name,
        yaml,
        previousYaml: existing.yaml,
        status: "draft",
        updatedAt: now(),
        version: existing.version + 1,
      }
    : {
        id: id("cfg"),
        kind,
        name: `${kind} document`,
        version: 1,
        status: "draft",
        tenant: "all",
        scope: "global",
        environment: "staging-local",
        updatedAt: now(),
        summary: "Imported from YAML.",
        yaml,
      };

  const next = existing ? config : { ...config };
  if (existing) {
    const index = state.configs.findIndex((item) => item.id === existing.id);
    state.configs[index] = config;
  } else {
    state.configs.unshift(next);
  }

  state.audits.unshift({
    id: id("aud"),
    actor: state.session?.user.email ?? "operator@memoryengine.local",
    role: state.session?.user.role ?? "operator",
    documentKind: kind,
    documentVersion: String(config.version),
    action: "import",
    timestamp: now(),
    diffRef: `${config.id}:yaml`,
  });

  writeState(state);
  return config;
}
