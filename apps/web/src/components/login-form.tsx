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
    <Card className="space-y-5">
      <form className="space-y-4" onSubmit={submit}>
        <div className="space-y-2">
          <div className="label">Email</div>
          <Input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="operator@memoryengine.local" />
        </div>
        <div className="space-y-2">
          <div className="label">Password</div>
          <Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" />
        </div>
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Signing in..." : "Sign in"}
        </Button>
      </form>
      <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
        The page first tries the local API boundary and falls back to the embedded demo session when the backend is unavailable.
      </div>
      <div className="rounded-2xl border border-cyan-300/15 bg-cyan-400/5 p-4 text-sm text-cyan-50">
        Seeded local passwords match the role name: `viewer`, `editor`, `approver`, `operator`, or `admin`.
      </div>
      {message ? <p className="text-sm text-rose-200">{message}</p> : null}
    </Card>
  );
}
