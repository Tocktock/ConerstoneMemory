"use client";

import { useEffect, useMemo, useState } from "react";
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

export function ConfigWorkspace({ kind }: { kind: ConfigKind }) {
  const meta = kindMeta[kind];
  const [docs, setDocs] = useState<ConfigDocument[]>([]);
  const [activeId, setActiveId] = useState<string>("");
  const [active, setActive] = useState<ConfigDocument | null>(null);
  const [editor, setEditor] = useState<ConfigDocument | null>(null);
  const [validations, setValidations] = useState<ValidationRun[]>([]);
  const [publications, setPublications] = useState<PublicationSnapshot[]>([]);
  const [importYaml, setImportYaml] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [confirmPublish, setConfirmPublish] = useState(false);

  const refresh = async () => {
    const [nextDocs, nextValidations, nextPublications] = await Promise.all([
      client.configs.list(kind),
      client.validations.list(),
      client.publications.list(),
    ]);
    setDocs(nextDocs);
    setValidations(nextValidations.filter((item) => nextDocs.some((doc) => doc.id === item.documentId)));
    setPublications(nextPublications.filter((item) => nextDocs.some((doc) => doc.id === item.documentId)));
    const selected = nextDocs.find((doc) => doc.id === (activeId || nextDocs[0]?.id)) ?? null;
    setActive(selected);
    setEditor(selected ? { ...selected } : null);
    if (selected && !activeId) {
      setActiveId(selected.id);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  useEffect(() => {
    if (!activeId) return;
    const next = docs.find((doc) => doc.id === activeId) ?? null;
    setActive(next);
    setEditor(next ? { ...next } : null);
  }, [activeId, docs]);

  const latestValidation = useMemo(
    () => (active ? validations.filter((item) => item.documentId === active.id)[0] ?? null : null),
    [active, validations],
  );

  const publishHistory = useMemo(
    () => publications.filter((item) => active && item.documentId === active.id),
    [active, publications],
  );

  const save = async () => {
    if (!editor) return;
    const saved = await client.configs.save(editor);
    setStatusMessage(`Saved ${saved.name} as v${saved.version}.`);
    await refresh();
  };

  const validate = async () => {
    if (!editor) return;
    const result = await client.configs.validate(editor.id);
    setStatusMessage(`Validation ${result.status.toUpperCase()} for ${result.documentName}.`);
    await refresh();
  };

  const publish = async () => {
    if (!editor) return;
    const snapshot = await client.configs.publish(editor.id);
    setStatusMessage(`Published snapshot ${shortId(snapshot.configSnapshotId)}.`);
    setConfirmPublish(false);
    await refresh();
  };

  const importDocument = async () => {
    if (!importYaml.trim()) return;
    await client.configs.importYaml(kind, importYaml);
    setStatusMessage("YAML imported into the active document set.");
    setImportYaml("");
    await refresh();
  };

  const exportDocument = async () => {
    if (!editor) return;
    const yaml = await client.configs.exportYaml(editor.id);
    await navigator.clipboard.writeText(yaml);
    setStatusMessage("YAML copied to clipboard.");
  };

  return (
    <div className="space-y-4">
      <Section
        eyebrow={meta.eyebrow}
        title={meta.title}
        action={<Badge tone={statusTone(active?.status ?? "draft")}>{active?.status ?? "draft"}</Badge>}
      >
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
                    <div className="mt-2 text-xs text-slate-400">
                      v{doc.version} · {doc.scope} · {doc.tenant}
                    </div>
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
                            <Input
                              value={editor.name}
                              onChange={(event) => setEditor({ ...editor, name: event.target.value })}
                            />
                          </div>
                          <div>
                            <Label>Status</Label>
                            <Select
                              value={editor.status}
                              onChange={(event) =>
                                setEditor({
                                  ...editor,
                                  status: event.target.value as ConfigDocument["status"],
                                })
                              }
                            >
                              {["draft", "validated", "approved", "published", "archived"].map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </Select>
                          </div>
                          <div>
                            <Label>Tenant</Label>
                            <Input
                              value={editor.tenant}
                              onChange={(event) => setEditor({ ...editor, tenant: event.target.value })}
                            />
                          </div>
                          <div>
                            <Label>Scope</Label>
                            <Input
                              value={editor.scope}
                              onChange={(event) => setEditor({ ...editor, scope: event.target.value })}
                            />
                          </div>
                        </div>

                        <div>
                          <Label>Summary</Label>
                          <Textarea
                            className="min-h-24"
                            value={editor.summary}
                            onChange={(event) => setEditor({ ...editor, summary: event.target.value })}
                          />
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <Button onClick={save}>Save draft</Button>
                          <Button variant="secondary" onClick={validate}>
                            Validate
                          </Button>
                          <Button variant="secondary" onClick={exportDocument}>
                            Export YAML
                          </Button>
                          <Button onClick={() => setConfirmPublish(true)}>Publish</Button>
                        </div>
                      </Card>

                      <Section eyebrow="Raw YAML editor" title="Document source">
                        <Textarea
                          value={editor.yaml}
                          onChange={(event) => setEditor({ ...editor, yaml: event.target.value })}
                        />
                      </Section>

                      <Section eyebrow="Diff viewer" title="Revision diff">
                        <div className="grid gap-4 md:grid-cols-2">
                          <Card>
                            <div className="label">Previous</div>
                            <CodeBlock>{editor.previousYaml ?? "No previous revision yet."}</CodeBlock>
                          </Card>
                          <Card>
                            <div className="label">Current</div>
                            <CodeBlock>{editor.yaml}</CodeBlock>
                          </Card>
                        </div>
                      </Section>
                    </div>

                    <div className="space-y-4">
                      <Card className="space-y-3">
                        <div className="label">Import YAML</div>
                        <Textarea
                          className="min-h-56"
                          placeholder={`Paste ${kind} YAML here`}
                          value={importYaml}
                          onChange={(event) => setImportYaml(event.target.value)}
                        />
                        <Button variant="secondary" onClick={importDocument}>
                          Import YAML
                        </Button>
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
                              <div className="mt-1 text-xs text-slate-400">
                                {timestamp(snapshot.createdAt)} · v{snapshot.version}
                              </div>
                            </div>
                          ))}
                          {!publishHistory.length ? <p className="text-sm text-slate-400">No snapshots for this document yet.</p> : null}
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
      </Section>

      <ConfirmGate
        title={`Publish ${editor?.name ?? "document"}?`}
        body="This will create an immutable config snapshot and mark the current runtime version as active."
        open={confirmPublish}
        confirmLabel="Publish snapshot"
        onCancel={() => setConfirmPublish(false)}
        onConfirm={() => {
          void publish();
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

  const refresh = async () => {
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
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runValidation = async () => {
    if (!selectedId) return;
    const result = await client.configs.validate(selectedId);
    setCurrent(result);
    await refresh();
  };

  return (
    <Section eyebrow="Validation" title="Validation results" action={<Button onClick={runValidation}>Run validation</Button>}>
      <Card className="space-y-4">
        <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div className="space-y-3">
            <div className="label">Documents</div>
            <Select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
              <option value="">Select a config document</option>
              {configs.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.name}
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
            {current ? (
              <>
                <div className="grid gap-3 md:grid-cols-3">
                  <Metric label="Result" value={current.status.toUpperCase()} hint={current.summary} />
                  <Metric label="Checks" value={String(current.checks.length)} hint="Schema, lifecycle, safety" />
                  <Metric label="Issues" value={String(current.issues.length)} hint="Blocking concerns" />
                </div>

                <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
                  <Card className="space-y-3">
                    <div className="label">Check output</div>
                    <div className="space-y-2">
                      {current.checks.map((check) => (
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
                    {current.issues.length ? (
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
    </Section>
  );
}

export function SimulationWorkspace() {
  const [configs, setConfigs] = useState<ConfigDocument[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [sampleEvent, setSampleEvent] = useState("action: docs.openDocument\nuser: demo\ncontext: local");
  const [current, setCurrent] = useState<SimulationRun | null>(null);

  useEffect(() => {
    void client.configs.list().then((docs) => {
      setConfigs(docs);
      if (!selectedId && docs[0]) {
        setSelectedId(docs[0].id);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runSimulation = async () => {
    if (!selectedId) return;
    const result = await client.configs.simulate(selectedId, sampleEvent);
    setCurrent(result);
  };

  return (
    <Section eyebrow="Simulation" title="Simulation runner" action={<Button onClick={runSimulation}>Run simulation</Button>}>
      <Card className="space-y-4">
        <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="space-y-3">
            <div>
              <Label>Config document</Label>
              <Select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
                <option value="">Select a document</option>
                {configs.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Sample event</Label>
              <Select
                value={sampleEvent}
                onChange={(event) => setSampleEvent(event.target.value)}
                className="mb-2"
              >
                <option value="action: docs.openDocument\nuser: demo\ncontext: local">docs.openDocument</option>
                <option value="action: profile.updateAddress\nuser: demo\ncontext: local">profile.updateAddress</option>
                <option value="action: search.webSearch\nuser: demo\ncontext: local">search.webSearch</option>
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
                  <Metric label="Reason codes" value={String(current.reasonCodes.length)} hint="Explanation tokens" />
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
                  </Card>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-400">Run a simulation to compare before and after decisions.</p>
            )}
          </div>
        </div>
      </Card>
    </Section>
  );
}

export function PublicationWorkspace() {
  const [configs, setConfigs] = useState<ConfigDocument[]>([]);
  const [publications, setPublications] = useState<PublicationSnapshot[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [confirmRollback, setConfirmRollback] = useState<string | null>(null);

  const refresh = async () => {
    const [nextConfigs, nextPublications] = await Promise.all([client.configs.list(), client.publications.list()]);
    setConfigs(nextConfigs);
    setPublications(nextPublications);
    if (!selectedId && nextConfigs[0]) {
      setSelectedId(nextConfigs[0].id);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const currentSnapshots = publications.filter((item) => !selectedId || item.documentId === selectedId);

  return (
    <Section eyebrow="Publication" title="Publication history">
      <Card className="space-y-4">
        <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
          <div className="space-y-3">
            <Label>Document</Label>
            <Select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
              <option value="">All documents</option>
              {configs.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.name}
                </option>
              ))}
            </Select>
            <div className="space-y-2">
              {currentSnapshots.map((snapshot) => (
                <div key={snapshot.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-white">{snapshot.documentName}</div>
                    <Badge tone={statusTone(snapshot.status)}>{snapshot.status}</Badge>
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    {timestamp(snapshot.createdAt)} · {shortId(snapshot.configSnapshotId)}
                  </div>
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
              <div className="label">Rollback history</div>
              <div className="space-y-2">
                {currentSnapshots.map((snapshot) => (
                  <div key={snapshot.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="space-y-1">
                        <div className="font-medium text-white">{snapshot.note}</div>
                        <div className="text-xs text-slate-400">
                          {snapshot.createdBy} · {timestamp(snapshot.createdAt)}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge tone={statusTone(snapshot.status)}>{snapshot.status}</Badge>
                        <Button variant="secondary" onClick={() => setConfirmRollback(snapshot.id)}>
                          Roll back
                        </Button>
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

      <ConfirmGate
        title="Rollback active runtime snapshot?"
        body="This will reactivate the selected snapshot for future events without touching historical audit data."
        open={Boolean(confirmRollback)}
        confirmLabel="Rollback snapshot"
        danger
        onCancel={() => setConfirmRollback(null)}
        onConfirm={() => {
          if (!confirmRollback) return;
          void client.configs.rollback(confirmRollback).then(() => {
            setConfirmRollback(null);
            void refresh();
          });
        }}
      />
    </Section>
  );
}

export function DecisionExplorerWorkspace() {
  const [filters, setFilters] = useState({ scope: "", tenant: "", environment: "", status: "", query: "" });
  const [decisions, setDecisions] = useState<DecisionRecord[]>([]);

  const refresh = async () => {
    setDecisions(
      await client.decisions.list({
        scope: filters.scope || undefined,
        tenant: filters.tenant || undefined,
        environment: filters.environment || undefined,
        status: filters.status || undefined,
        query: filters.query || undefined,
      }),
    );
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  return (
    <Section eyebrow="Decision explorer" title="Decision explorer">
      <Card className="space-y-4">
        <div className="grid gap-3 md:grid-cols-5">
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
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="font-medium text-white">{decision.title}</div>
                  <div className="mt-1 text-xs text-slate-400">
                    {decision.action} · {decision.scope} · {decision.tenant} · {decision.environment}
                  </div>
                </div>
                <Badge tone={statusTone(decision.status)}>{decision.status}</Badge>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                  <div className="label">Reason code</div>
                  <div className="mt-1 text-sm text-white">{decision.reasonCode}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                  <div className="label">Config snapshot</div>
                  <div className="mt-1 font-mono text-sm text-white">{shortId(decision.configSnapshotId)}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                  <div className="label">Evidence</div>
                  <div className="mt-1 text-sm text-white">{decision.evidence}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </Section>
  );
}

export function MemoryBrowserWorkspace() {
  const [filters, setFilters] = useState({ type: "", status: "", query: "" });
  const [memories, setMemories] = useState<MemoryRecord[]>([]);

  const refresh = async () => {
    setMemories(
      await client.memories.list({
        type: filters.type || undefined,
        status: filters.status || undefined,
        query: filters.query || undefined,
      }),
    );
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  return (
    <Section eyebrow="Memory browser" title="User memory browser">
      <Card className="space-y-4">
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
          <Metric label="Avg confidence" value={`${Math.round((memories.reduce((sum, item) => sum + item.confidence, 0) / Math.max(memories.length, 1)) * 100)}%`} hint="Seeded confidence" />
        </div>

        <div className="space-y-2">
          {memories.map((memory) => (
            <div key={memory.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <div className="font-medium text-white">{memory.title}</div>
                  <div className="mt-1 text-xs text-slate-400">
                    {memory.type} · {memory.scope} · {memory.tenant} · {timestamp(memory.timestamp)}
                  </div>
                </div>
                <Badge tone={statusTone(memory.status)}>{memory.status}</Badge>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                  <div className="label">Summary</div>
                  <div className="mt-1 text-sm text-white">{memory.summary}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                  <div className="label">Evidence</div>
                  <div className="mt-1 text-sm text-white">{memory.evidence}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                  <div className="label">Config snapshot</div>
                  <div className="mt-1 font-mono text-sm text-white">{shortId(memory.configSnapshotId)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </Section>
  );
}

export function AuditLogWorkspace() {
  const [records, setRecords] = useState<Awaited<ReturnType<typeof client.audit.list>>>([]);

  useEffect(() => {
    void client.audit.list().then(setRecords);
  }, []);

  return (
    <Section eyebrow="Audit log" title="Audit log viewer">
      <Card className="space-y-4">
        <div className="grid gap-3 md:grid-cols-4">
          <Metric label="Events" value={String(records.length)} hint="Logged operator actions" />
          <Metric label="Publishes" value={String(records.filter((item) => item.action === "publish").length)} hint="Config publication events" />
          <Metric label="Rollbacks" value={String(records.filter((item) => item.action === "rollback").length)} hint="Snapshot rollbacks" />
          <Metric label="Validations" value={String(records.filter((item) => item.action === "validate").length)} hint="Validation runs" />
        </div>

        <div className="overflow-hidden rounded-2xl border border-white/10">
          <table className="min-w-full divide-y divide-white/10 text-left text-sm">
            <thead className="bg-white/5 text-xs uppercase tracking-[0.18em] text-slate-400">
              <tr>
                <th className="px-4 py-3">Actor</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Document</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Version</th>
                <th className="px-4 py-3">Diff reference</th>
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
                  <td className="px-4 py-3 text-slate-300">{record.documentKind}</td>
                  <td className="px-4 py-3 text-white">{record.action}</td>
                  <td className="px-4 py-3 text-slate-300">{record.documentVersion}</td>
                  <td className="px-4 py-3 font-mono text-xs text-cyan-100">{record.diffRef}</td>
                  <td className="px-4 py-3 text-slate-400">{timestamp(record.timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </Section>
  );
}
