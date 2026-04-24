"use client";

import { LoginForm } from "@/components/login-form";
import { Badge } from "@/components/ui";

export default function LoginPage() {
  return (
    <div className="relative min-h-[100dvh] px-4 py-6 sm:px-6 lg:px-8">
      <div className="console-noise" />
      <div className="relative mx-auto grid min-h-[calc(100dvh-3rem)] max-w-5xl items-center gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(340px,420px)]">
        <div className="relative overflow-hidden rounded-3xl border border-[color:var(--color-line-subtle)] p-7 sm:p-10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.12),transparent_30rem)]" />
          <div className="relative space-y-6">
            <div className="space-y-4">
              <Badge tone="accent">MemoryEngine v1</Badge>
              <div className="space-y-3">
                <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-white text-balance sm:text-5xl">
                  Operator control for ontology, policy, and memory behavior.
                </h1>
                <p className="max-w-2xl text-sm leading-7 text-slate-300 sm:text-base">
                  Author versioned product data, validate changes before publication, and inspect runtime evidence without losing config snapshot lineage.
                </p>
              </div>
            </div>

            <ul className="space-y-3 border-t border-[color:var(--color-line-subtle)] pt-5 text-sm leading-6 text-slate-300">
              <li>Config authoring, validation, and publication stay in one operator flow.</li>
              <li>Runtime decisions remain traceable to evidence and config snapshots.</li>
              <li>Expert tools stay available without taking over the first screen.</li>
            </ul>
          </div>
        </div>

        <div className="space-y-4">
          <LoginForm />
        </div>
      </div>
    </div>
  );
}
