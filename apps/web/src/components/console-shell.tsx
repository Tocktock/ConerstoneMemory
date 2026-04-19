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

type NavItem = {
  href: string;
  label: string;
  summary: string;
  focus: string;
};

type NavGroup = {
  title: string;
  description: string;
  items: NavItem[];
};

const navGroups: NavGroup[] = [
  {
    title: "Config",
    description: "Author the control-plane documents that drive runtime behavior.",
    items: [
      {
        href: "/config/api-ontology",
        label: "API Ontology",
        summary: "Define event routing, workflow relationships, and package structure.",
        focus: "Draft, validate, approve, and publish package changes.",
      },
      {
        href: "/config/memory-ontology",
        label: "Memory Ontology",
        summary: "Model memory types, identity strategies, and supersession rules.",
        focus: "Tune durable memory definitions and retrieval behavior.",
      },
      {
        href: "/config/policy-profile",
        label: "Policy Profile",
        summary: "Set sensitivity ceilings, inference rules, and forget behavior.",
        focus: "Adjust operator policy without changing code.",
      },
    ],
  },
  {
    title: "Runtime",
    description: "Exercise the runtime before and after publication.",
    items: [
      {
        href: "/validation",
        label: "Validation",
        summary: "Review document health, warnings, and publish blockers.",
        focus: "Run validation and interpret failing checks quickly.",
      },
      {
        href: "/simulation",
        label: "Simulation",
        summary: "Replay a sample event and inspect decision outcomes safely.",
        focus: "Compose a sample event before you publish.",
      },
      {
        href: "/publication",
        label: "Publication",
        summary: "Promote reviewed snapshots and inspect release notes.",
        focus: "Track active and historical releases by snapshot.",
      },
      {
        href: "/rollback",
        label: "Rollback",
        summary: "Revert future behavior to an earlier snapshot without redeploy.",
        focus: "Operate rollback with explicit consequence framing.",
      },
    ],
  },
  {
    title: "Inspect",
    description: "Trace the runtime after decisions are made.",
    items: [
      {
        href: "/decision-explorer",
        label: "Decision Explorer",
        summary: "Inspect evidence, reason codes, and snapshot lineage.",
        focus: "Trace why a runtime decision happened.",
      },
      {
        href: "/memory-browser",
        label: "Memory Browser",
        summary: "Search structured memories and verify retrieval visibility.",
        focus: "Query user records and inspect active memory state.",
      },
      {
        href: "/audit-log",
        label: "Audit Log",
        summary: "Review operator actions and system lifecycle transitions.",
        focus: "Filter operational history and publication activity.",
      },
    ],
  },
];

function ShellLink({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <Link
      href={item.href}
      className={cx(
        "group flex min-h-[52px] items-start justify-between gap-3 rounded-2xl border px-3 py-3 transition",
        active
          ? "border-[color:var(--color-line-strong)] bg-[color:var(--color-card-accent)] text-white shadow-sm"
          : "border-transparent text-slate-300 hover:border-white/8 hover:bg-white/5 hover:text-white",
      )}
    >
      <div className="min-w-0">
        <div className="text-sm font-semibold sm:text-[15px]">{item.label}</div>
        <div className="mt-1 text-xs leading-5 text-slate-400 group-hover:text-slate-300">{item.summary}</div>
      </div>
      <span className={cx("mt-1 h-2.5 w-2.5 rounded-full", active ? "bg-[color:var(--color-accent)]" : "bg-transparent")} />
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

function summarizeApiBase(apiBase: string) {
  if (!apiBase) {
    return { host: "Not configured", value: "Set NEXT_PUBLIC_MEMORYENGINE_API_BASE_URL." };
  }

  try {
    const url = new URL(apiBase);
    return { host: url.host, value: url.toString() };
  } catch {
    return { host: apiBase, value: apiBase };
  }
}

function SidebarContent({
  session,
  initials,
  pathname,
  apiBase,
  onClose,
  onSignOut,
}: {
  session: Session;
  initials: string;
  pathname: string;
  apiBase: string;
  onClose?: () => void;
  onSignOut: () => void | Promise<void>;
}) {
  const boundary = summarizeApiBase(apiBase);
  const activeGroup = navGroups.find((group) => group.items.some((item) => item.href === pathname));

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-3">
            <Badge tone="accent">MemoryEngine v1</Badge>
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-white">Human-configurable operator console</h1>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                Author ontology and policy packages, validate changes, and inspect runtime evidence without losing snapshot lineage.
              </p>
            </div>
          </div>
          {onClose ? (
            <Button variant="ghost" onClick={onClose}>
              Close
            </Button>
          ) : null}
        </div>

        <div className="panel-inset space-y-4 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-sm font-semibold text-white">{session.user.displayName}</div>
              <div className="mt-1 break-all text-xs leading-5 text-slate-400">{session.user.email}</div>
            </div>
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-[color:var(--color-line)] bg-white/5 text-sm font-semibold text-slate-100">
              {initials}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge tone="accent">{session.user.role}</Badge>
            {activeGroup ? <Badge>{activeGroup.title}</Badge> : null}
          </div>
        </div>
      </div>

      <nav className="space-y-4">
        {navGroups.map((group) => (
          <div key={group.title} className="space-y-2">
            <div className="space-y-1">
              <div className="label">{group.title}</div>
              <p className="text-xs leading-5 text-slate-500">{group.description}</p>
            </div>
            <div className="space-y-2">
              {group.items.map((item) => (
                <ShellLink key={item.href} item={item} active={pathname === item.href} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="space-y-3">
        <div className="panel-inset space-y-2 p-4 text-xs text-slate-300">
          <div className="label">Live backend</div>
          <div className="text-sm font-semibold text-white">{boundary.host}</div>
          <div className="break-all leading-5 text-slate-400">{boundary.value}</div>
        </div>
        <Button variant="secondary" onClick={onSignOut} className="w-full">
          Sign out
        </Button>
      </div>
    </div>
  );
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
        return { ...item, groupTitle: group.title, groupDescription: group.description };
      }
    }
    return null;
  }, [pathname]);
  const boundary = useMemo(() => summarizeApiBase(apiBase), [apiBase]);

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
          <Badge tone="accent">Loading console</Badge>
          <div className="text-lg font-semibold text-white">Checking session state</div>
          <p className="text-sm text-slate-400">Contacting the configured API boundary and resolving the current operator session.</p>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="grid min-h-screen place-items-center px-6">
        <Card className="w-full max-w-xl space-y-4 text-center">
          <Badge tone="danger">Backend unavailable</Badge>
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
          <Badge tone="accent">Authentication required</Badge>
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
      <div className="min-h-screen px-3 py-3 sm:px-4 sm:py-4 lg:px-6">
        <div className="grid min-h-[calc(100vh-1.5rem)] items-start gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
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
              "panel-sidebar fixed inset-x-4 top-4 z-50 max-h-[calc(100vh-2rem)] overflow-y-auto p-5 transition xl:hidden",
              mobileNavOpen ? "translate-y-0 opacity-100" : "pointer-events-none -translate-y-4 opacity-0",
            )}
            aria-hidden={!mobileNavOpen}
          >
            <SidebarContent
              session={session}
              initials={initials}
              pathname={pathname}
              apiBase={apiBase}
              onClose={() => setMobileNavOpen(false)}
              onSignOut={signOut}
            />
          </aside>

          <aside className="panel-sidebar hidden self-start xl:flex xl:flex-col xl:gap-5 xl:p-5 2xl:sticky 2xl:top-4 2xl:max-h-[calc(100vh-2rem)] 2xl:overflow-y-auto">
            <SidebarContent session={session} initials={initials} pathname={pathname} apiBase={apiBase} onSignOut={signOut} />
          </aside>

          <main className="min-w-0 space-y-4">
            <header className="panel px-4 py-4 sm:px-6 sm:py-5">
              <div className="flex flex-col gap-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 space-y-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="accent">{currentNav?.groupTitle ?? "Control plane"}</Badge>
                      <Badge>{session.user.role}</Badge>
                    </div>
                    <div>
                      <div className="label">Current workspace</div>
                      <h1 className="mt-2 break-words text-2xl font-semibold tracking-tight text-white sm:text-3xl">
                        {pathname === "/login" ? "Login" : currentNav?.label ?? resolvePathTitle(pathname)}
                      </h1>
                      <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-300">
                        {currentNav?.summary ??
                          "Navigate the control plane, validate configuration, and inspect runtime evidence with live backend context."}
                      </p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2 xl:hidden">
                    <Button variant="secondary" onClick={() => setMobileNavOpen(true)}>
                      Menu
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <div className="panel-inset p-4">
                    <div className="label">Focus</div>
                    <div className="mt-2 text-sm font-semibold text-white">{currentNav?.focus ?? "Operate the control plane."}</div>
                    <p className="mt-1 text-xs leading-5 text-slate-400">
                      Shared chrome now frames the primary task before lower-priority diagnostics.
                    </p>
                  </div>
                  <div className="panel-inset p-4">
                    <div className="label">Operator</div>
                    <div className="mt-2 text-sm font-semibold text-white">{session.user.displayName}</div>
                    <p className="mt-1 break-all text-xs leading-5 text-slate-400">{session.user.email}</p>
                  </div>
                  <div className="panel-inset p-4">
                    <div className="label">API boundary</div>
                    <div className="mt-2 text-sm font-semibold text-white">{boundary.host}</div>
                    <p className="mt-1 break-all text-xs leading-5 text-slate-400">{boundary.value}</p>
                  </div>
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
