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
  updatedAt: string;
  lastPublishedAt?: string;
  summary: string;
  yaml: string;
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
  diff: string;
}

export interface PublicationSnapshot {
  id: string;
  documentId: string;
  documentName: string;
  version: number;
  status: "active" | "rolled-back" | "archived";
  createdAt: string;
  createdBy: string;
  configSnapshotId: string;
  note: string;
}

export interface DecisionRecord {
  id: string;
  title: string;
  action: string;
  status: DecisionStatus;
  scope: string;
  tenant: string;
  environment: string;
  reasonCode: string;
  configSnapshotId: string;
  evidence: string;
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
  status: "active" | "blocked" | "deleted";
  evidence: string;
  configSnapshotId: string;
  timestamp: string;
}

export interface AuditRecord {
  id: string;
  actor: string;
  role: string;
  documentKind: string;
  documentVersion: string;
  action: string;
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
