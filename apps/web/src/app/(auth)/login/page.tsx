"use client";

import { LoginForm } from "@/components/login-form";
import { Badge, Card } from "@/components/ui";

export default function LoginPage() {
  return (
    <div className="grid min-h-screen place-items-center px-4 py-10">
      <div className="grid w-full max-w-5xl gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="space-y-6 p-8">
          <div className="space-y-3">
            <Badge tone="accent">MemoryEngine v1</Badge>
            <h1 className="text-4xl font-semibold tracking-tight text-white">Operator login</h1>
            <p className="max-w-2xl text-sm leading-6 text-slate-300">
              The console is wired to the local API contract and falls back to the embedded demo client until the backend is available.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
              <div className="label">Control plane</div>
              <div className="mt-2 text-white">Config lifecycle and publication</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
              <div className="label">Runtime</div>
              <div className="mt-2 text-white">Validation and simulation</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
              <div className="label">Inspect</div>
              <div className="mt-2 text-white">Memory and audit history</div>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <LoginForm />
          <Card className="space-y-3 text-sm text-slate-300">
            <div className="label">Demo accounts</div>
            <p>Use `operator@memoryengine.local`, `approver@memoryengine.local`, or `admin@memoryengine.local` to seed different local roles.</p>
            <p>The local password matches the role name, for example `operator` or `admin`.</p>
          </Card>
        </div>
      </div>
    </div>
  );
}
