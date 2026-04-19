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
        <h2 className="text-2xl font-semibold tracking-tight text-white">Sign in to the console</h2>
        <p className="text-sm leading-6 text-slate-300">
          Requests go directly to the configured live backend. Authentication errors stay visible in the form instead of being hidden behind fallback behavior.
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
        <div className="rounded-2xl border border-rose-400/25 bg-rose-400/10 p-4 text-sm text-rose-100">{message}</div>
      ) : null}
      <div className="panel-inset space-y-3 p-4 text-sm text-slate-300">
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex rounded-md border border-[color:var(--color-line-strong)] bg-[color:var(--color-card-accent)] px-2.5 py-1 text-xs font-medium text-blue-100">
            Live backend only
          </span>
          <span className="inline-flex rounded-md border border-[color:var(--color-line)] bg-[color:var(--color-card-inset)] px-2.5 py-1 text-xs font-medium text-slate-200">
            Seeded roles available
          </span>
        </div>
        <p>If the service is unavailable, the form shows the request error directly so operators can stop and fix the boundary first.</p>
        <p>Seeded local passwords match the role name: `viewer`, `editor`, `approver`, `operator`, or `admin`.</p>
      </div>
    </Card>
  );
}
