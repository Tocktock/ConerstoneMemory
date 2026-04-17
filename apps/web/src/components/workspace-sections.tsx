"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useConsoleSession } from "@/components/console-shell";
import { client } from "@/lib/api/client";
import type {
  ConfigDocument,
  ConfigKind,
  DecisionRecord,
  MemoryRecord,
  PublicationSnapshot,
  SimulationRun,
  ValidationRun,
} from "@/lib/api/types";
import { Badge, Button, Card, CodeBlock, Input, Label, Metric, Select, Section, Textarea, cx } from "@/components/ui";

type EditorFormat = "yaml" | "json";

function canUseLifecycle(role?: string) {
  return role === "editor" || role === "approver" || role === "operator" || role === "admin";
}

function canApprove(role?: string) {
  return role === "approver" || role === "operator" || role === "admin";
}

function canRollback(role?: string) {
  return role === "operator" || role === "admin";
}

function canArchive(role?: string) {
  return role === "operator" || role === "admin";
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
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const [nextDocs, nextValidations, nextPublications] = await Promise.all([
        client.configs.list({ kind }),
        client.validations.list(),
        client.publications.list({ kind: kind === "api-ontology" ? "api_ontology" : kind === "memory-ontology" ? "memory_ontology" : "policy_profile" }),
      ]);
      setDocs(nextDocs);
      setValidations(nextValidations);
      setPublications(nextPublications);
      const selected = nextDocs.find((doc) => doc.id === (activeId || nextDocs[0]?.id)) ?? null;
      setActive(selected);
      setEditor(selected ? { ...selected } : null);
      setSourceText(selected ? (sourceFormat === "json" ? JSON.stringify(selected.definitionJson ?? {}, null, 2) : selected.yaml) : "");
      if (selected && !activeId) {
        setActiveId(selected.id);
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
  }, [kind]);

  useEffect(() => {
    if (!activeId) {
      return;
    }
    const next = docs.find((doc) => doc.id === activeId) ?? null;
    setActive(next);
    setEditor(next ? { ...next } : null);
    setSourceText(next ? (sourceFormat === "json" ? JSON.stringify(next.definitionJson ?? {}, null, 2) : next.yaml) : "");
  }, [activeId, docs, sourceFormat]);

  const activeFamilyDocs = useMemo(() => {
    if (!active) {
      return [];
    }
    return docs.filter(
      (doc) => doc.scope === active.scope && doc.tenant === active.tenant && doc.environment === active.environment,
    );
  }, [active, docs]);

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
  const lifecycleAllowed = canUseLifecycle(selectedRole);

  const save = async () => {
    if (!editor) return;
    const parsedJson = sourceFormat === "json" ? safeParseJson(sourceText) : editor.definitionJson;
    const saved = await client.configs.save({
      ...editor,
      yaml: sourceFormat === "json" ? editor.yaml : sourceText,
      definitionJson: parsedJson ?? editor.definitionJson ?? {},
      summary: editor.summary,
    });
    setStatusMessage(`Saved ${saved.name} as v${saved.version}.`);
    await refresh();
  };

  const validate = async () => {
    if (!editor) return;
    const result = await client.configs.validate(editor.id);
    setStatusMessage(`Validation ${result.status.toUpperCase()} for ${result.documentId}.`);
    await refresh();
  };

  const approve = async () => {
    if (!editor) return;
    const result = await client.configs.approve(editor.id);
    setStatusMessage(`Approved ${result.id} with status ${result.status}.`);
    await refresh();
  };

  const archive = async () => {
    if (!editor) return;
    const archived = await client.configs.archive(editor.id);
    setStatusMessage(`Archived ${archived.name} v${archived.version}.`);
    setConfirmArchive(false);
    await refresh();
  };

  const publish = async () => {
    if (!currentBundle || !active) return;
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
            <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
              <div className="space-y-3">
                <div className="label">Documents</div>
                <div className="space-y-2">
                  {docs.map((doc) => (
                    <button
                      key={doc.id}
                      onClick={() => setActiveId(doc.id)}
                      className={cx(
                        "w-full rounded-2xl border px-4 py-3 text-left transition",
                        doc.id === activeId ? "border-cyan-300/30 bg-cyan-400/10" : "border-white/10 bg-white/5 hover:bg-white/8",
                      )}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="font-medium text-white">{doc.name}</div>
                        <Badge tone={statusTone(doc.status)}>{doc.status}</Badge>
                      </div>
                      <div className="mt-2 text-xs text-slate-400">{joinItems([`v${doc.version}`, doc.scope, doc.tenant, doc.environment])}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                {editor ? (
                  <>
                    <div className="grid gap-3 md:grid-cols-3">
                      <Metric label="Version" value={`v${editor.version}`} hint="Document revision" />
                      <Metric label="Scope" value={editor.scope} hint="Applies to runtime" />
                      <Metric label="Environment" value={editor.environment} hint="Operator environment" />
                    </div>

                    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
                      <div className="space-y-4">
                        <Card className="space-y-4">
                          <div className="grid gap-4 md:grid-cols-2">
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

                          <div>
                            <Label>Summary</Label>
                            <Textarea className="min-h-24" value={editor.summary} onChange={(event) => setEditor({ ...editor, summary: event.target.value })} />
                          </div>

                          <div className="flex flex-wrap gap-2">
                            <Button onClick={save}>Save draft</Button>
                            <Button variant="secondary" onClick={validate}>
                              Validate
                            </Button>
                            <Button variant="secondary" onClick={approve} disabled={!canApprove(selectedRole)}>
                              Approve
                            </Button>
                            <Button variant="secondary" onClick={() => setConfirmArchive(true)} disabled={!canArchive(selectedRole)}>
                              Archive
                            </Button>
                            <Button variant="secondary" onClick={exportDocument}>
                              Export {sourceFormat.toUpperCase()}
                            </Button>
                            <Button onClick={() => setConfirmPublish(true)} disabled={!currentBundle || !lifecycleAllowed}>
                              Publish bundle
                            </Button>
                          </div>
                          {!lifecycleAllowed ? <p className="text-xs text-slate-400">Your current role is read-only for lifecycle actions.</p> : null}
                        </Card>

                        <Section eyebrow="Raw source" title="Document source">
                          <div className="grid gap-3 md:grid-cols-[160px_minmax(0,1fr)]">
                            <Select value={sourceFormat} onChange={(event) => setSourceFormat(event.target.value as EditorFormat)}>
                              <option value="yaml">YAML</option>
                              <option value="json">JSON</option>
                            </Select>
                            <Button variant="secondary" onClick={() => setSourceText(sourceFormat === "json" ? JSON.stringify(editor.definitionJson ?? {}, null, 2) : editor.yaml)}>
                              Reset from backend
                            </Button>
                          </div>
                          <Textarea
                            value={sourceText}
                            onChange={(event) => setSourceText(event.target.value)}
                            className="min-h-80"
                          />
                        </Section>

                        <Section eyebrow="Revision diff" title="Revision diff">
                          <div className="grid gap-4 md:grid-cols-2">
                            <Card>
                              <div className="label">Previous</div>
                              <CodeBlock>{editor.previousYaml ?? "No previous revision yet."}</CodeBlock>
                            </Card>
                            <Card>
                              <div className="label">Current</div>
                              <CodeBlock>{sourceText || editor.yaml}</CodeBlock>
                            </Card>
                          </div>
                        </Section>
                      </div>

                      <div className="space-y-4">
                        <Card className="space-y-3">
                          <div className="label">Import source</div>
                          <Select value={importFormat} onChange={(event) => setImportFormat(event.target.value as EditorFormat)}>
                            <option value="yaml">YAML</option>
                            <option value="json">JSON</option>
                          </Select>
                          <Textarea
                            className="min-h-56"
                            placeholder={`Paste ${importFormat.toUpperCase()} here`}
                            value={importSource}
                            onChange={(event) => setImportSource(event.target.value)}
                          />
                          <Button variant="secondary" onClick={importDocument}>
                            Import {importFormat.toUpperCase()}
                          </Button>
                        </Card>

                        <Card className="space-y-3">
                          <div className="label">Publish notes</div>
                          <Textarea
                            className="min-h-28"
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
                                <div className="font-medium text-white">{currentBundle.apiOntology.name}</div>
                                <div className="mt-1 text-xs text-slate-400">{joinItems([currentBundle.apiOntology.kind, `v${currentBundle.apiOntology.version}`, currentBundle.apiOntology.status])}</div>
                              </div>
                              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                                <div className="font-medium text-white">{currentBundle.memoryOntology.name}</div>
                                <div className="mt-1 text-xs text-slate-400">{joinItems([currentBundle.memoryOntology.kind, `v${currentBundle.memoryOntology.version}`, currentBundle.memoryOntology.status])}</div>
                              </div>
                              <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                                <div className="font-medium text-white">{currentBundle.policyProfile.name}</div>
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
                                <div className="flex items-center justify-between gap-3">
                                  <div className="font-medium text-white">{shortId(snapshot.configSnapshotId)}</div>
                                  <Badge tone={statusTone(snapshot.status)}>{snapshot.status}</Badge>
                                </div>
                                <div className="mt-1 text-xs text-slate-400">{timestamp(snapshot.publishedAt)} · {snapshot.releaseNotes || "No release notes"}</div>
                              </div>
                            ))}
                            {!publishHistory.length ? <p className="text-sm text-slate-400">No snapshots for this document family yet.</p> : null}
                          </div>
                        </Card>
                      </div>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-slate-400">Select a document to begin editing.</p>
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

  const runValidation = async () => {
    if (!selectedId) return;
    const result = await client.configs.validate(selectedId);
    setCurrent(result);
    await refresh();
  };

  return (
    <Section eyebrow="Validation" title="Validation results" action={<Button onClick={runValidation}>Run validation</Button>}>
      {error ? (
        <StateCard title="Validation data unavailable" body={error} action={<Button onClick={() => void refresh()}>Retry</Button>} />
      ) : loading ? (
        <StateCard title="Loading validations" body="Fetching config documents and validation runs from the backend." />
      ) : (
        <Card className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
            <div className="space-y-3">
              <div className="label">Documents</div>
              <Select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
                <option value="">Select a config document</option>
                {configs.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.name} · {doc.scope} · {doc.tenant}
                  </option>
                ))}
              </Select>
              <div className="space-y-2">
                {validations.map((run) => (
                  <button
                    key={run.id}
                    onClick={() => setCurrent(run)}
                    className={cx(
                      "w-full rounded-2xl border px-4 py-3 text-left transition",
                      current?.id === run.id ? "border-cyan-300/30 bg-cyan-400/10" : "border-white/10 bg-white/5 hover:bg-white/8",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <div className="font-medium text-white">{run.documentName}</div>
                      <Badge tone={statusTone(run.status)}>{run.status}</Badge>
                    </div>
                    <div className="mt-1 text-xs text-slate-400">{timestamp(run.timestamp)}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              {selectedId ? (
                <>
                  <div className="grid gap-3 md:grid-cols-3">
                    <Metric label="Result" value={current ? current.status.toUpperCase() : "PENDING"} hint={current?.summary ?? "Run validation to inspect the selected document."} />
                    <Metric label="Checks" value={String(current?.checks.length ?? 0)} hint="Schema, lifecycle, safety" />
                    <Metric label="Issues" value={String(current?.issues.length ?? 0)} hint="Blocking concerns" />
                  </div>

                  <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
                    <Card className="space-y-3">
                      <div className="label">Selected config</div>
                      {configs.find((doc) => doc.id === selectedId) ? (
                        <div className="space-y-2 text-sm text-slate-300">
                          <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                            <div className="font-medium text-white">{configs.find((doc) => doc.id === selectedId)?.name}</div>
                            <div className="mt-1 text-xs text-slate-400">
                              {joinItems([
                                configs.find((doc) => doc.id === selectedId)?.kind,
                                configs.find((doc) => doc.id === selectedId)?.scope,
                                configs.find((doc) => doc.id === selectedId)?.tenant,
                                configs.find((doc) => doc.id === selectedId)?.environment,
                              ])}
                            </div>
                          </div>
                        </div>
                      ) : null}
                      <div className="space-y-2">
                        {current?.checks.map((check) => (
                          <div key={check.name} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                            <div className="flex items-center justify-between gap-3">
                              <div className="font-medium text-white">{check.name}</div>
                              <Badge tone={statusTone(check.status)}>{check.status}</Badge>
                            </div>
                            <div className="mt-2 text-sm text-slate-300">{check.detail}</div>
                          </div>
                        ))}
                      </div>
                    </Card>
                    <Card className="space-y-3">
                      <div className="label">Issues</div>
                      {current?.issues.length ? (
                        <ul className="space-y-2 text-sm text-rose-100">
                          {current.issues.map((issue) => (
                            <li key={issue} className="rounded-xl border border-rose-300/20 bg-rose-400/10 p-3">
                              {issue}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-slate-400">No validation issues detected.</p>
                      )}
                    </Card>
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-400">Pick a document and run validation to inspect the result.</p>
              )}
            </div>
          </div>
        </Card>
      )}
    </Section>
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
          <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
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
                  <div className="grid gap-3 md:grid-cols-3">
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
                  <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
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
          <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
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
              <div className="grid gap-3 md:grid-cols-3">
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
                      <div className="mt-3 grid gap-3 md:grid-cols-3">
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
          <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
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
                  <div className="grid gap-3 md:grid-cols-3">
                    <Metric label="Snapshot" value={shortId(selectedSnapshot.configSnapshotId)} hint="Published bundle id" />
                    <Metric label="Status" value={selectedSnapshot.status.toUpperCase()} hint={selectedSnapshot.releaseNotes || "No release notes"} />
                    <Metric label="Published" value={timestamp(selectedSnapshot.publishedAt)} hint={selectedSnapshot.publishedBy} />
                  </div>
                  <Card className="space-y-3">
                    <div className="label">Snapshot details</div>
                    <div className="grid gap-3 md:grid-cols-3">
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
            <Input placeholder="Search reason codes" value={filters.query} onChange={(event) => setFilters({ ...filters, query: event.target.value })} />
          </div>

          <div className="grid gap-3 md:grid-cols-4">
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
                <div className="mt-3 grid gap-3 md:grid-cols-4">
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
          <div className="grid gap-3 md:grid-cols-4">
            <Input placeholder="Tenant" value={filters.tenant} onChange={(event) => setFilters({ ...filters, tenant: event.target.value })} />
            <Input placeholder="User" value={filters.user} onChange={(event) => setFilters({ ...filters, user: event.target.value })} />
            <Input placeholder="Scope" value={filters.scope} onChange={(event) => setFilters({ ...filters, scope: event.target.value })} />
            <Input placeholder="Environment" value={filters.environment} onChange={(event) => setFilters({ ...filters, environment: event.target.value })} />
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <Input placeholder="Memory type" value={filters.type} onChange={(event) => setFilters({ ...filters, type: event.target.value })} />
            <Select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
              <option value="">All statuses</option>
              {["active", "blocked", "deleted"].map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
            <Input placeholder="Search title or evidence" value={filters.query} onChange={(event) => setFilters({ ...filters, query: event.target.value })} />
          </div>

          <div className="grid gap-3 md:grid-cols-4">
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
                <div className="mt-3 grid gap-3 md:grid-cols-4">
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

          <div className="grid gap-3 md:grid-cols-4">
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
