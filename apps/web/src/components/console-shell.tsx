"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { client } from "@/lib/api/client";
import type { Session } from "@/lib/api/types";
import { Badge, Button, Card, cx } from "@/components/ui";

const ConsoleSessionContext = createContext<Session | null>(null);

export function useConsoleSession() {
  return useContext(ConsoleSessionContext);
}

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
      { href: "/rollback", label: "Rollback" },
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
        "flex min-h-[44px] items-center justify-between rounded-xl px-3 py-2.5 text-[15px] transition sm:min-h-10 sm:py-2 sm:text-sm",
        active ? "bg-cyan-400/15 text-white ring-1 ring-cyan-300/20" : "text-slate-300 hover:bg-white/6 hover:text-white",
      )}
    >
      <span>{label}</span>
      {active ? <span className="h-2 w-2 rounded-full bg-cyan-300" /> : null}
    </Link>
  );
}

function resolvePathTitle(pathname: string) {
  return pathname
    .replace(/^\/+/, "")
    .split("/")
    .filter(Boolean)
    .map((segment) => segment.replaceAll("-", " "))
    .join(" / ") || "Dashboard";
}

export function ConsoleShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [session, setSession] = useState<Session | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const apiBase = process.env.NEXT_PUBLIC_MEMORYENGINE_API_BASE_URL || "";

  const loadSession = () => {
    let active = true;
    setReady(false);
    setError(null);
    client.auth
      .me()
      .then((value) => {
        if (!active) {
          return;
        }
        setSession(value);
        setReady(true);
      })
      .catch((requestError) => {
        if (!active) {
          return;
        }
        setSession(null);
        setError(requestError instanceof Error ? requestError.message : "Unable to reach the backend.");
        setReady(true);
      });

    return () => {
      active = false;
    };
  };

  useEffect(() => {
    const cancel = loadSession();
    return cancel;
  }, []);

  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  useEffect(() => {
    const desktopSidebarMedia = window.matchMedia("(min-width: 1280px)");
    const syncNavMode = (event?: MediaQueryListEvent) => {
      if (event?.matches ?? desktopSidebarMedia.matches) {
        setMobileNavOpen(false);
      }
    };

    syncNavMode();
    desktopSidebarMedia.addEventListener("change", syncNavMode);
    return () => {
      desktopSidebarMedia.removeEventListener("change", syncNavMode);
    };
  }, []);

  useEffect(() => {
    if (!mobileNavOpen) {
      return;
    }
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
    };
  }, [mobileNavOpen]);

  const initials = useMemo(() => {
    const display = session?.user.displayName ?? "Demo User";
    return display
      .split(" ")
      .map((part) => part.slice(0, 1))
      .join("")
      .slice(0, 2)
      .toUpperCase();
  }, [session]);

  const currentNav = useMemo(() => {
    for (const group of navGroups) {
      const item = group.items.find((entry) => entry.href === pathname);
      if (item) {
        return { ...item, groupTitle: group.title };
      }
    }
    return null;
  }, [pathname]);

  const signOut = async () => {
    try {
      await client.auth.logout();
    } finally {
      setSession(null);
      router.push("/login");
    }
  };

  if (!ready) {
    return (
      <div className="grid min-h-screen place-items-center px-6">
        <Card className="w-full max-w-md space-y-4 text-center">
          <div className="label">Loading console</div>
          <div className="text-lg font-semibold text-white">Checking session state</div>
          <p className="text-sm text-slate-400">Contacting the live backend and resolving the current session.</p>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="grid min-h-screen place-items-center px-6">
        <Card className="w-full max-w-xl space-y-4 text-center">
          <div className="label">Backend unavailable</div>
          <div className="text-2xl font-semibold text-white">Operator console cannot start</div>
          <p className="text-sm text-slate-300">{error}</p>
          <div className="flex items-center justify-center gap-3">
            <Button onClick={() => void loadSession()}>Retry</Button>
            <Badge tone="danger">Live backend only</Badge>
          </div>
          {apiBase ? <div className="break-all text-xs text-slate-400">{apiBase}</div> : null}
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
            Sign in against the live backend to continue. This console does not use an embedded session fallback.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button onClick={() => router.push("/login")}>Go to login</Button>
            {apiBase ? <Badge tone="accent">{apiBase}</Badge> : null}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <ConsoleSessionContext.Provider value={session}>
      <div className="min-h-screen px-4 py-4 lg:px-6">
        <div className="grid min-h-[calc(100vh-2rem)] items-start gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
          <div
            className={cx(
              "fixed inset-0 z-40 bg-slate-950/70 backdrop-blur-sm transition xl:hidden",
              mobileNavOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
            )}
            onClick={() => setMobileNavOpen(false)}
            aria-hidden={!mobileNavOpen}
          />

          <aside
            className={cx(
              "panel-strong fixed inset-x-4 top-4 z-50 max-h-[calc(100vh-2rem)] overflow-y-auto p-5 transition xl:hidden",
              mobileNavOpen ? "translate-y-0 opacity-100" : "pointer-events-none -translate-y-4 opacity-0",
            )}
            aria-hidden={!mobileNavOpen}
          >
            <div className="space-y-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="label">MemoryEngine v1</div>
                  <h1 className="mt-1 text-2xl font-semibold text-white">Operator Console</h1>
                </div>
                <Button variant="secondary" onClick={() => setMobileNavOpen(false)}>
                  Close
                </Button>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-xs text-slate-300">
                <div className="font-medium text-white">{session.user.displayName}</div>
                <div className="mt-1 flex flex-wrap gap-2">
                  <Badge tone="accent">{session.user.role}</Badge>
                  <Badge>{session.user.email}</Badge>
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

              <div className="space-y-3">
                <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                  <div className="label">Runtime</div>
                  <div className="mt-2 text-white">Configured API boundary</div>
                  <div className="mt-1 break-all text-slate-400">{apiBase}</div>
                </div>
                <Button variant="secondary" onClick={signOut} className="w-full">
                  Sign out
                </Button>
              </div>
            </div>
          </aside>

          <aside className="panel-strong hidden self-start xl:flex xl:flex-col xl:gap-5 xl:p-5 2xl:sticky 2xl:top-4 2xl:max-h-[calc(100vh-2rem)] 2xl:overflow-y-auto">
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

            <nav className="space-y-4 xl:flex-1">
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

            <div className="space-y-3">
              <div className="rounded-2xl border border-white/10 bg-slate-950/40 p-3 text-xs text-slate-300">
                <div className="label">Runtime</div>
                <div className="mt-2 text-white">Configured API boundary</div>
                <div className="mt-1 break-all text-slate-400">{apiBase}</div>
              </div>
              <Button variant="secondary" onClick={signOut} className="w-full">
                Sign out
              </Button>
            </div>
          </aside>

          <main className="min-w-0 space-y-4">
            <header className="panel px-4 py-4 sm:px-5">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="label">{currentNav?.groupTitle ?? "Control plane"}</div>
                    <div className="mt-1 break-words text-xl font-semibold text-white sm:text-2xl">
                      {pathname === "/login" ? "Login" : currentNav?.label ?? resolvePathTitle(pathname)}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 xl:hidden">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-cyan-300/12 text-sm font-semibold text-cyan-100 ring-1 ring-cyan-300/20">
                      {initials}
                    </div>
                    <Button variant="secondary" onClick={() => setMobileNavOpen(true)}>
                      Menu
                    </Button>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 xl:justify-end">
                  <Button variant="secondary" onClick={signOut} className="xl:hidden">
                    Sign out
                  </Button>
                  <Badge tone="success">draft</Badge>
                  <Badge tone="accent">validated</Badge>
                  <Badge tone="warning">conflicted</Badge>
                  <Badge tone="danger">blocked</Badge>
                </div>
              </div>
            </header>

            <div className="space-y-4 pb-6">{children}</div>
          </main>
        </div>
      </div>
    </ConsoleSessionContext.Provider>
  );
}
