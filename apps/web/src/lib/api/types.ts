export type ConfigKind = "api-ontology" | "memory-ontology" | "policy-profile";

export type ConfigStatus = "draft" | "validated" | "approved" | "published" | "archived";

export type DecisionStatus = "accepted" | "overridden" | "blocked" | "conflicted";

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
