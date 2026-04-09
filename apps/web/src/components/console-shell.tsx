"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { client } from "@/lib/api/client";
import type { Session } from "@/lib/api/types";
import { Badge, Button, Card, cx } from "@/components/ui";

const navGroups = [
  {
    title: "Config",
    items: [
      { href: "/config/api-ontology", label: "API Ontology" },
      { href: "/config/memory-ontology", label: "Memory Ontology" },
      { href: "/config/policy-profile", label: "Policy Profile" },
    ],
  },
  {
    title: "Runtime",
    items: [
      { href: "/validation", label: "Validation" },
      { href: "/simulation", label: "Simulation" },
      { href: "/publication", label: "Publication" },
    ],
  },
  {
    title: "Inspect",
    items: [
      { href: "/decision-explorer", label: "Decision Explorer" },
      { href: "/memory-browser", label: "Memory Browser" },
      { href: "/audit-log", label: "Audit Log" },
    ],
  },
];

function ShellLink({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={cx(
        "flex items-center justify-between rounded-xl px-3 py-2 text-sm transition",
        active ? "bg-cyan-400/15 text-white ring-1 ring-cyan-300/20" : "text-slate-300 hover:bg-white/6 hover:text-white",
      )}
    >
      <span>{label}</span>
      {active ? <span className="h-2 w-2 rounded-full bg-cyan-300" /> : null}
    </Link>
  );
}

export function ConsoleShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const apiBase = process.env.NEXT_PUBLIC_MEMORYENGINE_API_BASE_URL || "mock://local-demo";

  useEffect(() => {
    let active = true;
    client.auth.me().then((value) => {
      if (!active) {
        return;
      }
      setSession(value);
      setReady(true);
    });

    return () => {
      active = false;
    };
  }, []);

  const initials = useMemo(() => {
    const display = session?.user.displayName ?? "Demo User";
    return display
      .split(" ")
      .map((part) => part.slice(0, 1))
      .join("")
      .slice(0, 2)
      .toUpperCase();
  }, [session]);

  const signOut = async () => {
    await client.auth.logout();
    setSession(null);
    router.push("/login");
  };

  if (!ready) {
    return (
      <div className="grid min-h-screen place-items-center px-6">
        <Card className="w-full max-w-md space-y-4 text-center">
          <div className="label">Loading console</div>
          <div className="text-lg font-semibold text-white">Checking local session state</div>
          <p className="text-sm text-slate-400">The mock API boundary and auth session are initializing.</p>
        </Card>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="grid min-h-screen place-items-center px-6">
        <Card className="w-full max-w-lg space-y-4 text-center">
          <div className="label">Authentication required</div>
          <div className="text-2xl font-semibold text-white">Operator console locked</div>
          <p className="text-sm text-slate-300">
            This frontend is wired to the expected local API boundary and falls back to the embedded demo client until the backend is online.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button onClick={() => router.push("/login")}>Go to login</Button>
            <Badge tone="accent">{apiBase}</Badge>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen px-4 py-4 lg:px-6">
      <div className="grid min-h-[calc(100vh-2rem)] gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="panel-strong flex flex-col gap-5 p-5">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="label">MemoryEngine v1</div>
                <h1 className="mt-1 text-2xl font-semibold text-white">Operator Console</h1>
              </div>
              <div className="flex h-11 w-11 items-center justify-center rounded-full bg-cyan-300/12 text-sm font-semibold text-cyan-100 ring-1 ring-cyan-300/20">
                {initials}
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-xs text-slate-300">
              <div className="font-medium text-white">{session.user.displayName}</div>
              <div className="mt-1 flex flex-wrap gap-2">
                <Badge tone="accent">{session.user.role}</Badge>
                <Badge>{session.user.email}</Badge>
              </div>
            </div>
          </div>

          <nav className="space-y-4">
            {navGroups.map((group) => (
              <div key={group.title} className="space-y-2">
                <div className="label">{group.title}</div>
                <div className="space-y-1">
                  {group.items.map((item) => (
                    <ShellLink key={item.href} href={item.href} label={item.label} active={pathname === item.href} />
                  ))}
                </div>
              </div>
            ))}
          </nav>

          <div className="mt-auto space-y-3">
            <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
              <div className="label">Runtime</div>
              <div className="mt-2 text-white">Local API boundary</div>
              <div className="mt-1 break-all text-slate-400">{apiBase}</div>
            </div>
            <Button variant="secondary" onClick={signOut} className="w-full">
              Sign out
            </Button>
          </div>
        </aside>

        <main className="space-y-4">
          <header className="panel flex items-center justify-between gap-4 px-5 py-4">
            <div>
              <div className="label">Control plane</div>
              <div className="text-lg font-semibold text-white">{pathname === "/login" ? "Login" : pathname.replaceAll("/", " ").trim() || "Dashboard"}</div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="success">draft</Badge>
              <Badge tone="accent">validated</Badge>
              <Badge tone="warning">conflicted</Badge>
              <Badge tone="danger">blocked</Badge>
            </div>
          </header>

          <div className="space-y-4 pb-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
