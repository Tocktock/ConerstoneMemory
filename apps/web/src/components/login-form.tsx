"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { client } from "@/lib/api/client";
import { Button, Card, Input, Label } from "@/components/ui";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("operator@memoryengine.local");
  const [password, setPassword] = useState("operator");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      await client.auth.login(email, password);
      router.push("/config/api-ontology");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="space-y-6 p-6 sm:p-7">
      <div className="space-y-2">
        <div className="label">Operator access</div>
        <h2 className="text-2xl font-semibold tracking-tight text-white text-balance">Sign in to the console</h2>
        <p className="text-sm leading-6 text-slate-300">
          Requests go directly to the configured backend. Authentication errors stay in the form so the boundary is easy to diagnose.
        </p>
      </div>
      <form className="space-y-4" onSubmit={submit}>
        <div className="space-y-2">
          <Label>Email</Label>
          <Input
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="operator@memoryengine.local"
            autoComplete="username"
          />
        </div>
        <div className="space-y-2">
          <Label>Password</Label>
          <Input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
          />
        </div>
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Signing in..." : "Sign in"}
        </Button>
      </form>
      {message ? (
        <div className="rounded-xl border border-rose-300/28 bg-rose-400/12 p-4 text-sm leading-6 text-rose-100">{message}</div>
      ) : null}
      <div className="panel-inset space-y-3 p-4 text-sm text-slate-300">
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex rounded-md border border-cyan-300/26 bg-cyan-400/10 px-2.5 py-1 text-xs font-semibold text-cyan-200">
            Live backend only
          </span>
          <span className="inline-flex rounded-md border border-[color:var(--color-line-subtle)] bg-white/[0.035] px-2.5 py-1 text-xs font-semibold text-slate-300">
            Seeded roles available
          </span>
        </div>
        <p>If the service is unavailable, the form shows the request error directly so operators can stop and fix the boundary first.</p>
        <p>
          Seeded local passwords match the role name: <code>viewer</code>, <code>editor</code>, <code>approver</code>, <code>operator</code>, or <code>admin</code>.
        </p>
      </div>
    </Card>
  );
}
