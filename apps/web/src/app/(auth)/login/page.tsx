"use client";

import { LoginForm } from "@/components/login-form";
import { Badge, Card } from "@/components/ui";

export default function LoginPage() {
  return (
    <div className="mx-auto grid min-h-screen max-w-6xl items-center gap-6 px-4 py-8 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,460px)]">
      <Card className="panel-strong relative overflow-hidden p-8 sm:p-10">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(88,166,255,0.16),transparent_32%)]" />
        <div className="relative space-y-8">
          <div className="space-y-4">
            <Badge tone="accent">MemoryEngine v1</Badge>
            <div className="space-y-3">
              <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                Operate the memory lifecycle with clearer control-plane hierarchy.
              </h1>
              <p className="max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
                This console exists for operators, not end users. The first pass prioritizes scanability, live-backend accountability, and control-plane discipline over decorative admin chrome.
              </p>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="panel-muted p-4 text-sm text-slate-300">
              <div className="label">Config</div>
              <div className="mt-2 font-semibold text-white">Ontology and policy authoring</div>
              <p className="mt-2 leading-6 text-slate-400">Stage API, memory, and policy changes through one operator workflow.</p>
            </div>
            <div className="panel-muted p-4 text-sm text-slate-300">
              <div className="label">Runtime</div>
              <div className="mt-2 font-semibold text-white">Validation and simulation</div>
              <p className="mt-2 leading-6 text-slate-400">Test the control plane before publication changes future event handling.</p>
            </div>
            <div className="panel-muted p-4 text-sm text-slate-300">
              <div className="label">Inspect</div>
              <div className="mt-2 font-semibold text-white">Memory, decisions, and audit</div>
              <p className="mt-2 leading-6 text-slate-400">Trace evidence, runtime decisions, and publication lineage from one surface.</p>
            </div>
          </div>

          <div className="panel-inset space-y-3 p-5 text-sm text-slate-300">
            <div className="label">Current direction</div>
            <p className="leading-6 text-slate-200">
              GitHub Primer informs the information hierarchy, repo-local shadcn/ui-style primitives anchor the shared component layer, and Tailwind enforces spacing, state, and responsive consistency.
            </p>
            <p className="leading-6 text-slate-400">
              The implementation starts with shell hierarchy and the login gateway before route-specific page rewrites.
            </p>
          </div>
        </div>
      </Card>

      <div className="space-y-4">
        <LoginForm />
      </div>
    </div>
  );
}
